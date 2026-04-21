"""Static audit — every `db.query(<FirmScoped>)` in api/services/ or
api/routers/ must have `firm_id` in its surrounding function body.

A missed `.filter(Model.firm_id == firm_id)` is the highest-blast-radius
bug class in this repo: broker A sees broker B's tenders, offers, deals,
policies, etc. This test makes the audit mechanical + CI-gated.

Opt-out mechanism: if a helper is legitimately firm-scoped via its
parameters or pre-filtered subquery, add `# FIRM_ID_AUDIT: <reason>`
anywhere in the function body. The test skips functions containing that
marker.
"""

import ast
from pathlib import Path

from api.db import Base


def _firm_scoped_models() -> set[str]:
    """Returns the set of SQLAlchemy model class names that have a
    firm_id column — reflected from the live metadata so the audit stays
    current as new firm-scoped models land."""
    names: set[str] = set()
    for mapper in Base.registry.mappers:
        if "firm_id" in mapper.local_table.columns:
            names.add(mapper.class_.__name__)
    return names


def _function_queries_firm_scoped(func: ast.AST, firm_scoped: set[str]) -> bool:
    """True if this function body contains `db.query(<FirmScopedModel>)`
    or `self.db.query(...)`, where the first positional arg is a firm-
    scoped model."""
    for n in ast.walk(func):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        if n.func.attr != "query":
            continue
        if not n.args:
            continue
        arg = n.args[0]
        if isinstance(arg, ast.Name) and arg.id in firm_scoped:
            return True
    return False


def test_every_service_function_filters_firm_id() -> None:
    firm_scoped = _firm_scoped_models()
    assert firm_scoped, "Expected to find firm-scoped models via metadata"

    violations: list[str] = []
    roots = [Path("api/services"), Path("api/routers")]
    for root in roots:
        for path in root.rglob("*.py"):
            src = path.read_text()
            tree = ast.parse(src, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not _function_queries_firm_scoped(node, firm_scoped):
                    continue
                func_source = ast.get_source_segment(src, node) or ""
                # Allow firm_id references anywhere in the body, OR
                # opt-out marker for legitimate helpers scoped upstream.
                if "firm_id" in func_source or "FIRM_ID_AUDIT" in func_source:
                    continue
                violations.append(
                    f"{path}:{node.lineno}  {node.name}() queries a firm-scoped "
                    "model without referencing firm_id. "
                    "Add .filter(Model.firm_id == <scope>) OR "
                    "annotate with `# FIRM_ID_AUDIT: <reason>`."
                )

    assert not violations, "firm_id audit violations:\n  " + "\n  ".join(violations)
