"""add mobile device tokens

Revision ID: w3l4m5n6o7p8
Revises: v2k3l4m5n6o7
Create Date: 2026-04-29 10:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "w3l4m5n6o7p8"
down_revision = "v2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mobile_device_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("device_name", sa.String(length=120), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_device_tokens_user_id", "mobile_device_tokens", ["user_id"], unique=False)
    op.create_index("ix_mobile_device_tokens_token", "mobile_device_tokens", ["token"], unique=True)
    op.create_index("ix_mobile_device_tokens_is_active", "mobile_device_tokens", ["is_active"], unique=False)
    op.create_index("ix_mobile_device_tokens_last_seen_at", "mobile_device_tokens", ["last_seen_at"], unique=False)


def downgrade():
    op.drop_index("ix_mobile_device_tokens_last_seen_at", table_name="mobile_device_tokens")
    op.drop_index("ix_mobile_device_tokens_is_active", table_name="mobile_device_tokens")
    op.drop_index("ix_mobile_device_tokens_token", table_name="mobile_device_tokens")
    op.drop_index("ix_mobile_device_tokens_user_id", table_name="mobile_device_tokens")
    op.drop_table("mobile_device_tokens")
