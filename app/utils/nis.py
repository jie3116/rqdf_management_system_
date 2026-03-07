from datetime import datetime
from app.models import Student, User
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
