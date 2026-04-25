from sqlalchemy import and_, or_

from app.models import BoardingDormitory, ClassRoom, ProgramGroup, Tenant, User


def get_default_tenant():
    return Tenant.query.filter_by(is_default=True, is_deleted=False).first()


def get_default_tenant_id():
    tenant = get_default_tenant()
    return tenant.id if tenant else None


def resolve_tenant_id(user=None, fallback_default=True):
    tenant_id = getattr(user, "tenant_id", None) if user else None
    if tenant_id is not None:
        return tenant_id
    if fallback_default:
        return get_default_tenant_id()
    return None


def scoped_classrooms_query(tenant_id):
    if tenant_id is None:
        return ClassRoom.query.filter(ClassRoom.id == -1)

    return (
        ClassRoom.query.join(
            ProgramGroup,
            and_(
                ProgramGroup.id == ClassRoom.program_group_id,
                ProgramGroup.is_deleted.is_(False),
            ),
        )
        .filter(
            ClassRoom.is_deleted.is_(False),
            ProgramGroup.tenant_id == tenant_id,
        )
    )


def scoped_dormitories_query(tenant_id):
    if tenant_id is None:
        return BoardingDormitory.query.filter(BoardingDormitory.id == -1)

    return (
        BoardingDormitory.query.outerjoin(
            ProgramGroup,
            and_(
                ProgramGroup.id == BoardingDormitory.program_group_id,
                ProgramGroup.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            User,
            and_(
                User.id == BoardingDormitory.guardian_user_id,
                User.is_deleted.is_(False),
            ),
        )
        .filter(
            BoardingDormitory.is_deleted.is_(False),
            or_(
                ProgramGroup.tenant_id == tenant_id,
                and_(
                    BoardingDormitory.program_group_id.is_(None),
                    User.tenant_id == tenant_id,
                ),
            ),
        )
    )


def classroom_in_tenant(class_room, tenant_id):
    if class_room is None or tenant_id is None:
        return False
    if not class_room.program_group_id:
        return False
    group = ProgramGroup.query.filter_by(id=class_room.program_group_id, is_deleted=False).first()
    if group is None:
        return False
    return group.tenant_id == tenant_id


def dormitory_in_tenant(dormitory, tenant_id):
    if dormitory is None or tenant_id is None:
        return False

    if dormitory.program_group_id:
        group = ProgramGroup.query.filter_by(id=dormitory.program_group_id, is_deleted=False).first()
        if group is not None:
            return group.tenant_id == tenant_id

    if dormitory.guardian_user_id:
        guardian = User.query.filter_by(id=dormitory.guardian_user_id, is_deleted=False).first()
        if guardian is not None:
            return guardian.tenant_id == tenant_id

    return False
