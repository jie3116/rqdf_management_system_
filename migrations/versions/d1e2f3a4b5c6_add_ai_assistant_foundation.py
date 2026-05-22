"""add ai assistant foundation

Revision ID: d1e2f3a4b5c6
Revises: c6d7e8f9g0h1
Create Date: 2026-05-17 20:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c6d7e8f9g0h1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_assistant_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_status", sa.String(length=20), nullable=False),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_documents_teacher_id", "ai_assistant_documents", ["teacher_id"], unique=False)
    op.create_index("ix_ai_assistant_documents_tenant_id", "ai_assistant_documents", ["tenant_id"], unique=False)
    op.create_index(
        "idx_ai_document_teacher_created",
        "ai_assistant_documents",
        ["teacher_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "ai_assistant_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["ai_assistant_documents.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_requests_document_id", "ai_assistant_requests", ["document_id"], unique=False)
    op.create_index("ix_ai_assistant_requests_teacher_id", "ai_assistant_requests", ["teacher_id"], unique=False)
    op.create_index("ix_ai_assistant_requests_tenant_id", "ai_assistant_requests", ["tenant_id"], unique=False)

    op.create_table(
        "ai_assistant_outputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("output_format", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["ai_assistant_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_outputs_request_id", "ai_assistant_outputs", ["request_id"], unique=False)


def downgrade():
    op.drop_index("ix_ai_assistant_outputs_request_id", table_name="ai_assistant_outputs")
    op.drop_table("ai_assistant_outputs")
    op.drop_index("ix_ai_assistant_requests_tenant_id", table_name="ai_assistant_requests")
    op.drop_index("ix_ai_assistant_requests_teacher_id", table_name="ai_assistant_requests")
    op.drop_index("ix_ai_assistant_requests_document_id", table_name="ai_assistant_requests")
    op.drop_table("ai_assistant_requests")
    op.drop_index("idx_ai_document_teacher_created", table_name="ai_assistant_documents")
    op.drop_index("ix_ai_assistant_documents_tenant_id", table_name="ai_assistant_documents")
    op.drop_index("ix_ai_assistant_documents_teacher_id", table_name="ai_assistant_documents")
    op.drop_table("ai_assistant_documents")
