# Canary deployment activation (Phase 7 of application-hardening)

## What this is

`scripts/canary_watchdog.py` + the `Canary watchdog` step in
`.github/workflows/deploy.yml` together give prod a 5-minute observation
window where new revisions serve 10% of traffic while we watch for 5xx
spikes. If the new revision misbehaves, traffic is rolled back to 100%
old automatically. Right now the step is behind `CANARY_ENABLED=1` and
does nothing — this runbook activates it.

## Why dormant by default

Two reasons the code ships OFF until a human deliberately enables it:

1. **One-time Azure state change**: the container app must switch from
   `revision-mode: single` to `revision-mode: multiple` for
   traffic-splitting to work. That's a destructive-ish operation (it
   stops Azure from auto-deactivating old revisions) and wants a human
   at the keyboard the first time.
2. **Rollback validation**: the code path that matters most — the actual
   auto-rollback on a bad deploy — cannot be tested safely without a
   deliberate bad deploy on prod. Landing the feature as dormant means
   the activation step is also the first time you observe the watchdog
   in action; that's the moment to schedule for a maintenance window.

## One-time activation checklist

### 1. Flip `revision-mode` to `multiple`

```bash
az containerapp revision set-mode \
  --name ca-api-prod \
  --resource-group rg-broker-accelerator-prod \
  --mode multiple
```

After this, every deploy creates a new revision without deactivating
the old one. The `deploy.yml` canary step will split traffic 90/10 on
the next deploy.

### 2. Set GitHub Actions secrets

- `CANARY_ENABLED` = `1`
- `APPLICATIONINSIGHTS_APP_ID` = the AI application ID (not the
  connection string) — found in the Azure portal under the App Insights
  resource → "API Access". Needed by the watchdog's KQL query.
- `APPLICATIONINSIGHTS_API_KEY` = create via App Insights → API Access
  → "Create API key" with "Read telemetry" permission.

The deploy step is gated on `env.CANARY_ENABLED == '1' && env == 'prod'`
so staging deploys are unaffected.

### 3. First deploy under canary

- Make sure the next deploy lands during working hours. The watchdog's
  5-minute observation window is a real wall-clock wait — deploys take
  ~5 min longer when canary is active.
- Watch the workflow logs for `canary: revision=...` lines. Rate should
  stay at 0% for a healthy deploy.
- If the watchdog rolls back, the step exits non-zero; the `Wait for API
  revision to become Healthy` step already passed, so the rollback is
  purely on 5xx rate from real traffic. Check App Insights for the new
  revision's request logs to diagnose.

### 4. Tune the thresholds (optional)

Defaults in `scripts/canary_watchdog.py`:
- `--window-seconds 300` — 5 min observation
- `--threshold 0.02` — rollback if 5xx rate > 2%

For a chatty backend (1000+ req/min) 2% is already noisy; you may want
`--threshold 0.05`. For a quiet backend (broker app has ~10 req/min in
prod), 1% could be a single random 502 on a dependency call —
consider raising the threshold or lengthening the window.

Override via env vars or edit the `python scripts/canary_watchdog.py`
invocation in `deploy.yml`.

## Rollback procedure (if canary misses)

If the watchdog promotes a bad revision (e.g. the bug only shows up at
>10% traffic, or App Insights had gaps during the window), manually roll
back:

```bash
PREV=$(az containerapp revision list --name ca-api-prod \
  --resource-group rg-broker-accelerator-prod \
  --query "[?properties.active] | [1].name" -o tsv)
az containerapp ingress traffic set \
  --name ca-api-prod --resource-group rg-broker-accelerator-prod \
  --revision-weight "$PREV=100"
```

Then open a retrospective issue: why did the watchdog not catch it?
Likely candidates: threshold too lenient, window too short, bug only
visible under sustained load.

## Disabling temporarily

If the watchdog is false-positive rolling back good deploys (e.g.
because a legit 500-heavy endpoint exists), set `CANARY_ENABLED` to
anything other than `1` in the workflow secrets. The step becomes a
no-op on the next deploy while you investigate.
