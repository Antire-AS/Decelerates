"""Historical Altman Z''-Score series — one point per year stored in company_history.

The point-in-time Z'' panel lives on the Overview tab. For a multi-year view
(is this company trending toward distress or recovering?) we re-run the same
computation against each historical year and hand the frontend a ready-to-plot
series. Years where the extraction lacks one of the four Altman inputs are
silently omitted — a half-populated point would be misleading, not helpful.
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from api.db import CompanyHistory
from api.risk import compute_altman_z_score


def get_altman_z_history(db: Session, orgnr: str) -> List[Dict[str, Any]]:
    """Compute Altman Z''-Score for every year in company_history for this org.

    Reads the row's ``raw`` JSON blob because that contains Gemini's full
    extraction with the Norwegian keys Altman needs
    (``sum_omloepsmidler``, ``sum_opptjent_egenkapital``, ``driftsresultat``).
    The flat columns on CompanyHistory are a projection for the UI and lack
    the current-assets / retained-earnings split.
    """
    rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        regn = row.raw or {}
        altman = compute_altman_z_score(regn)
        if altman is None:
            continue
        out.append(
            {
                "year": row.year,
                "z_score": altman["z_score"],
                "zone": altman["zone"],
                "score_20": altman["score_20"],
            }
        )
    return out
