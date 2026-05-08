"""add pin attempt tracking for withdrawals

Revision ID: d7e8f9a0b1c2
Revises: c9a1d2e3f4b5
Create Date: 2026-05-08 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7e8f9a0b1c2"
down_revision = "c9a1d2e3f4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("withdrawal_pin_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("withdrawal_pin_locked_until", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "student_savings_accounts",
        sa.Column("pin_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "student_savings_accounts",
        sa.Column("pin_locked_until", sa.DateTime(), nullable=True),
    )
    op.alter_column("users", "withdrawal_pin_failed_attempts", server_default=None)
    op.alter_column("student_savings_accounts", "pin_failed_attempts", server_default=None)


def downgrade():
    op.drop_column("student_savings_accounts", "pin_locked_until")
    op.drop_column("student_savings_accounts", "pin_failed_attempts")
    op.drop_column("users", "withdrawal_pin_locked_until")
    op.drop_column("users", "withdrawal_pin_failed_attempts")
