"""Schemas package — backward-compatible re-exports.

All schemas are split into domain files. This __init__.py re-exports
everything so existing `from api.schemas import X` continues to work.
"""
from api.schemas.common import *       # noqa: F401,F403
from api.schemas.common import _BrokerNoteBody  # noqa: F401 — underscore-prefixed, not exported by *
from api.schemas.broker import *       # noqa: F401,F403
from api.schemas.company import *      # noqa: F401,F403
from api.schemas.crm import *          # noqa: F401,F403
from api.schemas.portfolio import *    # noqa: F401,F403
from api.schemas.insurance import *    # noqa: F401,F403
from api.schemas.commission import *   # noqa: F401,F403
from api.schemas.documents import *    # noqa: F401,F403
from api.schemas.pipeline import *     # noqa: F401,F403
from api.schemas.notifications import *  # noqa: F401,F403
from api.schemas.tender import *       # noqa: F401,F403
from api.schemas.risk import *         # noqa: F401,F403
from api.schemas.knowledge import *    # noqa: F401,F403
from api.schemas.audit import *        # noqa: F401,F403
from api.schemas.saved_search import * # noqa: F401,F403
from api.schemas.email import *        # noqa: F401,F403
from api.schemas.consent import *      # noqa: F401,F403
