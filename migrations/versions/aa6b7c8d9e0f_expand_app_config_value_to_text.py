"""expand app_config value to text

Revision ID: aa6b7c8d9e0f
Revises: e1f2a3b4c5d7
Create Date: 2026-05-09 16:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aa6b7c8d9e0f"
down_revision = "e1f2a3b4c5d7"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "app_configs",
        "value",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "app_configs",
        "value",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
