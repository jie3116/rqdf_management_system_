# app/services/admission_service.py
from app.models import User, Student, Fee, FeeType, Candidate, AcademicYear
from app.extensions import db
from datetime import datetime


class AdmissionService:
    @staticmethod
    def accept_candidate(candidate_id, admission_data):
        candidate = Candidate.query.get_or_404(candidate_id)

        try:
            # 1. Create User Account
            user = User(
                username=candidate.registration_number,
                email=candidate.email,
                role='student'
            )
            user.set_password('rqdf1234')  # Default password
            db.session.add(user)
            db.session.flush()  # Mendapatkan user.id sebelum commit

            # 2. Create Student Profile
            student = Student(
                user_id=user.id,
                full_name=candidate.full_name,
                gender=candidate.gender,
                program_type=candidate.program_type,
                # ... data lainnya
            )
            db.session.add(student)

            # 3. Generate Invoices (LOGIKA HARGA DIAMBIL DARI DB, BUKAN HARDCODED)
            AdmissionService._generate_initial_fees(student, candidate.program_type)

            candidate.status = 'accepted'
            db.session.commit()
            return student

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def _generate_initial_fees(student, program_type):
        # Ambil template biaya dari database
        # Senior Tip: Jangan hardcode harga '200000' di sini.
        fees_to_create = FeeType.query.filter_by(is_active=True, category='admission').all()

        for ft in fees_to_create:
            new_fee = Fee(
                student_id=student.id,
                fee_type_id=ft.id,
                amount=ft.default_amount,  # Ambil dari kolom nominal di DB
                status='unpaid'
            )
            db.session.add(new_fee)