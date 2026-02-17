from flask import session

from app.models import UserRole


ROLE_PRIORITY = [
    UserRole.ADMIN,
    UserRole.GURU,
    UserRole.TU,
    UserRole.WALI_ASRAMA,
    UserRole.WALI_MURID,
    UserRole.SISWA,
    UserRole.MAJLIS_PARTICIPANT,
]

ROLE_LABELS = {
    UserRole.ADMIN: 'Admin',
    UserRole.GURU: 'Guru',
    UserRole.TU: 'Staf TU',
    UserRole.WALI_ASRAMA: 'Wali Asrama',
    UserRole.WALI_MURID: 'Wali Murid',
    UserRole.SISWA: 'Santri',
    UserRole.MAJLIS_PARTICIPANT: 'Peserta Majlis',
}


def parse_role(raw):
    if not raw:
        return None

    if isinstance(raw, UserRole):
        return raw

    if isinstance(raw, str):
        normalized = raw.strip()
        if not normalized:
            return None

        try:
            return UserRole[normalized]
        except KeyError:
            pass

        for role in UserRole:
            if normalized.lower() == role.value.lower():
                return role

    return None


def get_user_roles(user):
    if not user:
        return set()

    if hasattr(user, 'all_roles'):
        return set(user.all_roles())

    return {user.role} if getattr(user, 'role', None) else set()


def get_default_role(user):
    roles = get_user_roles(user)
    for role in ROLE_PRIORITY:
        if role in roles:
            return role
    return next(iter(roles), None)


def get_active_role(user):
    roles = get_user_roles(user)
    if not roles:
        return None

    active_raw = session.get('active_role')
    active_role = parse_role(active_raw)
    if active_role in roles:
        return active_role

    default_role = get_default_role(user)
    if default_role:
        session['active_role'] = default_role.name
    return default_role


def set_active_role(user, role):
    parsed = parse_role(role)
    if not parsed:
        return False

    roles = get_user_roles(user)
    if parsed not in roles:
        return False

    session['active_role'] = parsed.name
    return True


def role_label(role):
    parsed = parse_role(role)
    if not parsed:
        return '-'
    return ROLE_LABELS.get(parsed, parsed.value.replace('_', ' ').title())


def validate_role_combination(roles):
    role_set = {parse_role(role) for role in roles}
    role_set.discard(None)

    if not role_set:
        return False, 'User minimal harus memiliki satu role.'

    if UserRole.ADMIN in role_set and len(role_set) > 1:
        return False, 'Role Admin tidak boleh digabung dengan role lain.'

    if UserRole.SISWA in role_set:
        blocked_for_student = {
            UserRole.ADMIN,
            UserRole.TU,
        }
        conflicts = sorted(
            [role_label(r) for r in role_set.intersection(blocked_for_student)]
        )
        if conflicts:
            return False, f"Role Santri tidak boleh digabung dengan: {', '.join(conflicts)}."

    if UserRole.SISWA in role_set and UserRole.WALI_MURID in role_set:
        return False, 'Role Santri tidak boleh digabung dengan Wali Murid.'

    return True, ''
