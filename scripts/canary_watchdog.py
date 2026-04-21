"""Canary deployment watchdog — Phase 7 of application-hardening plan.

Watches a freshly-deployed Azure Container Apps revision for the first N
minutes after it takes 10% of traffic. Queries ApplicationInsights for
the 5xx rate on requests routed to the new revision. If the rate exceeds
the threshold, swaps traffic back to 100% on the previous revision.
Otherwise promotes the new revision to 100% traffic.

Deliberately DORMANT until `CANARY_ENABLED=1` is set on the deploy
workflow — running `az containerapp revision set-mode --mode multiple`
is a one-time destructive-adjacent operation that must be done
interactively, not via an auto-merged PR. See
docs/runbooks/canary-activation.md for the activation checklist.

Invocation (from deploy.yml):
    python scripts/canary_watchdog.py \\
        --app ca-api-prod \\
        --resource-group rg-broker-accelerator-prod \\
        --new-revision <latestRevisionName> \\
        --previous-revision <prior-latest-revision> \\
        --window-seconds 300 \\
        --threshold 0.02

Requires:
- `az` CLI authenticated via the workflow's OIDC federated identity
- `APPLICATIONINSIGHTS_APP_ID` + `APPLICATIONINSIGHTS_API_KEY` env vars
  (used to query the Log Analytics workspace via the REST API)

Exits 0 on successful promotion, non-zero on rollback (so the workflow
step goes red and a human gets paged).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

try:
    import requests
except ImportError:  # pragma: no cover — the deploy image pins requests
    sys.stderr.write("requests is required for canary_watchdog.py\n")
    raise


_THRESHOLD_DEFAULT = 0.02  # 2% 5xx rate = rollback
_WINDOW_SECONDS_DEFAULT = 300  # observe for 5 min before promoting
_POLL_SECONDS = 30


@dataclass(frozen=True)
class WatchdogArgs:
    app: str
    resource_group: str
    new_revision: str
    previous_revision: str
    window_seconds: int
    threshold: float
    ai_app_id: Optional[str]
    ai_api_key: Optional[str]


def parse_args(argv: Optional[list[str]] = None) -> WatchdogArgs:
    p = argparse.ArgumentParser(description="Canary traffic watchdog")
    p.add_argument("--app", required=True, help="Container App name")
    p.add_argument("--resource-group", required=True)
    p.add_argument("--new-revision", required=True)
    p.add_argument("--previous-revision", required=True)
    p.add_argument(
        "--window-seconds",
        type=int,
        default=_WINDOW_SECONDS_DEFAULT,
        help="How long to observe the new revision before promoting (default 300)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=_THRESHOLD_DEFAULT,
        help="5xx rate that triggers rollback (default 0.02 = 2%%)",
    )
    ns = p.parse_args(argv)
    return WatchdogArgs(
        app=ns.app,
        resource_group=ns.resource_group,
        new_revision=ns.new_revision,
        previous_revision=ns.previous_revision,
        window_seconds=ns.window_seconds,
        threshold=ns.threshold,
        ai_app_id=os.getenv("APPLICATIONINSIGHTS_APP_ID"),
        ai_api_key=os.getenv("APPLICATIONINSIGHTS_API_KEY"),
    )


def compute_failure_rate(total_requests: int, failed_requests: int) -> float:
    """Pure function — easy to unit-test.

    Returns 0.0 when there are no requests yet (cold revision) so we
    never rollback purely from "no traffic seen yet" — the window is
    long enough that real failures accumulate even at low QPS.
    """
    if total_requests <= 0:
        return 0.0
    return failed_requests / total_requests


def query_5xx_rate(args: WatchdogArgs) -> float:
    """Query App Insights for the 5xx rate on requests tagged with
    cloud_RoleInstance == <new_revision>. Returns 0.0 if App Insights
    isn't configured (watchdog passes the window — the deploy is still
    subject to the Healthy probe on the way in)."""
    if not args.ai_app_id or not args.ai_api_key:
        sys.stderr.write(
            "APPLICATIONINSIGHTS_APP_ID / _API_KEY not set — skipping KQL query\n"
        )
        return 0.0
    kql = (
        "requests | where cloud_RoleInstance == '"
        + args.new_revision.replace("'", "")
        + "' | summarize total = count(), failed = countif(resultCode startswith '5')"
    )
    url = (
        f"https://api.applicationinsights.io/v1/apps/{args.ai_app_id}/query"
        f"?query={quote(kql)}"
    )
    resp = requests.get(
        url,
        headers={"x-api-key": args.ai_api_key},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    rows = (body.get("tables") or [{}])[0].get("rows") or []
    if not rows:
        return 0.0
    total, failed = int(rows[0][0] or 0), int(rows[0][1] or 0)
    return compute_failure_rate(total, failed)


def _az(*cmd: str) -> None:
    """Run an `az` command with stderr passthrough, exit non-zero on failure."""
    subprocess.run(["az", *cmd], check=True)


def rollback_to_previous(args: WatchdogArgs, reason: str) -> None:
    sys.stderr.write(f"::error::Canary rollback triggered: {reason}\n")
    _az(
        "containerapp",
        "ingress",
        "traffic",
        "set",
        "--name",
        args.app,
        "--resource-group",
        args.resource_group,
        "--revision-weight",
        f"{args.previous_revision}=100",
        f"{args.new_revision}=0",
    )
    sys.exit(1)


def promote_new_revision(args: WatchdogArgs) -> None:
    _az(
        "containerapp",
        "ingress",
        "traffic",
        "set",
        "--name",
        args.app,
        "--resource-group",
        args.resource_group,
        "--revision-weight",
        f"{args.new_revision}=100",
        f"{args.previous_revision}=0",
    )
    print(f"Canary promoted: {args.new_revision} now serves 100% traffic.")


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    deadline = time.time() + args.window_seconds
    while time.time() < deadline:
        rate = query_5xx_rate(args)
        remaining = int(deadline - time.time())
        print(
            f"canary: revision={args.new_revision} 5xx_rate={rate:.2%} "
            f"window_remaining={remaining}s",
        )
        if rate > args.threshold:
            rollback_to_previous(
                args,
                f"5xx rate {rate:.2%} exceeded {args.threshold:.2%}",
            )
        time.sleep(_POLL_SECONDS)
    promote_new_revision(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
