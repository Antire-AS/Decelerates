/**
 * Client-side Altman Z''-Score recompute for the scenario slider.
 *
 * Mirrors api/risk.py::compute_altman_z_score. Kept tiny on purpose so
 * drift between Python and TS is obvious — the slider's re-rendered Z''
 * must match what the backend returned on load.
 *
 * Reference formula (Altman 2000, non-manufacturing private firms):
 *   Z'' = 6.56·x1 + 3.26·x2 + 6.72·x3 + 1.05·x4
 *
 * Zone thresholds:
 *   z > 2.60        → safe
 *   1.10 ≤ z ≤ 2.60 → grey
 *   z < 1.10        → distress
 *
 * PINNING FIXTURES — mirrored in tests/unit/test_altman_z.py under
 * `SCENARIO_PARITY_FIXTURES`. If you change the coefficients, zone cutoffs,
 * or score_20 mapping here, update BOTH this file AND the Python test
 * so the parity check keeps failing loudly on drift.
 *
 *   Fixture A: x1=0.30 x2=0.35 x3=0.15 x4=1.50
 *     → z = 6.56·0.30 + 3.26·0.35 + 6.72·0.15 + 1.05·1.50
 *       = 1.968 + 1.141 + 1.008 + 1.575 = 5.692
 *     → zone=safe, score_20=0
 *
 *   Fixture B: x1=0.10 x2=0.15 x3=0.05 x4=0.40
 *     → z = 0.656 + 0.489 + 0.336 + 0.420 = 1.901
 *     → zone=grey, score_20=10
 *
 *   Fixture C: x1=-0.10 x2=-0.20 x3=-0.05 x4=0.05
 *     → z = -0.656 - 0.652 - 0.336 + 0.0525 = -1.5915
 *     → zone=distress, score_20=20
 */

export type AltmanZone = "safe" | "grey" | "distress";

export interface AltmanComponents {
  working_capital_ratio: number; // x1
  retained_earnings_ratio: number; // x2
  ebit_ratio: number; // x3
  equity_to_liab_ratio: number; // x4
}

export interface AltmanRecomputed {
  z_score: number;
  zone: AltmanZone;
  score_20: number;
}

const Z_SAFE = 3.5;
const Z_GREY_TOP = 2.6;
const Z_GREY_MID = 1.85;
const Z_DISTRESS_TOP = 1.1;
const Z_CRITICAL = 0.0;

export function computeZScore(c: AltmanComponents): number {
  return (
    6.56 * c.working_capital_ratio +
    3.26 * c.retained_earnings_ratio +
    6.72 * c.ebit_ratio +
    1.05 * c.equity_to_liab_ratio
  );
}

export function zoneFor(z: number): AltmanZone {
  if (z > Z_GREY_TOP) return "safe";
  if (z >= Z_DISTRESS_TOP) return "grey";
  return "distress";
}

/** Piecewise linear 0-20 mapping — mirrors api.risk._map_z_to_risk_score. */
export function scoreFor(z: number): number {
  if (z >= Z_SAFE) return 0;
  if (z >= Z_GREY_TOP) return Math.round((5 * (Z_SAFE - z)) / (Z_SAFE - Z_GREY_TOP));
  if (z >= Z_GREY_MID)
    return Math.round(5 + (5 * (Z_GREY_TOP - z)) / (Z_GREY_TOP - Z_GREY_MID));
  if (z >= Z_DISTRESS_TOP)
    return Math.round(10 + (5 * (Z_GREY_MID - z)) / (Z_GREY_MID - Z_DISTRESS_TOP));
  if (z >= Z_CRITICAL)
    return Math.round(
      15 + (5 * (Z_DISTRESS_TOP - z)) / (Z_DISTRESS_TOP - Z_CRITICAL),
    );
  return 20;
}

export function recompute(c: AltmanComponents): AltmanRecomputed {
  const z = computeZScore(c);
  return {
    z_score: Math.round(z * 100) / 100,
    zone: zoneFor(z),
    score_20: scoreFor(z),
  };
}

/**
 * Apply broker scenario levers to baseline Altman components.
 *
 * EBIT delta scales x3 directly (EBIT/TA) — a +20% EBIT shock becomes
 * x3 · 1.20 because total assets stay the same.
 *
 * Equity delta scales x4 (equity/liab). We also scale x1 by a fraction
 * of the delta to reflect that equity injection often ends up as
 * current assets (reducing short-term debt or padding working capital).
 * The weight 0.3 is deliberately coarse — the slider is a conversation
 * tool, not a DCF model.
 */
const EQUITY_TO_WC_COUPLING = 0.3;

export function applyScenario(
  base: AltmanComponents,
  ebitDelta: number,
  equityDelta: number,
): AltmanComponents {
  return {
    working_capital_ratio:
      base.working_capital_ratio * (1 + equityDelta * EQUITY_TO_WC_COUPLING),
    retained_earnings_ratio: base.retained_earnings_ratio,
    ebit_ratio: base.ebit_ratio * (1 + ebitDelta),
    equity_to_liab_ratio: base.equity_to_liab_ratio * (1 + equityDelta),
  };
}
