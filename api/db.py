"""Backward-compatible shim — all models now live in api/models/.

This file re-exports everything so existing `from api.db import X`
statements continue to work without modification. New code should
import from api.models directly.
"""

from api.models._base import Base, engine, SessionLocal, EMBEDDING_DIM, DATABASE_URL  # noqa: F401
from api.models.broker import *  # noqa: F401,F403
from api.models.company import *  # noqa: F401,F403
from api.models.crm import *  # noqa: F401,F403
from api.models.portfolio import *  # noqa: F401,F403
from api.models.pipeline import *  # noqa: F401,F403
from api.models.insurance import *  # noqa: F401,F403
from api.models.tender import *  # noqa: F401,F403
from api.models.coverage import *  # noqa: F401,F403
from api.models.compliance import *  # noqa: F401,F403
from api.models.system import *  # noqa: F401,F403
from api.models.news import *  # noqa: F401,F403
from api.models.inbound_email import *  # noqa: F401,F403


def init_db():
    """Delegate to the canonical init_db in _base.py."""
    from api.models._base import init_db as _init_db

    _init_db()
