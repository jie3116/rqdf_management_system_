from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_
from app.extensions import db
from app.decorators import role_required
from app.forms import PaymentForm, StudentForm  # Pastikan import ini ada
from app.models import (
    UserRole, User, Student, Parent, Staff, ClassRoom, Gender,
    Invoice, Transaction, PaymentStatus, FeeType,
    StudentCandidate, RegistrationStatus, ProgramType, EducationLevel,
    MajlisParticipant, ClassType, Announcement
)
from app.utils.nis import generate_nis

staff_bp = Blueprint('staff', __name__)


@staff_bp.route('/dashboard')
@login_required
@role_required(UserRole.TU)
def dashboard():
    # 1. Hitung Pemasukan Hari Ini
    today = datetime.now().date()
    pemasukan_hari_ini = db.session.query(func.sum(Transaction.amount)).filter(
        func.date(Transaction.date) == today
    ).scalar() or 0

    # 2. Kirim ke HTML
    return render_template('staff/dashboard.html',
                           pemasukan_hari_ini=pemasukan_hari_ini)


# =========================================================
# 1. MODUL KEUANGAN (KASIR & GENERATE TAGIHAN)
# =========================================================

@staff_bp.route('/kasir', methods=['GET'])
@login_required
@role_required(UserRole.TU)
def cashier_search():
    query = request.args.get('q')
    students = []
    if query:
        students = Student.query.filter(
            (Student.full_name.ilike(f'%{query}%')) |
            (Student.nis.ilike(f'%{query}%'))).all()
    return render_template('staff/cashier_search.html', students=students, query=query)


@staff_bp.route('/kasir/bayar/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def cashier_pay(student_id):
    student = Student.query.get_or_404(student_id)
    unpaid_invoices = Invoice.query.filter(
        Invoice.student_id == student.id,
        Invoice.is_deleted.is_(False),
        Invoice.status != PaymentStatus.PAID
    ).all()

    form = PaymentForm()

    if request.method == 'POST':
        invoice_id = request.form.get('invoice_id')
        invoice = Invoice.query.filter_by(id=invoice_id, is_deleted=False).first()

        if invoice and form.validate_on_submit():
            bayar = form.amount.data
            sisa_tagihan = invoice.total_amount - invoice.paid_amount

            if bayar > sisa_tagihan:
                flash(f'Gagal! Pembayaran melebihi sisa (Maks: {sisa_tagihan})', 'danger')
            else:
                # Catat Transaksi
                trx = Transaction(
                    invoice_id=invoice.id,
                    amount=bayar,
                    method=form.method.data,
                    pic_id=current_user.id,  # TU yang login
                    #status='SUCCESS'
                )
                db.session.add(trx)

                # Update Invoice
                invoice.paid_amount += bayar
                if invoice.paid_amount >= invoice.total_amount:
                    invoice.status = PaymentStatus.PAID
                else:
                    invoice.status = PaymentStatus.PARTIAL

                db.session.commit()
                flash(f'Pembayaran Rp {bayar:,.0f} diterima!', 'success')
                return redirect(url_for('staff.cashier_pay', student_id=student.id))

    return render_template('staff/cashier_payment.html', student=student, invoices=unpaid_invoices, form=form)


def _program_labels():
    return {
        ProgramType.SEKOLAH_FULLDAY.name: "SBQ (Sekolah Bina Qur'an)",
        ProgramType.RQDF_SORE.name: 'Reguler (RQDF Sore)',
        ProgramType.TAKHOSUS_TAHFIDZ.name: 'Takhosus Tahfidz',
        ProgramType.MAJLIS_TALIM.name: "Majlis Ta'lim",
    }


def _parse_invoice_target(source):
    target_scope = (source.get('target_scope') or 'ALL').upper()
    target_program_type = (source.get('target_program_type') or '').strip()
    target_class_id = source.get('target_class_id', type=int)
    target_student_id = source.get('target_student_id', type=int)

    if target_scope not in {'ALL', 'PROGRAM', 'CLASS', 'STUDENT'}:
        return None, "Target tagihan tidak valid."

    if target_scope == 'PROGRAM' and target_program_type not in _program_labels().keys():
        return None, "Pilih program tujuan terlebih dahulu."

    if target_scope == 'CLASS' and not target_class_id:
        return None, "Pilih kelas tujuan terlebih dahulu."

    if target_scope == 'STUDENT' and not target_student_id:
        return None, "Pilih siswa tujuan terlebih dahulu."

    return {
        'target_scope': target_scope,
        'target_program_type': target_program_type,
        'target_class_id': target_class_id,
        'target_student_id': target_student_id,
    }, None


def _targeted_students(target):
    students_query = Student.query.filter_by(is_deleted=False)

    if target['target_scope'] == 'PROGRAM':
        program_enum = ProgramType[target['target_program_type']]
        students_query = students_query.join(
            ClassRoom, Student.current_class_id == ClassRoom.id
        ).filter(
            ClassRoom.is_deleted.is_(False),
            ClassRoom.program_type == program_enum
        )
    elif target['target_scope'] == 'CLASS':
        students_query = students_query.filter(Student.current_class_id == target['target_class_id'])
    elif target['target_scope'] == 'STUDENT':
        students_query = students_query.filter(Student.id == target['target_student_id'])

    return students_query.order_by(Student.full_name.asc()).all()


def _invoice_number(fee_id, student_id):
    return f"INV/{datetime.now().strftime('%Y%m%d%H%M%S%f')}/{fee_id}/{student_id}"


def _send_invoices_redirect_params(source, target):
    selected_fee_id = source.get('selected_fee_id', type=int) if hasattr(source, 'get') else None
    return {
        'selected_fee_id': selected_fee_id or '',
        'target_scope': target['target_scope'],
        'target_program_type': target['target_program_type'] or '',
        'target_class_id': target['target_class_id'] or '',
        'target_student_id': target['target_student_id'] or '',
    }


@staff_bp.route('/tagihan/terbitkan/<int:fee_id>', methods=['POST'])
@login_required
@role_required(UserRole.TU)
def generate_invoices(fee_id):
    fee = FeeType.query.get_or_404(fee_id)
    target, error_message = _parse_invoice_target(request.form)
    if error_message:
        flash(error_message, 'warning')
        return redirect(url_for('staff.send_invoices'))

    students = _targeted_students(target)
    if not students:
        flash('Tidak ada siswa sesuai target pengiriman tagihan.', 'warning')
        return redirect(url_for('staff.send_invoices', **_send_invoices_redirect_params(request.form, target)))

    total_target = len(students)
    count_success = 0
    skipped_duplicate = 0
    due_date_default = datetime.now() + timedelta(days=10)
    is_monthly_fee = "SPP" in fee.name.upper() or "BULAN" in fee.name.upper()

    try:
        for student in students:
            candidate = getattr(student, "student_candidate", None)

            # Cek duplikat hanya pada invoice aktif.
            if Invoice.query.filter_by(student_id=student.id, fee_type_id=fee.id, is_deleted=False).first():
                skipped_duplicate += 1
                continue

            nominal_final = fee.amount
            if is_monthly_fee and student.custom_spp_fee is not None:
                nominal_final = student.custom_spp_fee
            elif candidate and candidate.scholarship_category.name != 'NON_BEASISWA':
                nominal_final = fee.amount * 0.5

            new_inv = Invoice(
                invoice_number=_invoice_number(fee.id, student.id),
                student_id=student.id,
                fee_type_id=fee.id,
                total_amount=int(nominal_final),
                status=PaymentStatus.UNPAID,
                due_date=due_date_default
            )
            db.session.add(new_inv)
            count_success += 1

        db.session.commit()
        if count_success == 0 and skipped_duplicate > 0:
            flash(
                f'Tidak ada tagihan baru. Target {total_target} siswa, seluruhnya sudah punya tagihan aktif untuk biaya ini.',
                'warning'
            )
        elif skipped_duplicate > 0:
            flash(
                f'Berhasil menerbitkan {count_success} tagihan baru. Dilewati karena duplikat: {skipped_duplicate}.',
                'warning'
            )
        else:
            flash(f'Berhasil menerbitkan {count_success} tagihan baru.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('staff.send_invoices', **_send_invoices_redirect_params(request.form, target)))


@staff_bp.route('/tagihan/hapus/<int:fee_id>', methods=['POST'])
@login_required
@role_required(UserRole.TU)
def delete_generated_invoices(fee_id):
    fee = FeeType.query.get_or_404(fee_id)
    target, error_message = _parse_invoice_target(request.form)
    if error_message:
        flash(error_message, 'warning')
        return redirect(url_for('staff.send_invoices'))

    students = _targeted_students(target)
    student_ids = [student.id for student in students]
    if not student_ids:
        flash('Tidak ada siswa sesuai target penghapusan.', 'warning')
        return redirect(url_for('staff.send_invoices', **_send_invoices_redirect_params(request.form, target)))

    invoices = Invoice.query.filter(
        Invoice.fee_type_id == fee.id,
        Invoice.student_id.in_(student_ids),
        Invoice.is_deleted.is_(False)
    ).all()

    if not invoices:
        flash('Tidak ada invoice aktif yang bisa dihapus pada target ini.', 'warning')
        return redirect(url_for('staff.send_invoices', **_send_invoices_redirect_params(request.form, target)))

    deleted_count = 0
    skipped_count = 0
    try:
        for invoice in invoices:
            if invoice.transactions or (invoice.paid_amount or 0) > 0:
                skipped_count += 1
                continue
            invoice.is_deleted = True
            deleted_count += 1

        db.session.commit()
        if skipped_count:
            flash(
                f'Invoice terhapus: {deleted_count}. Dilewati (sudah ada pembayaran/transaksi): {skipped_count}.',
                'warning'
            )
        else:
            flash(f'Berhasil menghapus {deleted_count} invoice pada biaya "{fee.name}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus invoice: {str(e)}', 'danger')

    return redirect(url_for('staff.send_invoices', **_send_invoices_redirect_params(request.form, target)))


@staff_bp.route('/tagihan/kirim', methods=['GET'])
@login_required
@role_required(UserRole.TU)
def send_invoices():
    selected_fee_id = request.args.get('selected_fee_id', type=int)
    target, _ = _parse_invoice_target(request.args)
    if not target:
        target = {
            'target_scope': 'ALL',
            'target_program_type': '',
            'target_class_id': None,
            'target_student_id': None,
        }
    fees_query = FeeType.query
    if selected_fee_id:
        fees_query = fees_query.filter(FeeType.id == selected_fee_id)
    fees = fees_query.order_by(FeeType.id.desc()).all()
    fee_options = FeeType.query.order_by(FeeType.name.asc()).all()
    classes = ClassRoom.query.filter_by(is_deleted=False).order_by(ClassRoom.name.asc()).all()
    students = Student.query.filter_by(is_deleted=False).order_by(Student.full_name.asc()).all()
    return render_template(
        'staff/send_invoices.html',
        fees=fees,
        fee_options=fee_options,
        selected_fee_id=selected_fee_id,
        classes=classes,
        students=students,
        program_labels=_program_labels(),
        target_scope=target['target_scope'],
        target_program_type=target['target_program_type'],
        target_class_id=target['target_class_id'],
        target_student_id=target['target_student_id']
    )


@staff_bp.route('/pengumuman', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def manage_announcements():
    classes = ClassRoom.query.filter_by(is_deleted=False).order_by(ClassRoom.name.asc()).all()
    users = User.query.filter(
        User.role != UserRole.ADMIN,
        ~User.role_assignments.any(role=UserRole.ADMIN)
    ).order_by(User.username.asc()).limit(500).all()
    available_roles = sorted({role_value for u in users for role_value in u.all_role_values()})
    role_labels = {
        UserRole.WALI_MURID.value: 'Wali Murid',
        UserRole.WALI_ASRAMA.value: 'Wali Asrama',
        UserRole.SISWA.value: 'Santri',
        UserRole.GURU.value: 'Guru',
        UserRole.TU.value: 'Staf TU',
        UserRole.MAJLIS_PARTICIPANT.value: 'Peserta Majlis',
    }
    targetable_roles = [
        UserRole.GURU.value,
        UserRole.SISWA.value,
        UserRole.WALI_MURID.value,
        UserRole.WALI_ASRAMA.value,
        UserRole.MAJLIS_PARTICIPANT.value,
    ]
    program_labels = {
        ProgramType.SEKOLAH_FULLDAY.name: "SBQ (Sekolah Bina Qur'an)",
        ProgramType.RQDF_SORE.name: 'Reguler (RQDF Sore)',
        ProgramType.TAKHOSUS_TAHFIDZ.name: 'Takhosus Tahfidz',
        ProgramType.MAJLIS_TALIM.name: "Majlis Ta'lim",
    }

    if request.method == 'POST':
        target_scope = (request.form.get('target_scope') or 'ALL').upper()
        title = (request.form.get('title') or '').strip()
        content = (request.form.get('content') or '').strip()
        class_id = request.form.get('target_class_id', type=int)
        target_user_id = request.form.get('target_user_id', type=int)
        target_role = (request.form.get('target_role') or '').strip()
        target_program_type = (request.form.get('target_program_type') or '').strip()
        is_active = request.form.get('is_active') == 'on'

        if not title or not content:
            flash("Judul dan isi pengumuman wajib diisi.", "warning")
            return redirect(url_for('staff.manage_announcements'))

        if target_scope not in {'ALL', 'CLASS', 'USER', 'ROLE', 'PROGRAM'}:
            flash("Target pengumuman tidak valid.", "danger")
            return redirect(url_for('staff.manage_announcements'))

        if target_scope == 'CLASS' and not class_id:
            flash("Pilih kelas tujuan terlebih dahulu.", "warning")
            return redirect(url_for('staff.manage_announcements'))

        if target_scope == 'USER' and not target_user_id:
            flash("Pilih pengguna tujuan terlebih dahulu.", "warning")
            return redirect(url_for('staff.manage_announcements'))

        if target_scope == 'ROLE' and target_role not in targetable_roles:
            flash("Pilih role tujuan terlebih dahulu.", "warning")
            return redirect(url_for('staff.manage_announcements'))

        if target_scope == 'PROGRAM' and target_program_type not in program_labels.keys():
            flash("Pilih program tujuan terlebih dahulu.", "warning")
            return redirect(url_for('staff.manage_announcements'))

        announcement = Announcement(
            title=title,
            content=content,
            is_active=is_active,
            target_scope=target_scope,
            target_class_id=class_id if target_scope == 'CLASS' else None,
            target_user_id=target_user_id if target_scope == 'USER' else None,
            target_role=target_role if target_scope == 'ROLE' else None,
            target_program_type=target_program_type if target_scope == 'PROGRAM' else None,
            user_id=current_user.id
        )
        db.session.add(announcement)
        db.session.commit()
        flash("Pengumuman berhasil dikirim.", "success")
        return redirect(url_for('staff.manage_announcements'))

    recent_announcements = Announcement.query.filter_by(user_id=current_user.id).order_by(
        Announcement.created_at.desc()
    ).limit(30).all()
    return render_template(
        'staff/announcements.html',
        classes=classes,
        users=users,
        available_roles=available_roles,
        role_labels=role_labels,
        targetable_roles=targetable_roles,
        program_labels=program_labels,
        recent_announcements=recent_announcements
    )


# =========================================================
# 2. MODUL KESISWAAN (DATA SISWA & PENEMPATAN KELAS)
# =========================================================

@staff_bp.route('/siswa/data')
@login_required
@role_required(UserRole.TU)
def list_students():
    query = (request.args.get('q') or '').strip()
    query_majlis = (request.args.get('q_majlis') or '').strip()
    active_category = (request.args.get('category') or 'all').strip().lower()

    students_query = Student.query.filter_by(is_deleted=False).outerjoin(ClassRoom, Student.current_class_id == ClassRoom.id)
    majlis_query = MajlisParticipant.query.filter_by(is_deleted=False)

    if query:
        students_query = students_query.outerjoin(Parent, Student.parent_id == Parent.id).filter(
            db.or_(
                Student.full_name.ilike(f'%{query}%'),
                Student.nis.ilike(f'%{query}%'),
                Parent.full_name.ilike(f'%{query}%'),
                Parent.phone.ilike(f'%{query}%'),
                ClassRoom.name.ilike(f'%{query}%')
            )
        )

    if query_majlis:
        majlis_query = majlis_query.outerjoin(ClassRoom, MajlisParticipant.majlis_class_id == ClassRoom.id).filter(
            db.or_(
                MajlisParticipant.full_name.ilike(f'%{query_majlis}%'),
                MajlisParticipant.phone.ilike(f'%{query_majlis}%'),
                ClassRoom.name.ilike(f'%{query_majlis}%')
            )
        )

    if active_category == 'sbq_sd':
        students_query = students_query.filter(
            or_(
                and_(
                    ClassRoom.program_type == ProgramType.SEKOLAH_FULLDAY,
                    ClassRoom.education_level == EducationLevel.SD
                ),
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%sd%'),
                        ClassRoom.grade_level.in_([1, 2, 3, 4, 5, 6])
                    )
                )
            )
        )
    elif active_category == 'sbq_smp':
        students_query = students_query.filter(
            or_(
                and_(
                    ClassRoom.program_type == ProgramType.SEKOLAH_FULLDAY,
                    ClassRoom.education_level == EducationLevel.SMP
                ),
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%smp%'),
                        ClassRoom.grade_level.in_([7, 8, 9])
                    )
                )
            )
        )
    elif active_category == 'sbq_sma':
        students_query = students_query.filter(
            or_(
                and_(
                    ClassRoom.program_type == ProgramType.SEKOLAH_FULLDAY,
                    ClassRoom.education_level == EducationLevel.SMA
                ),
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%sma%'),
                        ClassRoom.grade_level.in_([10, 11, 12])
                    )
                )
            )
        )
    elif active_category == 'reguler':
        students_query = students_query.filter(
            or_(
                ClassRoom.program_type == ProgramType.RQDF_SORE,
                and_(
                    ClassRoom.program_type.is_(None),
                    or_(
                        ClassRoom.name.ilike('%reguler%'),
                        ClassRoom.name.ilike('%rqdf%')
                    )
                )
            )
        )
    elif active_category == 'takhosus':
        students_query = students_query.filter(
            or_(
                ClassRoom.program_type == ProgramType.TAKHOSUS_TAHFIDZ,
                and_(
                    ClassRoom.program_type.is_(None),
                    ClassRoom.name.ilike('%takhosus%')
                )
            )
        )

    students = students_query.order_by(Student.id.desc()).all()
    majlis_participants = majlis_query.order_by(MajlisParticipant.id.desc()).all()

    return render_template(
        'student/list_students.html',
        students=students,
        majlis_participants=majlis_participants,
        query=query,
        query_majlis=query_majlis,
        active_category=active_category
    )


@staff_bp.route('/majlis/penempatan-kelas', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def assign_majlis_classes():
    query = (request.args.get('q') or '').strip()
    participants_query = MajlisParticipant.query.filter_by(is_deleted=False)
    if query:
        participants_query = participants_query.filter(
            or_(
                MajlisParticipant.full_name.ilike(f'%{query}%'),
                MajlisParticipant.phone.ilike(f'%{query}%')
            )
        )

    majlis_participants = participants_query.order_by(MajlisParticipant.full_name).all()
    majlis_classes = ClassRoom.query.filter_by(is_deleted=False, class_type=ClassType.MAJLIS_TALIM).order_by(ClassRoom.name).all()

    # Fallback: jika belum ada class_type khusus, tetap izinkan pilih semua kelas agar operasional tidak terblokir
    if not majlis_classes:
        majlis_classes = ClassRoom.query.filter_by(is_deleted=False).order_by(ClassRoom.name).all()

    if request.method == 'POST':
        updated = 0
        for participant in majlis_participants:
            class_id_raw = request.form.get(f'class_{participant.id}', '').strip()
            new_class_id = int(class_id_raw) if class_id_raw else None
            if participant.majlis_class_id != new_class_id:
                participant.majlis_class_id = new_class_id
                updated += 1

        db.session.commit()
        flash(f'Penempatan kelas peserta Majlis berhasil diperbarui ({updated} perubahan).', 'success')
        return redirect(url_for('staff.assign_majlis_classes'))

    return render_template(
        'staff/majlis_class_assignment.html',
        majlis_participants=majlis_participants,
        majlis_classes=majlis_classes,
        query=query
    )


@staff_bp.route('/siswa/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def edit_student(student_id):
    """TU bertugas menempatkan siswa ke kelas dan input NISN"""
    student = Student.query.get_or_404(student_id)
    classes = ClassRoom.query.all()

    if request.method == 'POST':
        student.full_name = request.form.get('full_name')
        student.nisn = request.form.get('nisn')

        class_id = request.form.get('class_id')
        student.current_class_id = int(class_id) if class_id else None

        # TU juga bisa update SPP Khusus jika ada negosiasi
        spp_input = request.form.get('custom_spp')
        if spp_input:
            student.custom_spp_fee = int(''.join(filter(str.isdigit, spp_input)))
        else:
            student.custom_spp_fee = None

        db.session.commit()
        flash('Data siswa berhasil diupdate.', 'success')
        return redirect(url_for('staff.list_students'))

    return render_template('staff/edit_student.html',
                           student=student,
                           classes=classes,)



# =========================================================
# 3. MODUL PPDB (VERIFIKASI & PENERIMAAN)
# =========================================================

@staff_bp.route('/ppdb/list')
@login_required
@role_required(UserRole.TU)
def ppdb_list():
    query = (request.args.get('q') or '').strip()
    candidates_query = StudentCandidate.query
    if query:
        candidates_query = candidates_query.filter(
            or_(
                StudentCandidate.registration_no.ilike(f'%{query}%'),
                StudentCandidate.full_name.ilike(f'%{query}%'),
                StudentCandidate.parent_phone.ilike(f'%{query}%'),
                StudentCandidate.personal_phone.ilike(f'%{query}%')
            )
        )

    candidates = candidates_query.order_by(StudentCandidate.created_at.desc()).all()
    return render_template('staff/ppdb/list.html', candidates=candidates, query=query)


@staff_bp.route('/ppdb/detail/<int:candidate_id>')
@login_required
@role_required(UserRole.TU)
def ppdb_detail(candidate_id):
    candidate = StudentCandidate.query.get_or_404(candidate_id)
    return render_template('staff/ppdb/detail.html', candidate=candidate)


@staff_bp.route('/ppdb/terima/<int:candidate_id>', methods=['POST'])  # <--- GANTI JADI staff_bp
@login_required
@role_required(UserRole.TU)
def accept_candidate(candidate_id):
    calon = StudentCandidate.query.get_or_404(candidate_id)

    if calon.status == RegistrationStatus.ACCEPTED:
        flash('Siswa ini sudah diproses sebelumnya.', 'warning')
        return redirect(url_for('staff.ppdb_detail', candidate_id=calon.id))

    try:
        # Jalur khusus peserta Majelis Ta'lim (tidak membuat akun siswa/wali)
        if calon.program_type == ProgramType.MAJLIS_TALIM:
            nomor_majelis = calon.personal_phone or calon.parent_phone
            if not nomor_majelis:
                raise ValueError('Nomor WhatsApp peserta Majelis tidak ditemukan.')

            majlis_user = User.query.filter_by(username=nomor_majelis).first()
            if not majlis_user:
                majlis_user = User(
                    username=nomor_majelis,
                    email=f"majlis.{calon.id}@sekolah.id",
                    password_hash=generate_password_hash("123456"),
                    role=UserRole.MAJLIS_PARTICIPANT,
                    must_change_password=True
                )
                db.session.add(majlis_user)
                db.session.flush()

            if not majlis_user.majlis_profile:
                db.session.add(MajlisParticipant(
                    user_id=majlis_user.id,
                    full_name=calon.full_name,
                    phone=nomor_majelis,
                    address=calon.address,
                    job=calon.personal_job,
                ))

            calon.status = RegistrationStatus.ACCEPTED
            db.session.commit()
            flash(f'Peserta Majelis {calon.full_name} berhasil diterima.', 'success')
            return redirect(url_for('staff.ppdb_detail', candidate_id=candidate_id))

        # --- 1. PROSES AKUN ---
        nis_baru = generate_nis()

        # User Wali
        user_wali = User.query.filter_by(username=calon.parent_phone).first()
        if not user_wali:
            user_wali = User(username=calon.parent_phone, email=f"wali.{nis_baru}@sekolah.id",
                             password_hash=generate_password_hash(calon.parent_phone or "123456"),
                             role=UserRole.WALI_MURID,
                             must_change_password=True)
            db.session.add(user_wali)
            db.session.flush()
            parent_profile = Parent(user_id=user_wali.id, full_name=calon.father_name, phone=calon.parent_phone,
                                    job=calon.father_job, address=calon.address)
            db.session.add(parent_profile)
            db.session.flush()
        else:
            parent_profile = user_wali.parent_profile

        # User Siswa
        user_siswa = User(username=nis_baru, email=f"{nis_baru}@sekolah.id",
                          password_hash=generate_password_hash("123456"), role=UserRole.SISWA,
                          must_change_password=True)
        db.session.add(user_siswa)
        db.session.flush()
        siswa_baru = Student(user_id=user_siswa.id, parent_id=parent_profile.id, nis=nis_baru,
                             full_name=calon.full_name, gender=calon.gender, place_of_birth=calon.place_of_birth,
                             date_of_birth=calon.date_of_birth, address=calon.address)
        db.session.add(siswa_baru)
        db.session.flush()

        # --- 2. SMART INVOICING (VERSI DINAMIS) ---
        def get_nominal(nama_biaya, harga_default):
            biaya_db = FeeType.query.filter_by(name=nama_biaya).first()
            if biaya_db:
                return biaya_db.amount
            return harga_default

        tagihan_list = []

        if calon.program_type.name == 'SEKOLAH_FULLDAY':
            if calon.scholarship_category.name == 'NON_BEASISWA':
                tagihan_list = [
                    {'nama': 'Biaya Pendaftaran', 'nominal': get_nominal('Biaya Pendaftaran', 200000)},
                    {'nama': 'Seragam Batik', 'nominal': get_nominal('Seragam Batik', 100000)},
                    {'nama': 'Infaq Bulanan (Juli)', 'nominal': get_nominal('Infaq Bulanan (Juli)', 650000)},
                    {'nama': 'Wakaf Bangunan', 'nominal': get_nominal('Wakaf Bangunan', 1000000)},
                    {'nama': 'Fasilitas Kasur', 'nominal': get_nominal('Fasilitas Kasur', 500000)},
                    {'nama': 'Orientasi Siswa', 'nominal': get_nominal('Orientasi Siswa', 150000)},
                    {'nama': 'Wakaf Perpustakaan', 'nominal': get_nominal('Wakaf Perpustakaan', 100000)},
                    {'nama': 'Infaq Qurban', 'nominal': get_nominal('Infaq Qurban', 100000)},
                    {'nama': 'Raport Pesantren', 'nominal': get_nominal('Raport Pesantren', 65000)},
                    {'nama': 'Adm Sekolah Formal', 'nominal': get_nominal('Adm Sekolah Formal', 500000)},
                    {'nama': 'Infaq Kegiatan', 'nominal': get_nominal('Infaq Kegiatan', 100000)}
                ]
            else:
                tagihan_list = [
                    {'nama': 'Biaya Pendaftaran (Beasiswa)',
                     'nominal': get_nominal('Biaya Pendaftaran (Beasiswa)', 100000)},
                    {'nama': 'Infaq Bulanan (Beasiswa)', 'nominal': get_nominal('Infaq Bulanan (Beasiswa)', 325000)},
                    {'nama': 'Wakaf Bangunan (Beasiswa)', 'nominal': get_nominal('Wakaf Bangunan (Beasiswa)', 500000)},
                    {'nama': 'Fasilitas Lemari (Beasiswa)',
                     'nominal': get_nominal('Fasilitas Lemari (Beasiswa)', 250000)},
                    {'nama': 'Fasilitas Kasur (Beasiswa)',
                     'nominal': get_nominal('Fasilitas Kasur (Beasiswa)', 250000)},
                    {'nama': 'Orientasi Siswa (Beasiswa)', 'nominal': get_nominal('Orientasi Siswa (Beasiswa)', 75000)},
                    {'nama': 'Raport', 'nominal': get_nominal('Raport', 65000)},
                    {'nama': 'Wakaf Perpustakaan (Beasiswa)',
                     'nominal': get_nominal('Wakaf Perpustakaan (Beasiswa)', 50000)},
                    {'nama': 'Infaq Kegiatan (Beasiswa)', 'nominal': get_nominal('Infaq Kegiatan (Beasiswa)', 50000)},
                    {'nama': 'Infaq Qurban (Beasiswa)', 'nominal': get_nominal('Infaq Qurban (Beasiswa)', 50000)},
                    {'nama': 'Seragam Batik', 'nominal': get_nominal('Seragam Batik', 100000)},
                    {'nama': 'Adm Sekolah Formal', 'nominal': get_nominal('Adm Sekolah Formal', 500000)}
                ]

        elif calon.program_type.name == 'RQDF_SORE':
            tagihan_list = [
                {'nama': 'Infaq Pendaftaran (RQDF)', 'nominal': get_nominal('Infaq Pendaftaran (RQDF)', 300000)},
                {'nama': 'Uang Dana Semesteran', 'nominal': get_nominal('Uang Dana Semesteran', 50000)},
                {'nama': 'Infaq Bulanan RQDF', 'nominal': get_nominal('Infaq Bulanan RQDF', 150000)},
                {'nama': 'Atribut (Syal) & Buku', 'nominal': get_nominal('Atribut (Syal) & Buku', 100000)},
                {'nama': 'Raport RQDF', 'nominal': get_nominal('Raport RQDF', 50000)}
            ]

            if calon.initial_pledge_amount and calon.initial_pledge_amount > 0:
                tagihan_list.append({'nama': 'Infaq Pembangunan Pesantren', 'nominal': calon.initial_pledge_amount})

            harga_seragam = 0
            uk = calon.uniform_size.name
            if uk in ['S', 'M']:
                harga_seragam = get_nominal('Seragam RQDF (S/M)', 345000)
            elif uk in ['L', 'XL']:
                harga_seragam = get_nominal('Seragam RQDF (L/XL)', 355000)
            elif uk == 'XXL':
                harga_seragam = get_nominal('Seragam RQDF (XXL)', 380000)

            if harga_seragam > 0:
                tagihan_list.append({'nama': f'Seragam RQDF (Ukuran {uk})', 'nominal': harga_seragam})

        due_date = datetime.now() + timedelta(days=14)
        inv_prefix = f"INV/{datetime.now().strftime('%Y%m')}/{siswa_baru.id}"

        ctr = 1
        for item in tagihan_list:
            fee_type = FeeType.query.filter_by(name=item['nama']).first()
            if not fee_type:
                fee_type = FeeType(name=item['nama'], amount=item['nominal'])
                db.session.add(fee_type)
                db.session.flush()

            new_inv = Invoice(
                invoice_number=f"{inv_prefix}/{ctr}",
                student_id=siswa_baru.id,
                fee_type_id=fee_type.id,
                total_amount=item['nominal'],
                paid_amount=0,
                status=PaymentStatus.UNPAID,
                due_date=due_date
            )
            db.session.add(new_inv)
            ctr += 1

        calon.status = RegistrationStatus.ACCEPTED
        db.session.commit()
        flash(f'Sukses! Siswa {siswa_baru.full_name} diterima. {len(tagihan_list)} rincian tagihan diterbitkan.',
              'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
        print(e)

    return redirect(url_for('staff.ppdb_detail', candidate_id=candidate_id))
