"""add mobile refresh tokens

Revision ID: bg67hi89jk01
Revises: af56gh78ij90
Create Date: 2026-07-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "bg67hi89jk01"
down_revision = "af56gh78ij90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mobile_refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_mobile_refresh_tokens_expires_at",
        "mobile_refresh_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_family_id",
        "mobile_refresh_tokens",
        ["family_id"],
        unique=False,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_jti",
        "mobile_refresh_tokens",
        ["jti"],
        unique=True,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_status",
        "mobile_refresh_tokens",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_tenant_id",
        "mobile_refresh_tokens",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_token_hash",
        "mobile_refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_user_id",
        "mobile_refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_mobile_refresh_tokens_user_tenant_status",
        "mobile_refresh_tokens",
        ["user_id", "tenant_id", "status"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_mobile_refresh_tokens_user_tenant_status", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_user_id", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_token_hash", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_tenant_id", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_status", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_jti", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_family_id", table_name="mobile_refresh_tokens")
    op.drop_index("ix_mobile_refresh_tokens_expires_at", table_name="mobile_refresh_tokens")
    op.drop_table("mobile_refresh_tokens")
