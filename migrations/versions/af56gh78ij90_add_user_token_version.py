"""add user token version

Revision ID: af56gh78ij90
Revises: ae45fg67hi89
Create Date: 2026-06-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "af56gh78ij90"
down_revision = "ae45fg67hi89"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("users", "token_version")
