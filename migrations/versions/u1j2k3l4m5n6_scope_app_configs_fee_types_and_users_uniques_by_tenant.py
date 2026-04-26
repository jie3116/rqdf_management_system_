"""scope app_configs fee_types and users uniques by tenant

Revision ID: u1j2k3l4m5n6
Revises: t0i1j2k3l4m5
Create Date: 2026-04-26 20:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "u1j2k3l4m5n6"
down_revision = "t0i1j2k3l4m5"
branch_labels = None
depends_on = None


def _get_default_tenant_id(conn):
    default_tenant_id = conn.execute(
        sa.text(
            "SELECT id FROM tenants "
            "WHERE is_default = true AND is_deleted = false "
            "ORDER BY id ASC LIMIT 1"
        )
    ).scalar()
    if default_tenant_id is not None:
        return default_tenant_id

    fallback_tenant_id = conn.execute(
        sa.text(
            "SELECT id FROM tenants "
            "WHERE is_deleted = false "
            "ORDER BY id ASC LIMIT 1"
        )
    ).scalar()
    if fallback_tenant_id is not None:
        return fallback_tenant_id

    raise RuntimeError("Tenant tidak ditemukan. Tidak bisa backfill tenant_id untuk konfigurasi biaya.")


def _list_unique_constraints(table_name):
    inspector = sa.inspect(op.get_bind())
    return inspector.get_unique_constraints(table_name)


def _list_indexes(table_name):
    inspector = sa.inspect(op.get_bind())
    return inspector.get_indexes(table_name)


def _drop_unique_by_columns(table_name, columns):
    target = set(columns)
    for uq in _list_unique_constraints(table_name):
        uq_cols = set(uq.get("column_names") or [])
        name = uq.get("name")
        if uq_cols == target and name:
            op.drop_constraint(name, table_name, type_="unique")
            return


def _drop_unique_index_by_columns(table_name, columns):
    target = set(columns)
    for idx in _list_indexes(table_name):
        if not idx.get("unique"):
            continue
        idx_cols = set(idx.get("column_names") or [])
        name = idx.get("name")
        if idx_cols == target and name:
            op.drop_index(name, table_name=table_name)
            return


def _has_unique_constraint(table_name, name):
    for uq in _list_unique_constraints(table_name):
        if uq.get("name") == name:
            return True
    return False


def upgrade():
    conn = op.get_bind()
    default_tenant_id = _get_default_tenant_id(conn)

    op.add_column("app_configs", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_app_configs_tenant_id", "app_configs", ["tenant_id"], unique=False)
    op.create_foreign_key(
        "fk_app_configs_tenant_id_tenants",
        "app_configs",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    op.add_column("fee_types", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_fee_types_tenant_id", "fee_types", ["tenant_id"], unique=False)
    op.create_foreign_key(
        "fk_fee_types_tenant_id_tenants",
        "fee_types",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    conn.execute(
        sa.text("UPDATE app_configs SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": default_tenant_id},
    )
    conn.execute(
        sa.text("UPDATE fee_types SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": default_tenant_id},
    )

    op.alter_column("app_configs", "tenant_id", nullable=False)
    op.alter_column("fee_types", "tenant_id", nullable=False)

    _drop_unique_by_columns("app_configs", ["key"])
    _drop_unique_index_by_columns("app_configs", ["key"])
    _drop_unique_by_columns("users", ["username"])
    _drop_unique_by_columns("users", ["email"])
    _drop_unique_index_by_columns("users", ["username"])
    _drop_unique_index_by_columns("users", ["email"])

    if not _has_unique_constraint("app_configs", "uq_app_configs_tenant_key"):
        op.create_unique_constraint(
            "uq_app_configs_tenant_key",
            "app_configs",
            ["tenant_id", "key"],
        )
    if not _has_unique_constraint("users", "uq_users_tenant_username"):
        op.create_unique_constraint(
            "uq_users_tenant_username",
            "users",
            ["tenant_id", "username"],
        )
    if not _has_unique_constraint("users", "uq_users_tenant_email"):
        op.create_unique_constraint(
            "uq_users_tenant_email",
            "users",
            ["tenant_id", "email"],
        )


def downgrade():
    _drop_unique_by_columns("users", ["tenant_id", "email"])
    _drop_unique_by_columns("users", ["tenant_id", "username"])
    _drop_unique_by_columns("app_configs", ["tenant_id", "key"])
    _drop_unique_index_by_columns("users", ["tenant_id", "email"])
    _drop_unique_index_by_columns("users", ["tenant_id", "username"])
    _drop_unique_index_by_columns("app_configs", ["tenant_id", "key"])

    if not _has_unique_constraint("app_configs", "uq_app_configs_key"):
        op.create_unique_constraint("uq_app_configs_key", "app_configs", ["key"])
    if not _has_unique_constraint("users", "uq_users_username"):
        op.create_unique_constraint("uq_users_username", "users", ["username"])
    if not _has_unique_constraint("users", "uq_users_email"):
        op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.drop_constraint("fk_fee_types_tenant_id_tenants", "fee_types", type_="foreignkey")
    op.drop_index("ix_fee_types_tenant_id", table_name="fee_types")
    op.drop_column("fee_types", "tenant_id")

    op.drop_constraint("fk_app_configs_tenant_id_tenants", "app_configs", type_="foreignkey")
    op.drop_index("ix_app_configs_tenant_id", table_name="app_configs")
    op.drop_column("app_configs", "tenant_id")
