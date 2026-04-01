from app import create_app
from app.extensions import db
from app.models import (
    BoardingGuardian,
    MajlisParticipant,
    Parent,
    Person,
    PersonKind,
    Staff,
    Student,
    Tenant,
    Teacher,
    User,
)


def _tenant_id_from_user(user_id):
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    return user.tenant_id if user else None


def _default_tenant_id():
    tenant = Tenant.query.filter_by(is_default=True).first()
    return tenant.id if tenant else None


def _resolve_tenant_id(profile):
    user_id = getattr(profile, "user_id", None)
    tenant_id = _tenant_id_from_user(user_id)
    if tenant_id is not None:
        return tenant_id

    if isinstance(profile, Student) and profile.parent_id:
        parent = db.session.get(Parent, profile.parent_id)
        if parent and parent.user_id:
            tenant_id = _tenant_id_from_user(parent.user_id)
            if tenant_id is not None:
                return tenant_id

    return _default_tenant_id()


def _find_existing_person(tenant_id, profile):
    if getattr(profile, "person_id", None):
        return Person.query.filter_by(id=profile.person_id, tenant_id=tenant_id).first()

    user_id = getattr(profile, "user_id", None)
    if user_id is not None:
        existing = Person.query.filter_by(tenant_id=tenant_id, user_id=user_id).first()
        if existing:
            return existing

    return None


def _ensure_person(tenant_id, profile, kind, code_prefix):
    person = _find_existing_person(tenant_id, profile)
    if person is None:
        person = Person(
            tenant_id=tenant_id,
            user_id=getattr(profile, "user_id", None),
            person_code=f"{code_prefix}-{profile.id}",
            person_kind=kind,
        )
        db.session.add(person)

    person.full_name = getattr(profile, "full_name", None) or person.full_name or "-"
    person.phone = getattr(profile, "phone", None)
    person.address = getattr(profile, "address", None)
    person.is_active = True
    profile.person_id = person.id if person.id is not None else profile.person_id
    return person


def _flush_and_attach(profile, person):
    db.session.flush()
    profile.person_id = person.id


def backfill_people():
    app = create_app()
    with app.app_context():
        stats = {
            "students": 0,
            "parents": 0,
            "majlis": 0,
            "teachers": 0,
            "staff": 0,
            "guardians": 0,
            "skipped": 0,
        }

        students = Student.query.execution_options(include_deleted=True).all()
        for student in students:
            tenant_id = _resolve_tenant_id(student)
            if tenant_id is None:
                stats["skipped"] += 1
                continue
            person = _ensure_person(tenant_id, student, PersonKind.STUDENT, "STUDENT")
            person.gender = student.gender
            person.date_of_birth = student.date_of_birth
            _flush_and_attach(student, person)
            stats["students"] += 1

        parents = Parent.query.execution_options(include_deleted=True).all()
        for parent in parents:
            tenant_id = _resolve_tenant_id(parent)
            if tenant_id is None:
                stats["skipped"] += 1
                continue
            person = _ensure_person(tenant_id, parent, PersonKind.PARENT, "PARENT")
            _flush_and_attach(parent, person)
            stats["parents"] += 1

        majlis_participants = MajlisParticipant.query.execution_options(include_deleted=True).all()
        for participant in majlis_participants:
            tenant_id = _resolve_tenant_id(participant)
            if tenant_id is None:
                stats["skipped"] += 1
                continue
            person = _ensure_person(tenant_id, participant, PersonKind.EXTERNAL, "EXTERNAL")
            _flush_and_attach(participant, person)
            stats["majlis"] += 1

        teachers = Teacher.query.execution_options(include_deleted=True).all()
        for teacher in teachers:
            tenant_id = _resolve_tenant_id(teacher)
            if tenant_id is None:
                stats["skipped"] += 1
                continue
            person = _ensure_person(tenant_id, teacher, PersonKind.STAFF, "TEACHER")
            _flush_and_attach(teacher, person)
            stats["teachers"] += 1

        staffs = Staff.query.execution_options(include_deleted=True).all()
        for staff in staffs:
            tenant_id = _resolve_tenant_id(staff)
            if tenant_id is None:
                stats["skipped"] += 1
                continue
            person = _ensure_person(tenant_id, staff, PersonKind.STAFF, "STAFF")
            _flush_and_attach(staff, person)
            stats["staff"] += 1

        guardians = BoardingGuardian.query.execution_options(include_deleted=True).all()
        for guardian in guardians:
            tenant_id = _resolve_tenant_id(guardian)
            if tenant_id is None:
                stats["skipped"] += 1
                continue
            person = _ensure_person(tenant_id, guardian, PersonKind.STAFF, "GUARDIAN")
            _flush_and_attach(guardian, person)
            stats["guardians"] += 1

        db.session.commit()
        print("People backfill completed.")
        for key, value in stats.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    backfill_people()
