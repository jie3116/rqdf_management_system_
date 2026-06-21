import argparse
import os
import sys


CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import Tenant, TenantStatus, User, UserRole


PLATFORM_TENANT_SLUG = "platform"
PLATFORM_TENANT_CODE = "PLATFORM"
PLATFORM_TENANT_NAME = "Platform"
DEFAULT_SUPERADMIN_USERNAME = "superadmin"


class PreparationError(RuntimeError):
    pass


def _has_super_admin_role(user):
    return user.has_role(UserRole.SUPER_ADMIN)


def _super_admin_users():
    users = (
        User.query
        .filter(User.is_deleted.is_(False))
        .order_by(User.id.asc())
        .all()
    )
    return [user for user in users if _has_super_admin_role(user)]


def _tenant_user_counts(tenant_id):
    if tenant_id is None:
        return {"total": 0, "super_admin": 0, "non_super_admin": 0}

    users = (
        User.query
        .filter(
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        )
        .order_by(User.id.asc())
        .all()
    )
    super_admin_count = sum(1 for user in users if _has_super_admin_role(user))
    return {
        "total": len(users),
        "super_admin": super_admin_count,
        "non_super_admin": len(users) - super_admin_count,
    }


def _print_tenant_summary(label, tenant):
    if tenant is None:
        print(f"{label}: tenant=(missing)")
        return
    counts = _tenant_user_counts(tenant.id)
    print(
        f"{label}:",
        f"tenant_id={tenant.id}",
        f"name={tenant.name!r}",
        f"slug={tenant.slug!r}",
        f"code={tenant.code!r}",
        f"status={tenant.status.name if tenant.status else None}",
        f"is_default={tenant.is_default}",
        f"is_deleted={tenant.is_deleted}",
        f"users_total={counts['total']}",
        f"users_super_admin={counts['super_admin']}",
        f"users_non_super_admin={counts['non_super_admin']}",
    )


def _print_user_summary(label, user):
    if user is None:
        print(f"{label}: user=(missing)")
        return
    tenant = db.session.get(Tenant, user.tenant_id)
    print(
        f"{label}:",
        f"user_id={user.id}",
        f"username={user.username!r}",
        f"email={user.email!r}",
        f"primary_role={user.role.name if user.role else None}",
        f"has_super_admin={_has_super_admin_role(user)}",
        f"is_deleted={user.is_deleted}",
        f"tenant_id={user.tenant_id}",
        f"tenant_slug={tenant.slug if tenant else None!r}",
        f"tenant_code={tenant.code if tenant else None!r}",
    )


def _find_platform_tenant():
    slug_match = (
        Tenant.query
        .execution_options(include_deleted=True)
        .filter(Tenant.slug == PLATFORM_TENANT_SLUG)
        .first()
    )
    code_match = (
        Tenant.query
        .execution_options(include_deleted=True)
        .filter(Tenant.code == PLATFORM_TENANT_CODE)
        .first()
    )

    if slug_match and code_match and slug_match.id != code_match.id:
        raise PreparationError(
            "Konflik platform tenant: slug 'platform' dan code 'PLATFORM' dimiliki tenant berbeda."
        )
    if slug_match and slug_match.code != PLATFORM_TENANT_CODE:
        raise PreparationError(
            f"Konflik platform tenant: slug 'platform' sudah dipakai tenant #{slug_match.id} "
            f"dengan code {slug_match.code!r}."
        )
    if code_match and code_match.slug != PLATFORM_TENANT_SLUG:
        raise PreparationError(
            f"Konflik platform tenant: code 'PLATFORM' sudah dipakai tenant #{code_match.id} "
            f"dengan slug {code_match.slug!r}."
        )
    return slug_match or code_match


def _validate_existing_platform_tenant_users(platform_tenant, target_user):
    if platform_tenant is None:
        return

    users = (
        User.query
        .filter(
            User.tenant_id == platform_tenant.id,
            User.is_deleted.is_(False),
        )
        .order_by(User.id.asc())
        .all()
    )
    unexpected_users = [
        user for user in users
        if user.id != target_user.id and not _has_super_admin_role(user)
    ]
    if unexpected_users:
        details = ", ".join(
            f"#{user.id}:{user.username}" for user in unexpected_users
        )
        raise PreparationError(
            "Platform tenant sudah berisi user non-SUPER_ADMIN. "
            f"Tidak aman melanjutkan otomatis: {details}"
        )


def prepare_platform_tenant(
    *,
    apply_changes=False,
    superadmin_username=DEFAULT_SUPERADMIN_USERNAME,
    expected_user_id=None,
):
    mode = "APPLY" if apply_changes else "DRY-RUN"
    print(f"Mode: {mode}")
    print(
        "Target platform tenant:",
        f"slug={PLATFORM_TENANT_SLUG!r}",
        f"code={PLATFORM_TENANT_CODE!r}",
    )
    print(f"Target superadmin username: {superadmin_username!r}")
    print(f"Expected user id: {expected_user_id if expected_user_id is not None else '(not provided)'}")

    if apply_changes and expected_user_id is None:
        raise PreparationError(
            "--apply membutuhkan --expected-user-id. "
            "Jalankan --dry-run terlebih dahulu, catat target user_id dari output, "
            "lalu jalankan ulang dengan --apply --expected-user-id <id>."
        )

    super_admins = _super_admin_users()
    if len(super_admins) > 1:
        details = ", ".join(f"#{user.id}:{user.username}" for user in super_admins)
        raise PreparationError(
            "Ditemukan lebih dari satu SUPER_ADMIN. Butuh approval/manual handling: "
            f"{details}"
        )

    target_user = User.query.filter(
        User.username == superadmin_username,
        User.is_deleted.is_(False),
    ).first()
    if target_user is None:
        raise PreparationError(
            f"User {superadmin_username!r} tidak ditemukan atau sudah soft-deleted."
        )

    if expected_user_id is not None and target_user.id != expected_user_id:
        raise PreparationError(
            "Target user tidak sesuai expected user id. "
            f"expected={expected_user_id}, actual=#{target_user.id}:{target_user.username}"
        )

    if super_admins and super_admins[0].id != target_user.id:
        existing = super_admins[0]
        raise PreparationError(
            "SUPER_ADMIN existing bukan target user yang diminta. "
            f"existing=#{existing.id}:{existing.username}, target=#{target_user.id}:{target_user.username}"
        )

    platform_tenant = _find_platform_tenant()
    original_tenant = db.session.get(Tenant, target_user.tenant_id)

    print("\nBefore summary")
    _print_user_summary("target_user", target_user)
    _print_tenant_summary("current_user_tenant", original_tenant)
    _print_tenant_summary("platform_tenant", platform_tenant)

    _validate_existing_platform_tenant_users(platform_tenant, target_user)

    planned_actions = []
    if platform_tenant is None:
        planned_actions.append("create_platform_tenant")
    elif platform_tenant.status != TenantStatus.ACTIVE or platform_tenant.is_deleted:
        planned_actions.append("activate_platform_tenant")

    if target_user.role != UserRole.SUPER_ADMIN:
        planned_actions.append("set_user_primary_role_super_admin")

    target_platform_tenant_id = platform_tenant.id if platform_tenant else "(new)"
    if target_user.tenant_id != target_platform_tenant_id:
        planned_actions.append("move_superadmin_to_platform_tenant")

    print("\nPlanned actions")
    if planned_actions:
        for action in planned_actions:
            print(f"- {action}")
    else:
        print("- none")

    if not apply_changes:
        print("\nDRY-RUN completed. No database changes were committed.")
        return

    try:
        if platform_tenant is None:
            platform_tenant = Tenant(
                name=PLATFORM_TENANT_NAME,
                slug=PLATFORM_TENANT_SLUG,
                code=PLATFORM_TENANT_CODE,
                status=TenantStatus.ACTIVE,
                timezone="Asia/Jakarta",
                is_default=False,
            )
            db.session.add(platform_tenant)
            db.session.flush()
        else:
            platform_tenant.status = TenantStatus.ACTIVE
            platform_tenant.is_deleted = False

        target_user.role = UserRole.SUPER_ADMIN
        target_user.tenant_id = platform_tenant.id

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    print("\nAfter summary")
    _print_user_summary("target_user", target_user)
    _print_tenant_summary("previous_user_tenant", original_tenant)
    _print_tenant_summary("platform_tenant", platform_tenant)
    print("\nAPPLY completed. Database changes were committed.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Prepare platform tenant and move the single superadmin account. "
            "Idempotent; use --dry-run first."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print planned changes without committing.")
    mode.add_argument("--apply", action="store_true", help="Apply changes and commit.")
    parser.add_argument(
        "--superadmin-username",
        default=DEFAULT_SUPERADMIN_USERNAME,
        help="Target superadmin username. Default: superadmin.",
    )
    parser.add_argument(
        "--expected-user-id",
        type=int,
        help=(
            "Optional guard for dry-run, required for --apply. "
            "Use the target user_id printed by --dry-run."
        ),
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        try:
            prepare_platform_tenant(
                apply_changes=args.apply,
                superadmin_username=args.superadmin_username,
                expected_user_id=args.expected_user_id,
            )
        except PreparationError as exc:
            db.session.rollback()
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
