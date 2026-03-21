# Router package — each module holds a FastAPI APIRouter for a domain area.
# All routers are included in app.py via app.include_router().
from api.routers import (  # noqa: F401
    company,
    financials,
    risk_router,
    offers,
    documents,
    videos,
    knowledge,
    broker,
    sla,
    utils,
    portfolio_router,
)
