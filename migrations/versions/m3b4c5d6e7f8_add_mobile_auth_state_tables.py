"""add mobile auth state tables

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-03-19 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm3b4c5d6e7f8'
down_revision = 'l2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mobile_revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('token_type', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_mobile_revoked_tokens_expires_at'), 'mobile_revoked_tokens', ['expires_at'], unique=False)
    op.create_index(op.f('ix_mobile_revoked_tokens_token_hash'), 'mobile_revoked_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_mobile_revoked_tokens_token_type'), 'mobile_revoked_tokens', ['token_type'], unique=False)

    op.create_table(
        'mobile_rate_limit_buckets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bucket_key', sa.String(length=255), nullable=False),
        sa.Column('action_name', sa.String(length=50), nullable=False),
        sa.Column('scope_key', sa.String(length=255), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('window_ends_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bucket_key')
    )
    op.create_index(op.f('ix_mobile_rate_limit_buckets_action_name'), 'mobile_rate_limit_buckets', ['action_name'], unique=False)
    op.create_index(op.f('ix_mobile_rate_limit_buckets_bucket_key'), 'mobile_rate_limit_buckets', ['bucket_key'], unique=True)
    op.create_index(op.f('ix_mobile_rate_limit_buckets_scope_key'), 'mobile_rate_limit_buckets', ['scope_key'], unique=False)
    op.create_index(op.f('ix_mobile_rate_limit_buckets_window_ends_at'), 'mobile_rate_limit_buckets', ['window_ends_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_mobile_rate_limit_buckets_window_ends_at'), table_name='mobile_rate_limit_buckets')
    op.drop_index(op.f('ix_mobile_rate_limit_buckets_scope_key'), table_name='mobile_rate_limit_buckets')
    op.drop_index(op.f('ix_mobile_rate_limit_buckets_bucket_key'), table_name='mobile_rate_limit_buckets')
    op.drop_index(op.f('ix_mobile_rate_limit_buckets_action_name'), table_name='mobile_rate_limit_buckets')
    op.drop_table('mobile_rate_limit_buckets')

    op.drop_index(op.f('ix_mobile_revoked_tokens_token_type'), table_name='mobile_revoked_tokens')
    op.drop_index(op.f('ix_mobile_revoked_tokens_token_hash'), table_name='mobile_revoked_tokens')
    op.drop_index(op.f('ix_mobile_revoked_tokens_expires_at'), table_name='mobile_revoked_tokens')
    op.drop_table('mobile_revoked_tokens')
