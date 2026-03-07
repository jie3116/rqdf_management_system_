"""Finance amounts to integer rupiah

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-03-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l2a3b4c5d6e7'
down_revision = 'k1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Normalisasi data lama agar aman saat cast ke integer.
    conn.execute(sa.text("UPDATE fee_types SET amount = ROUND(COALESCE(amount, 0))"))
    conn.execute(sa.text("UPDATE invoices SET total_amount = ROUND(COALESCE(total_amount, 0))"))
    conn.execute(sa.text("UPDATE invoices SET paid_amount = ROUND(COALESCE(paid_amount, 0))"))
    conn.execute(sa.text("UPDATE transactions SET amount = ROUND(COALESCE(amount, 0))"))

    with op.batch_alter_table('fee_types', schema=None) as batch_op:
        batch_op.alter_column('amount', existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=True)

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.alter_column('total_amount', existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=True)
        batch_op.alter_column('paid_amount', existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=True)

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('amount', existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=True)


def downgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('amount', existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=True)

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.alter_column('paid_amount', existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=True)
        batch_op.alter_column('total_amount', existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=True)

    with op.batch_alter_table('fee_types', schema=None) as batch_op:
        batch_op.alter_column('amount', existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=True)
