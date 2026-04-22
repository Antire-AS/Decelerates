"""Company news endpoints — on-demand fetch + classify."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import CompanyNewsOut, CompanyNewsRefreshOut
from api.services.news_service import list_company_news, refresh_company_news

router = APIRouter()


@router.get("/org/{orgnr}/news", response_model=CompanyNewsOut)
def read_company_news(
    orgnr: str,
    only_material: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict:
    """Return stored news articles for this company, newest first.
    `only_material=true` filters to underwriter-relevant events."""
    return {
        "orgnr": orgnr,
        "items": list_company_news(orgnr, db, only_material=only_material),
    }


@router.post("/org/{orgnr}/news/refresh", response_model=CompanyNewsRefreshOut)
def refresh_company_news_endpoint(orgnr: str, db: Session = Depends(get_db)) -> dict:
    """Query Serper /news for the company, classify each new hit via
    Foundry, upsert into company_news. Returns the count of newly
    stored articles (dedupe by URL)."""
    try:
        added = refresh_company_news(orgnr, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"orgnr": orgnr, "added": added}
