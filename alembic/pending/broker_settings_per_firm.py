"""Per-firm BrokerSettings — gated migration.

DO NOT MOVE THIS FILE INTO alembic/versions/ UNTIL the business is onboarding a
2nd BrokerFirm. Until then, BrokerSettings stays as a singleton (id=1) and the
409 fence in api/routers/admin_router.py::_resolve_single_firm_id keeps the
cron jobs single-firm-safe.

See alembic/pending/README.md for the activation procedure and plan §🟡 #8 for
the original context.

═══════════════════════════════════════════════════════════════════════════════
COMPANION CODE CHANGES — apply at the same time as this migration
═══════════════════════════════════════════════════════════════════════════════

1. api/db.py — replace BrokerSettings with the per-firm shape:

       class BrokerSettings(Base):
           __tablename__ = "broker_settings"

           id            = Column(Integer, primary_key=True, autoincrement=True)
           firm_id       = Column(Integer, ForeignKey("broker_firms.id", ondelete="CASCADE"),
                                  nullable=False, unique=True, index=True)
           firm_name     = Column(String, nullable=False, default="")
           orgnr         = Column(String(9))
           address       = Column(String)
           contact_name  = Column(String)
           contact_email = Column(String)
           contact_phone = Column(String)
           updated_at    = Column(String)

2. api/services/broker.py — both methods take firm_id:

       def get_settings(self, firm_id: int) -> Optional[BrokerSettings]:
           return self.db.query(BrokerSettings).filter(BrokerSettings.firm_id == firm_id).first()

       def save_settings(self, firm_id: int, body: BrokerSettingsIn) -> Dict[str, Any]:
           row = self.db.query(BrokerSettings).filter(BrokerSettings.firm_id == firm_id).first()
           # … rest unchanged, but pass firm_id when constructing a new row …

3. api/routers/broker.py — inject current_user and pass firm_id:

       from api.auth import get_current_user, CurrentUser

       @router.get("/broker/settings")
       def get_broker_settings_endpoint(
           svc: BrokerService = Depends(_get_broker_service),
           user: CurrentUser = Depends(get_current_user),
       ) -> dict:
           row = svc.get_settings(user.firm_id)
           ...

       @router.post("/broker/settings")
       def save_broker_settings_endpoint(
           body: BrokerSettingsIn,
           svc: BrokerService = Depends(_get_broker_service),
           user: CurrentUser = Depends(get_current_user),
       ):
           return svc.save_settings(user.firm_id, body)

4. api/routers/admin_router.py::_resolve_single_firm_id — DELETE the 409 fence
   and have the helper return current_user.firm_id instead. The cron entry-point
   functions (send_portfolio_digest, send_activity_reminders, etc.) take a
   `user: CurrentUser = Depends(get_current_user)` and pass user.firm_id to the
   resolver. The cron call sites (GitHub Actions workflows in
   .github/workflows/*-reminders.yml etc.) must pass a service-account JWT.

5. tests/unit/test_broker_service.py — update fixtures to set firm_id=1, and
   add a new test_broker_service_isolates_per_firm test that creates two
   BrokerSettings rows under different firm_ids and asserts they don't bleed.

═══════════════════════════════════════════════════════════════════════════════
"""
from alembic import op
import sqlalchemy as sa


# IMPORTANT: when activating, set down_revision to the current alembic head id
# (run `uv run alembic current` first). Leaving it as None makes alembic refuse
# to apply this migration in a pre-existing chain — by design.
revision = "broker_settings_per_firm"
down_revision = None  # ← REPLACE with current head when moving to versions/
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Refuse to run if no broker_firms exist — explicit failure beats a
    #    silent NULL backfill that would then trip the NOT NULL constraint.
    bind = op.get_bind()
    firm_count = bind.execute(sa.text("SELECT COUNT(*) FROM broker_firms")).scalar()
    if not firm_count:
        raise RuntimeError(
            "Cannot run broker_settings_per_firm migration: broker_firms is empty. "
            "Create at least one BrokerFirm row first (set BROKER_FIRM_NAME env "
            "var and restart api/main.py, or insert manually)."
        )

    # 2. Add firm_id as nullable so the backfill can populate it.
    op.add_column(
        "broker_settings",
        sa.Column("firm_id", sa.Integer(), nullable=True),
    )

    # 3. Backfill: existing singleton row(s) get the lowest firm_id.
    op.execute(
        "UPDATE broker_settings "
        "SET firm_id = (SELECT id FROM broker_firms ORDER BY id LIMIT 1) "
        "WHERE firm_id IS NULL"
    )

    # 4. Lock it down: NOT NULL + FK + unique-per-firm.
    op.alter_column("broker_settings", "firm_id", nullable=False)
    op.create_foreign_key(
        "fk_broker_settings_firm_id",
        "broker_settings",
        "broker_firms",
        ["firm_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_broker_settings_firm_id", "broker_settings", ["firm_id"]
    )
    op.create_index(
        "idx_broker_settings_firm_id", "broker_settings", ["firm_id"]
    )

    # 5. Drop the singleton id=1 default. The id column becomes a regular
    #    autoincrement primary key. The actual rows are addressed by firm_id.
    #    (Postgres SERIAL columns don't carry a default attached to the column
    #    in the same way SQLAlchemy emits one — this is a no-op on most setups
    #    but kept for completeness.)
    op.alter_column(
        "broker_settings",
        "id",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index("idx_broker_settings_firm_id", table_name="broker_settings")
    op.drop_constraint(
        "uq_broker_settings_firm_id", "broker_settings", type_="unique"
    )
    op.drop_constraint(
        "fk_broker_settings_firm_id", "broker_settings", type_="foreignkey"
    )
    op.drop_column("broker_settings", "firm_id")
