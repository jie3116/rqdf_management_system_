from datetime import datetime
from app.models import Student, Teacher, User
from app.utils.timezone import local_now


def generate_nis(year=None):
    target_year = year or local_now().year
    prefix = f"{target_year}"
    last_student = Student.query.filter(Student.nis.like(f"{prefix}%")).order_by(Student.nis.desc()).first()

    sequence = 1
    if last_student and last_student.nis and last_student.nis[4:].isdigit():
        sequence = int(last_student.nis[4:]) + 1

    while True:
        nis = f"{prefix}{sequence:05d}"
        if not User.query.filter_by(username=nis).first():
            return nis
        sequence += 1


def generate_nip(year=None):
    target_year = year or local_now().year
    prefix = f"{target_year % 100:02d}"
    last_teacher = Teacher.query.filter(Teacher.nip.like(f"{prefix}%")).order_by(Teacher.nip.desc()).first()

    sequence = 1
    if last_teacher and last_teacher.nip:
        suffix = last_teacher.nip[len(prefix):]
        if suffix.isdigit():
            sequence = int(suffix) + 1

    while True:
        nip = f"{prefix}{sequence:04d}"
        if not User.query.filter_by(username=nip).first():
            return nip
        sequence += 1
