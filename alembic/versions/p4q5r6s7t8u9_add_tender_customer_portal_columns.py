"""add tender customer portal columns

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-04-28 10:50:00.000000

P4 from anbud-expansion roadmap (#251). User asked: "Megleren kan
analysere tilbudene også blir en tilbudsfremstilling for kunde sendt
til kunde for godkjenning. Også kontrakter basert på tilbudet."

Lets the broker generate a customer-facing URL after running the AI
analysis. The customer opens it, reviews the comparison, and approves
or rejects with one click. Approve kicks off the existing DocuSeal
e-sign flow (already webhook-wired via `mark_contract_signed_by_session`
on PR #234).

Columns on `tenders`:
- customer_access_token: opaque 64-char token, unique, nullable. NULL
  until the broker generates it. Same shape as
  TenderRecipient.access_token but on the customer side.
- customer_email: who the broker is sending the offer to. NULL until
  generated.
- customer_approval_status: pending | approved | rejected. NULL until
  the customer responds. Free-string column (not PG enum) so we can
  grow the vocabulary without an enum migration.
- customer_approval_at: when they responded.

Single-customer-per-tender by design — if a broker needs multi-stake-
holder approval later, we can split into a `tender_customer_approvals`
table without breaking this column set.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "p4q5r6s7t8u9"
down_revision: str | None = "o3p4q5r6s7t8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenders",
        sa.Column("customer_access_token", sa.String(length=64), nullable=True),
    )
    op.add_column("tenders", sa.Column("customer_email", sa.String(), nullable=True))
    op.add_column(
        "tenders",
        sa.Column("customer_approval_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "tenders",
        sa.Column("customer_approval_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Unique index on the token, partial so multiple NULLs coexist.
    op.create_index(
        "ix_tenders_customer_access_token_unique",
        "tenders",
        ["customer_access_token"],
        unique=True,
        postgresql_where=sa.text("customer_access_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_tenders_customer_access_token_unique", table_name="tenders")
    op.drop_column("tenders", "customer_approval_at")
    op.drop_column("tenders", "customer_approval_status")
    op.drop_column("tenders", "customer_email")
    op.drop_column("tenders", "customer_access_token")
