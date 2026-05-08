"""add withdrawal pin hash to users

Revision ID: c9a1d2e3f4b5
Revises: fa28f14d5f8c
Create Date: 2026-05-08 09:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9a1d2e3f4b5"
down_revision = "fa28f14d5f8c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("withdrawal_pin_hash", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("users", "withdrawal_pin_hash")
