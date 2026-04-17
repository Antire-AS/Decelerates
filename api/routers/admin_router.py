"""Admin router — backward-compatible shim.

All endpoints are now split into focused sub-routers:
  - admin_seed.py: reset, demo seed variants (6 endpoints)
  - debug.py: /debug/status diagnostic (1 endpoint)
  - dashboard.py: /dashboard summary (1 endpoint)
  - cron.py: email/notification cron triggers (6 endpoints)
"""

from fastapi import APIRouter
from api.routers.admin_seed import router as _seed
from api.routers.debug import router as _debug
from api.routers.dashboard import router as _dashboard
from api.routers.cron import router as _cron

router = APIRouter()
router.include_router(_seed)
router.include_router(_debug)
router.include_router(_dashboard)
router.include_router(_cron)
