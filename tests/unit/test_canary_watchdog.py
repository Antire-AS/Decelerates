"""Unit tests for scripts/canary_watchdog.py — pure-function bits."""

import importlib.util
import sys
from pathlib import Path


# The watchdog lives under scripts/ which isn't a package. Load via
# importlib so pytest can still test it without adding scripts to the
# import path. Python 3.14's dataclass resolves module bindings through
# sys.modules during class construction, so we MUST register the module
# there before exec_module — otherwise `@dataclass(frozen=True)` blows
# up with "NoneType has no attribute __dict__".
_WATCHDOG_PATH = Path(__file__).resolve().parents[2] / "scripts" / "canary_watchdog.py"
_spec = importlib.util.spec_from_file_location("_canary_watchdog", _WATCHDOG_PATH)
_wd = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["_canary_watchdog"] = _wd
_spec.loader.exec_module(_wd)  # type: ignore[union-attr]


class TestComputeFailureRate:
    def test_zero_requests_returns_zero(self):
        # A cold revision with no traffic yet must not be flagged as failed —
        # we'd rollback every new deploy before the first request landed.
        assert _wd.compute_failure_rate(0, 0) == 0.0

    def test_zero_failed_returns_zero(self):
        assert _wd.compute_failure_rate(100, 0) == 0.0

    def test_all_failed_returns_one(self):
        assert _wd.compute_failure_rate(50, 50) == 1.0

    def test_half_failed_returns_half(self):
        assert _wd.compute_failure_rate(10, 5) == 0.5

    def test_single_failure_under_typical_threshold(self):
        # 1/100 = 1%, below the 2% default — should NOT trigger rollback.
        assert _wd.compute_failure_rate(100, 1) == 0.01

    def test_negative_total_clamps_to_zero(self):
        # Defensive: a KQL misparse that returns -1 must not divide-by-zero
        # or flip the rate negative.
        assert _wd.compute_failure_rate(-5, 3) == 0.0


class TestParseArgs:
    def test_required_args_present(self):
        args = _wd.parse_args(
            [
                "--app",
                "ca-api-prod",
                "--resource-group",
                "rg-broker-accelerator-prod",
                "--new-revision",
                "ca-api-prod--abc123",
                "--previous-revision",
                "ca-api-prod--xyz999",
            ]
        )
        assert args.app == "ca-api-prod"
        assert args.new_revision == "ca-api-prod--abc123"
        assert args.previous_revision == "ca-api-prod--xyz999"

    def test_defaults_applied(self):
        args = _wd.parse_args(
            [
                "--app",
                "x",
                "--resource-group",
                "rg",
                "--new-revision",
                "new",
                "--previous-revision",
                "prev",
            ]
        )
        # Defaults locked in by the unit test so an accidental change is
        # visible. 300s + 2% match the plan document.
        assert args.window_seconds == 300
        assert args.threshold == 0.02

    def test_threshold_override(self):
        args = _wd.parse_args(
            [
                "--app",
                "x",
                "--resource-group",
                "rg",
                "--new-revision",
                "new",
                "--previous-revision",
                "prev",
                "--threshold",
                "0.05",
            ]
        )
        assert args.threshold == 0.05


class TestQuery5xxRateFallback:
    def test_returns_zero_when_app_insights_not_configured(self, monkeypatch):
        """If APPLICATIONINSIGHTS_APP_ID / _API_KEY are unset, the watchdog
        must skip the KQL query and return 0.0 — the Healthy probe in
        deploy.yml is still the outer gate. Rolling back just because we
        can't read telemetry would be worse than proceeding."""
        monkeypatch.delenv("APPLICATIONINSIGHTS_APP_ID", raising=False)
        monkeypatch.delenv("APPLICATIONINSIGHTS_API_KEY", raising=False)
        args = _wd.parse_args(
            [
                "--app",
                "x",
                "--resource-group",
                "rg",
                "--new-revision",
                "new",
                "--previous-revision",
                "prev",
            ]
        )
        assert _wd.query_5xx_rate(args) == 0.0
