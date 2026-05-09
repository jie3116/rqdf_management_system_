"""add online learning classroom features

Revision ID: e1f2a3b4c5d7
Revises: d7e8f9a0b1c2
Create Date: 2026-05-08 14:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d7"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "learning_materials",
        sa.Column("class_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "learning_materials",
        sa.Column("material_type", sa.String(length=20), nullable=False, server_default="LINK"),
    )
    op.add_column(
        "learning_materials",
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "learning_materials",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_learning_materials_class_id",
        "learning_materials",
        ["class_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_learning_materials_class_id_class_rooms",
        "learning_materials",
        "class_rooms",
        ["class_id"],
        ["id"],
    )
    op.alter_column("learning_materials", "material_type", server_default=None)
    op.alter_column("learning_materials", "is_published", server_default=None)

    op.create_table(
        "online_class_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("meeting_url", sa.String(length=255), nullable=False),
        sa.Column("meeting_provider", sa.String(length=30), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["class_id"], ["class_rooms.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_online_class_sessions_class_id", "online_class_sessions", ["class_id"], unique=False)
    op.create_index("ix_online_class_sessions_teacher_id", "online_class_sessions", ["teacher_id"], unique=False)
    op.create_index("ix_online_class_sessions_subject_id", "online_class_sessions", ["subject_id"], unique=False)
    op.create_index("ix_online_class_sessions_starts_at", "online_class_sessions", ["starts_at"], unique=False)
    op.create_index("ix_online_class_sessions_ends_at", "online_class_sessions", ["ends_at"], unique=False)
    op.create_index(
        "idx_online_class_session_class_time",
        "online_class_sessions",
        ["class_id", "starts_at"],
        unique=False,
    )

    op.create_table(
        "learning_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("resource_url", sa.String(length=255), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["class_id"], ["class_rooms.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_assignments_class_id", "learning_assignments", ["class_id"], unique=False)
    op.create_index("ix_learning_assignments_teacher_id", "learning_assignments", ["teacher_id"], unique=False)
    op.create_index("ix_learning_assignments_subject_id", "learning_assignments", ["subject_id"], unique=False)
    op.create_index("ix_learning_assignments_due_at", "learning_assignments", ["due_at"], unique=False)
    op.create_index(
        "idx_learning_assignment_class_due",
        "learning_assignments",
        ["class_id", "due_at"],
        unique=False,
    )

    op.create_table(
        "learning_assignment_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("submission_text", sa.Text(), nullable=True),
        sa.Column("submission_url", sa.String(length=255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("graded_at", sa.DateTime(), nullable=True),
        sa.Column("graded_by_teacher_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["learning_assignments.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["graded_by_teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_submission_student"),
    )
    op.create_index(
        "ix_learning_assignment_submissions_assignment_id",
        "learning_assignment_submissions",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_assignment_submissions_student_id",
        "learning_assignment_submissions",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_assignment_submissions_submitted_at",
        "learning_assignment_submissions",
        ["submitted_at"],
        unique=False,
    )
    op.create_index(
        "idx_assignment_submission_assignment_submitted",
        "learning_assignment_submissions",
        ["assignment_id", "submitted_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "idx_assignment_submission_assignment_submitted",
        table_name="learning_assignment_submissions",
    )
    op.drop_index("ix_learning_assignment_submissions_submitted_at", table_name="learning_assignment_submissions")
    op.drop_index("ix_learning_assignment_submissions_student_id", table_name="learning_assignment_submissions")
    op.drop_index("ix_learning_assignment_submissions_assignment_id", table_name="learning_assignment_submissions")
    op.drop_table("learning_assignment_submissions")

    op.drop_index("idx_learning_assignment_class_due", table_name="learning_assignments")
    op.drop_index("ix_learning_assignments_due_at", table_name="learning_assignments")
    op.drop_index("ix_learning_assignments_subject_id", table_name="learning_assignments")
    op.drop_index("ix_learning_assignments_teacher_id", table_name="learning_assignments")
    op.drop_index("ix_learning_assignments_class_id", table_name="learning_assignments")
    op.drop_table("learning_assignments")

    op.drop_index("idx_online_class_session_class_time", table_name="online_class_sessions")
    op.drop_index("ix_online_class_sessions_ends_at", table_name="online_class_sessions")
    op.drop_index("ix_online_class_sessions_starts_at", table_name="online_class_sessions")
    op.drop_index("ix_online_class_sessions_subject_id", table_name="online_class_sessions")
    op.drop_index("ix_online_class_sessions_teacher_id", table_name="online_class_sessions")
    op.drop_index("ix_online_class_sessions_class_id", table_name="online_class_sessions")
    op.drop_table("online_class_sessions")

    op.drop_constraint("fk_learning_materials_class_id_class_rooms", "learning_materials", type_="foreignkey")
    op.drop_index("ix_learning_materials_class_id", table_name="learning_materials")
    op.drop_column("learning_materials", "published_at")
    op.drop_column("learning_materials", "is_published")
    op.drop_column("learning_materials", "material_type")
    op.drop_column("learning_materials", "class_id")
