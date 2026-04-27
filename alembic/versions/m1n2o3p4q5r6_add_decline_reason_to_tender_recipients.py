"""add decline_reason + decline_note to tender_recipients

Revision ID: m1n2o3p4q5r6
Revises: d1e2f3g4h5i6
Create Date: 2026-04-25 14:35:00.000000

Today the recipient status enum has `declined` but no field for *why*.
The user explicitly asked: "Forsikringsselskaper kan også avslå —
kapasitet, dårlig anbud, høy risiko." Capturing this lets the broker
see at a glance which insurers said no and why, and lets us aggregate
"capacity"-driven declines in portfolio reporting.

Both columns are nullable so existing `declined` rows stay valid; the
service layer fills them on new declines.

`decline_reason` is a free string (not a PG enum) because Postgres
enum migrations are painful and the four-value vocabulary may grow
(e.g. "duplicate_existing_policy", "deadline_too_short"). The model
layer constrains the values via a Python Enum.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "m1n2o3p4q5r6"
down_revision: str | None = "d1e2f3g4h5i6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tender_recipients",
        sa.Column("decline_reason", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "tender_recipients",
        sa.Column("decline_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tender_recipients", "decline_note")
    op.drop_column("tender_recipients", "decline_reason")
