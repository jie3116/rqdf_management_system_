from sqlalchemy import and_, or_

from app.extensions import db
from app.models import Announcement, AnnouncementRead, UserRole


def visible_announcements_query(user, class_ids=None, user_ids=None, program_types=None):
    class_ids = [cid for cid in (class_ids or []) if cid]
    user_ids = [uid for uid in (user_ids or []) if uid]
    program_types = [p for p in (program_types or []) if p]

    filters = [
        Announcement.target_scope == 'ALL',
        and_(Announcement.target_scope == 'ROLE', Announcement.target_role == user.role.value),
    ]

    if class_ids:
        filters.append(and_(Announcement.target_scope == 'CLASS', Announcement.target_class_id.in_(class_ids)))

    if user_ids:
        filters.append(and_(Announcement.target_scope == 'USER', Announcement.target_user_id.in_(user_ids)))

    if program_types:
        filters.append(and_(Announcement.target_scope == 'PROGRAM', Announcement.target_program_type.in_(program_types)))

    return Announcement.query.filter(
        Announcement.is_active.is_(True),
        or_(*filters)
    )


def announcement_author_label(announcement):
    author = announcement.author
    if not author:
        return "Sistem"

    role = author.role.value if author.role else ""
    if role == UserRole.TU.value:
        return "Staf TU"
    if role == UserRole.GURU.value:
        if announcement.target_class and announcement.target_class.homeroom_teacher and \
                announcement.target_class.homeroom_teacher.user_id == author.id:
            return f"Wali Kelas {announcement.target_class.name}"
        return "Guru"
    if role == UserRole.ADMIN.value:
        return "Admin"
    if role == UserRole.WALI_MURID.value:
        return "Wali Murid"
    if role == UserRole.SISWA.value:
        return "Santri"
    if role == UserRole.MAJLIS_PARTICIPANT.value:
        return "Peserta Majlis"
    return author.username


def get_announcements_for_dashboard(user, class_ids=None, user_ids=None, program_types=None, show_all=False):
    base_query = visible_announcements_query(
        user,
        class_ids=class_ids,
        user_ids=user_ids,
        program_types=program_types
    )
    ordered_query = base_query.order_by(Announcement.created_at.desc())
    announcements = ordered_query.all() if show_all else ordered_query.limit(3).all()

    all_visible_ids = [row[0] for row in base_query.with_entities(Announcement.id).all()]
    unread_count = 0
    read_ids = set()
    if all_visible_ids:
        read_ids = {
            row[0] for row in db.session.query(AnnouncementRead.announcement_id).filter(
                AnnouncementRead.user_id == user.id,
                AnnouncementRead.announcement_id.in_(all_visible_ids)
            ).all()
        }
        unread_count = len(set(all_visible_ids) - read_ids)

    for item in announcements:
        item.is_unread_for_current_user = item.id not in read_ids
        item.author_label = announcement_author_label(item)

    return announcements, unread_count


def mark_announcements_as_read(user, announcements):
    if not announcements:
        return

    ann_ids = [a.id for a in announcements if a]
    if not ann_ids:
        return

    existing = {
        row[0] for row in db.session.query(AnnouncementRead.announcement_id).filter(
            AnnouncementRead.user_id == user.id,
            AnnouncementRead.announcement_id.in_(ann_ids)
        ).all()
    }
    new_items = [
        AnnouncementRead(user_id=user.id, announcement_id=ann_id)
        for ann_id in ann_ids if ann_id not in existing
    ]
    if new_items:
        db.session.add_all(new_items)
        db.session.commit()
