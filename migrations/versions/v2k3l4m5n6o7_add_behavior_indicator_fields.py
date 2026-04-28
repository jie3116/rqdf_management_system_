"""add behavior indicator fields

Revision ID: v2k3l4m5n6o7
Revises: u1j2k3l4m5n6
Create Date: 2026-04-28 13:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "v2k3l4m5n6o7"
down_revision = "u1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("behavior_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("class_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("indicator_key", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("indicator_group", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("is_yes", sa.Boolean(), nullable=True))
        batch_op.create_index("ix_behavior_reports_class_id", ["class_id"], unique=False)
        batch_op.create_index("ix_behavior_reports_indicator_key", ["indicator_key"], unique=False)
        batch_op.create_foreign_key(
            "fk_behavior_reports_class_id",
            "class_rooms",
            ["class_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("behavior_reports", schema=None) as batch_op:
        batch_op.drop_constraint("fk_behavior_reports_class_id", type_="foreignkey")
        batch_op.drop_index("ix_behavior_reports_indicator_key")
        batch_op.drop_index("ix_behavior_reports_class_id")
        batch_op.drop_column("is_yes")
        batch_op.drop_column("indicator_group")
        batch_op.drop_column("indicator_key")
        batch_op.drop_column("class_id")
