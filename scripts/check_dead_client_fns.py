#!/usr/bin/env python3
"""Find dead frontend API client functions whose URLs no longer exist on the backend.

Uses the live FastAPI OpenAPI schema as the source of truth (NOT a regex over
router files), so route prefixes, path-param renames, and method changes are
all caught. Compares against `apiFetch(...)` calls in frontend/src/lib/api.ts.

Run from repo root:
    uv run python scripts/check_dead_client_fns.py

Exits non-zero if any dead URL is found — wire into CI to prevent regressions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _load_backend_paths() -> set[str]:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))
    from api.main import app  # noqa: E402  (delayed to keep CLI startup snappy)

    return set(app.openapi().get("paths", {}).keys())


_APIFETCH_RE = re.compile(
    r"""apiFetch          # the call
        (?:<[^>]*>)?      # optional generic
        \(\s*             # opening paren
        ['"`]             # opening quote
        ([^'"`]+)         # path body (lazy-stops at next quote of same kind)
        ['"`]             # closing quote
    """,
    re.VERBOSE,
)


def _normalize_client_url(raw: str) -> str:
    # 1. Strip explicit query string in the literal: `/foo?x=1` → `/foo`.
    head = raw.split("?", 1)[0]
    # 2. Strip a trailing `${var}` only if NOT preceded by `/` — these are
    #    built-up query suffixes like the `${q}` in `/renewals${q}` (q = "?…").
    #    A path param like `/contacts/${id}` IS preceded by `/`, so we keep it.
    head = re.sub(r"(?<!/)\$\{[^}]+\}$", "", head)
    # 3. `${variable}` → `{variable}` so frontend templates align with FastAPI path params.
    return re.sub(r"\$\{([^}]+)\}", lambda m: "{" + m.group(1) + "}", head)


def _client_paths(api_ts: Path) -> list[tuple[int, str]]:
    text = api_ts.read_text(encoding="utf-8")
    found: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for raw in _APIFETCH_RE.findall(line):
            found.append((line_no, _normalize_client_url(raw)))
    return found


def _path_param_match(client: str, backend_paths: set[str]) -> bool:
    """Return True if client path matches a backend path with the same shape.

    FastAPI uses {orgnr}; the frontend may interpolate any variable name. So we
    compare path components allowing any single {placeholder} segment to match
    any other {placeholder}.
    """
    if client in backend_paths:
        return True
    client_parts = client.split("/")
    for backend in backend_paths:
        bparts = backend.split("/")
        if len(bparts) != len(client_parts):
            continue
        if all(
            (cp == bp) or (cp.startswith("{") and bp.startswith("{"))
            for cp, bp in zip(client_parts, bparts)
        ):
            return True
    return False


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    api_ts = repo_root / "frontend" / "src" / "lib" / "api.ts"
    if not api_ts.exists():
        print(f"::error::{api_ts} not found", file=sys.stderr)
        return 2

    backend = _load_backend_paths()
    print(f"Backend exposes {len(backend)} paths")

    dead: list[tuple[int, str]] = []
    for line_no, path in _client_paths(api_ts):
        if not _path_param_match(path, backend):
            dead.append((line_no, path))

    if not dead:
        print(f"OK: every apiFetch URL in {api_ts.name} resolves to a backend route.")
        return 0

    print(f"\nDead client URLs found in {api_ts}:")
    for line_no, path in dead:
        print(f"  L{line_no}: {path}")
    print("\nDelete the dead function or rename the backend route.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
