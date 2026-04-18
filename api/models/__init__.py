"""Models package — domain-organized SQLAlchemy models.

All models are re-exported here so `from api.models import Company` works.
"""

from api.models._base import Base, engine, SessionLocal, EMBEDDING_DIM, init_db  # noqa: F401
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
