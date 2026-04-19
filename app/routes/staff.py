from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from sqlalchemy import func, or_, and_
from itsdangerous import URLSafeSerializer, BadSignature
from app.extensions import db
from app.decorators import role_required
from app.forms import PaymentForm, StudentForm  # Pastikan import ini ada
from app.services.majlis_enrollment_service import (
    assign_majlis_class,
    ensure_majlis_participant_acceptance,
    get_default_tenant_id,
    list_active_majlis_participants,
    sync_majlis_participant_profile,
)
from app.services.rumah_quran_service import (
    apply_rumah_quran_student_filter,
    assign_student_rumah_quran_class,
    get_student_rumah_quran_classroom,
    list_rumah_quran_classes,
)
from app.services.bahasa_service import (
    apply_bahasa_student_filter,
    assign_student_bahasa_class,
    get_student_bahasa_classroom,
    list_bahasa_classes,
)
from app.services.formal_service import sync_student_formal_class_membership
from app.services.ppdb_fee_service import build_candidate_fee_drafts
from app.models import (
    UserRole, User, Student, Parent, Staff, ClassRoom, Gender,
    Invoice, Transaction, PaymentStatus, FeeType,
    StudentCandidate, RegistrationStatus, ProgramType, EducationLevel,
    MajlisParticipant, ClassType, Announcement
)
from app.utils.nis import generate_nis
from app.utils.roles import get_active_role
from app.utils.money import to_rupiah_int
from app.utils.timezone import local_day_bounds_utc_naive, local_now

staff_bp = Blueprint('staff', __name__)


def _safe_students_list_return_url(next_url, fallback_endpoint='staff.list_students'):
    fallback_url = url_for(fallback_endpoint)
    if not next_url:
        return fallback_url

    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc:
        return fallback_url

    allowed_paths = {url_for('admin.list_students'), url_for('staff.list_students')}
    if parsed.path not in allowed_paths:
        return fallback_url

    return next_url


def _cashier_serializer():
    return URLSafeSerializer(current_app.config['SECRET_KEY'], salt='cashier-invoice-v1')


def _sign_cashier_invoice(invoice_id, student_id):
    return _cashier_serializer().dumps({'invoice_id': int(invoice_id), 'student_id': int(student_id)})


def _verify_cashier_invoice(token):
    try:
        data = _cashier_serializer().loads(token)
        return int(data.get('invoice_id')), int(data.get('student_id'))
    except (BadSignature, TypeError, ValueError):
        return None, None


def _parse_rupiah_input(raw_value, default_value):
    if raw_value is None:
        return default_value
    digits = ''.join(ch for ch in str(raw_value) if ch.isdigit())
    if not digits:
        return default_value
    return to_rupiah_int(digits, default=default_value)


def _candidate_fee_drafts(candidate):
    return build_candidate_fee_drafts(candidate)


def _apply_candidate_fee_overrides(drafts, source_form):
    updated = []
    for idx, item in enumerate(drafts):
        default_nominal = to_rupiah_int(item.get('nominal'))
        raw_nominal = source_form.get(f'fee_amount_{idx}')
        edited_nominal = _parse_rupiah_input(raw_nominal, default_nominal)
        if edited_nominal < 0:
            edited_nominal = 0
        updated.append({
            'nama': item.get('nama'),
            'nominal': edited_nominal,
        })
    return updated


@staff_bp.route('/dashboard')
@login_required
@role_required(UserRole.TU)
def dashboard():
    # 1. Hitung Pemasukan Hari Ini
    start_utc, end_utc = local_day_bounds_utc_naive()
    pemasukan_hari_ini = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.date >= start_utc,
        Transaction.date < end_utc
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
    students_due_map = {}
    if query:
        students = Student.query.filter(
            Student.is_deleted.is_(False),
            (Student.full_name.ilike(f'%{query}%')) |
            (Student.nis.ilike(f'%{query}%'))
        ).all()

    if students:
        student_ids = [s.id for s in students]
        due_rows = (
            db.session.query(
                Invoice.student_id,
                func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount'),
                func.coalesce(func.sum(Invoice.paid_amount), 0).label('paid_amount'),
            )
            .filter(
                Invoice.student_id.in_(student_ids),
                Invoice.is_deleted.is_(False),
                Invoice.status != PaymentStatus.PAID,
            )
            .group_by(Invoice.student_id)
            .all()
        )
        students_due_map = {
            student_id: max(0, to_rupiah_int(total_amount) - to_rupiah_int(paid_amount))
            for student_id, total_amount, paid_amount in due_rows
        }

    return render_template(
        'staff/cashier_search.html',
        students=students,
        query=query,
        students_due_map=students_due_map,
    )


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
    transactions = (
        Transaction.query.join(Invoice, Invoice.id == Transaction.invoice_id)
        .filter(Invoice.student_id == student.id, Invoice.is_deleted.is_(False))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(40)
        .all()
    )
    selected_trx_id = request.args.get('trx', type=int)
    highlighted_transaction = next((trx for trx in transactions if trx.id == selected_trx_id), None)
    invoice_tokens = {inv.id: _sign_cashier_invoice(inv.id, student.id) for inv in unpaid_invoices}
    invoice_summary = (
        db.session.query(
            func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount'),
            func.coalesce(func.sum(Invoice.paid_amount), 0).label('paid_amount'),
        )
        .filter(
            Invoice.student_id == student.id,
            Invoice.is_deleted.is_(False),
        )
        .first()
    )
    student_total_billed = to_rupiah_int(invoice_summary.total_amount if invoice_summary else 0)
    student_total_paid = to_rupiah_int(invoice_summary.paid_amount if invoice_summary else 0)
    student_total_due = max(0, student_total_billed - student_total_paid)

    form = PaymentForm()

    if request.method == 'POST':
        invoice_token = request.form.get('invoice_token', '').strip()
        invoice_id, signed_student_id = _verify_cashier_invoice(invoice_token)
        if not invoice_id or signed_student_id != student.id:
            current_app.logger.warning(
                "Cashier token mismatch user_id=%s route_student_id=%s signed_student_id=%s invoice_id=%s ip=%s",
                getattr(current_user, 'id', None), student.id, signed_student_id, invoice_id, request.remote_addr
            )
            flash('Invoice tidak valid atau tidak sesuai siswa.', 'danger')
            return redirect(url_for('staff.cashier_pay', student_id=student.id))

        if not form.validate_on_submit():
            flash('Input pembayaran tidak valid.', 'danger')
            return redirect(url_for('staff.cashier_pay', student_id=student.id))

        # Lock invoice saat proses pembayaran untuk mengurangi risiko update paralel.
        invoice = Invoice.query.filter(
            Invoice.id == invoice_id,
            Invoice.student_id == student.id,
            Invoice.is_deleted.is_(False),
            Invoice.status != PaymentStatus.PAID
        ).with_for_update().first()

        if not invoice:
            current_app.logger.warning(
                "Cashier invoice mismatch user_id=%s route_student_id=%s invoice_id=%s ip=%s",
                getattr(current_user, 'id', None), student.id, invoice_id, request.remote_addr
            )
            flash('Invoice tidak ditemukan atau tidak sesuai dengan siswa ini.', 'danger')
            return redirect(url_for('staff.cashier_pay', student_id=student.id))

        bayar = to_rupiah_int(form.amount.data)
        total_tagihan = to_rupiah_int(invoice.total_amount)
        sudah_bayar = to_rupiah_int(invoice.paid_amount)
        sisa_tagihan = max(0, total_tagihan - sudah_bayar)

        if bayar <= 0:
            flash('Jumlah pembayaran harus lebih dari 0.', 'danger')
        elif bayar > sisa_tagihan:
            flash(f'Gagal! Pembayaran melebihi sisa (Maks: {sisa_tagihan})', 'danger')
        else:
            # Catat Transaksi
            trx = Transaction(
                invoice_id=invoice.id,
                amount=bayar,
                method=form.method.data,
                pic_id=current_user.id,
            )
            db.session.add(trx)

            # Update Invoice
            invoice.paid_amount = sudah_bayar + bayar
            if invoice.paid_amount >= total_tagihan:
                invoice.paid_amount = total_tagihan
                invoice.status = PaymentStatus.PAID
            elif invoice.paid_amount > 0:
                invoice.status = PaymentStatus.PARTIAL
            else:
                invoice.status = PaymentStatus.UNPAID

            db.session.commit()
            flash(f'Pembayaran Rp {bayar:,.0f} diterima!', 'success')
            return redirect(url_for('staff.cashier_pay', student_id=student.id, trx=trx.id))

    return render_template(
        'staff/cashier_payment.html',
        student=student,
        invoices=unpaid_invoices,
        invoice_tokens=invoice_tokens,
        transactions=transactions,
        highlighted_transaction=highlighted_transaction,
        student_total_billed=student_total_billed,
        student_total_paid=student_total_paid,
        student_total_due=student_total_due,
        form=form
    )


@staff_bp.route('/kasir/kwitansi/<int:transaction_id>')
@login_required
@role_required(UserRole.TU)
def cashier_receipt(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    invoice = Invoice.query.filter_by(id=transaction.invoice_id, is_deleted=False).first()
    if invoice is None:
        abort(404)
    student = Student.query.filter_by(id=invoice.student_id, is_deleted=False).first()
    if student is None:
        abort(404)

    payment_pic = User.query.filter_by(id=transaction.pic_id).first()
    sisa_tagihan = max(0, to_rupiah_int(invoice.total_amount) - to_rupiah_int(invoice.paid_amount))

    return render_template(
        'staff/cashier_receipt.html',
        transaction=transaction,
        invoice=invoice,
        student=student,
        payment_pic=payment_pic,
        sisa_tagihan=sisa_tagihan,
    )


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
    return f"INV/{local_now().strftime('%Y%m%d%H%M%S%f')}/{fee_id}/{student_id}"


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
    due_date_default = local_now() + timedelta(days=10)
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
                total_amount=to_rupiah_int(nominal_final),
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


@staff_bp.route('/pengumuman/hapus/<int:announcement_id>', methods=['POST'])
@login_required
@role_required(UserRole.TU)
def delete_announcement(announcement_id):
    announcement = Announcement.query.filter_by(id=announcement_id, user_id=current_user.id).first()
    if not announcement:
        flash("Pengumuman tidak ditemukan atau bukan milik Anda.", "danger")
        return redirect(url_for('staff.manage_announcements'))

    try:
        announcement.is_deleted = True
        db.session.commit()
        flash("Pengumuman berhasil dihapus.", "success")
    except Exception:
        db.session.rollback()
        flash("Gagal menghapus pengumuman.", "danger")

    return redirect(url_for('staff.manage_announcements'))


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
        students_query = apply_rumah_quran_student_filter(students_query, track='reguler')
    elif active_category == 'takhosus':
        students_query = apply_rumah_quran_student_filter(students_query, track='takhosus')
    elif active_category == 'bahasa':
        students_query = apply_bahasa_student_filter(students_query)

    students = students_query.order_by(Student.id.desc()).all()
    bahasa_class_map = {}
    if active_category == 'bahasa':
        bahasa_class_map = {
            student.id: get_student_bahasa_classroom(student)
            for student in students
        }
    majlis_participants = list_active_majlis_participants(search=query_majlis)

    return render_template(
        'student/list_students.html',
        students=students,
        bahasa_class_map=bahasa_class_map,
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
    majlis_participants = list_active_majlis_participants(search=query)
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
                assign_majlis_class(participant.id, new_class_id)
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


@staff_bp.route('/majlis/peserta/edit/<int:participant_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU, UserRole.ADMIN)
def edit_majlis_participant(participant_id):
    participant = MajlisParticipant.query.filter_by(id=participant_id, is_deleted=False).first_or_404()
    active_role = get_active_role(current_user)
    list_endpoint = 'admin.list_students' if active_role == UserRole.ADMIN else 'staff.list_students'

    majlis_classes = ClassRoom.query.filter_by(
        is_deleted=False,
        class_type=ClassType.MAJLIS_TALIM
    ).order_by(ClassRoom.name).all()
    if not majlis_classes:
        majlis_classes = ClassRoom.query.filter_by(is_deleted=False).order_by(ClassRoom.name).all()
    allowed_class_ids = {cls.id for cls in majlis_classes}

    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        address = (request.form.get('address') or '').strip()
        job = (request.form.get('job') or '').strip()
        class_id_raw = (request.form.get('majlis_class_id') or '').strip()
        new_class_id = int(class_id_raw) if class_id_raw else None

        if not full_name or not phone:
            flash('Nama peserta dan nomor WhatsApp wajib diisi.', 'warning')
            return redirect(url_for('staff.edit_majlis_participant', participant_id=participant.id))

        if new_class_id and new_class_id not in allowed_class_ids:
            flash('Kelas Majlis yang dipilih tidak valid.', 'warning')
            return redirect(url_for('staff.edit_majlis_participant', participant_id=participant.id))

        if participant.user and phone != participant.phone and phone != participant.user.username:
            duplicate_user = User.query.filter(
                User.username == phone,
                User.id != participant.user_id
            ).first()
            if duplicate_user:
                flash('Nomor WhatsApp tersebut sudah digunakan akun lain.', 'danger')
                return redirect(url_for('staff.edit_majlis_participant', participant_id=participant.id))
            participant.user.username = phone

        sync_majlis_participant_profile(
            participant=participant,
            full_name=full_name,
            phone=phone,
            address=address,
        )
        participant.job = job or None
        assign_majlis_class(participant.id, new_class_id)

        db.session.commit()
        flash('Data peserta Majlis berhasil diperbarui.', 'success')
        return redirect(url_for(list_endpoint))

    return render_template(
        'staff/edit_majlis_participant.html',
        participant=participant,
        majlis_classes=majlis_classes,
        list_endpoint=list_endpoint
    )


@staff_bp.route('/siswa/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def edit_student(student_id):
    """TU bertugas menempatkan siswa ke kelas dan input NISN"""
    student = Student.query.get_or_404(student_id)
    return_url = _safe_students_list_return_url(
        request.args.get('next') or request.form.get('next'),
        fallback_endpoint='staff.list_students'
    )
    classes = ClassRoom.query.all()
    rumah_quran_classes = list_rumah_quran_classes()
    rumah_quran_class = get_student_rumah_quran_classroom(student)
    bahasa_classes = list_bahasa_classes()
    bahasa_class = get_student_bahasa_classroom(student)

    if request.method == 'POST':
        student.full_name = request.form.get('full_name')
        student.nisn = (request.form.get('nisn') or '').strip() or None

        class_id = request.form.get('class_id')
        selected_class_id = int(class_id) if class_id else None
        student.current_class_id = selected_class_id
        rumah_quran_class_id = request.form.get('rumah_quran_class_id')
        rumah_quran_class_id = int(rumah_quran_class_id) if rumah_quran_class_id else None
        bahasa_class_id = request.form.get('bahasa_class_id')
        bahasa_class_id = int(bahasa_class_id) if bahasa_class_id else None

        selected_class = ClassRoom.query.filter_by(id=selected_class_id, is_deleted=False).first() if selected_class_id else None
        if selected_class and selected_class.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ):
            rumah_quran_class_id = selected_class.id
        if selected_class and selected_class.program_type == ProgramType.BAHASA:
            bahasa_class_id = selected_class.id

        # TU juga bisa update SPP Khusus jika ada negosiasi
        spp_input = request.form.get('custom_spp')
        if spp_input:
            student.custom_spp_fee = int(''.join(filter(str.isdigit, spp_input)))
        else:
            student.custom_spp_fee = None

        try:
            sync_student_formal_class_membership(student, selected_class_id)
            assign_student_rumah_quran_class(student, rumah_quran_class_id)
            assign_student_bahasa_class(student, bahasa_class_id)
            db.session.commit()
            flash('Data siswa berhasil diupdate.', 'success')
            return redirect(return_url)
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal update data siswa: {e}', 'danger')

    return render_template('staff/edit_student.html',
                           student=student,
                           classes=classes,
                           rumah_quran_classes=rumah_quran_classes,
                           rumah_quran_class=rumah_quran_class,
                           bahasa_classes=bahasa_classes,
                           bahasa_class=bahasa_class,
                           return_url=return_url)



# =========================================================
# 3. MODUL PPDB (VERIFIKASI & PENERIMAAN)
# =========================================================

@staff_bp.route('/ppdb/list')
@login_required
@role_required(UserRole.TU)
def ppdb_list():
    query = (request.args.get('q') or '').strip()
    candidates_query = StudentCandidate.query.filter_by(is_deleted=False)
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
    candidate = StudentCandidate.query.filter_by(id=candidate_id, is_deleted=False).first_or_404()
    fee_drafts = []
    if candidate.status == RegistrationStatus.PENDING and candidate.program_type != ProgramType.MAJLIS_TALIM:
        fee_drafts = _candidate_fee_drafts(candidate)

    return render_template(
        'staff/ppdb/detail.html',
        candidate=candidate,
        fee_drafts=fee_drafts,
        fee_drafts_total=sum(item.get('nominal', 0) for item in fee_drafts),
    )


@staff_bp.route('/ppdb/terima/<int:candidate_id>', methods=['POST'])  # <--- GANTI JADI staff_bp
@login_required
@role_required(UserRole.TU)
def accept_candidate(candidate_id):
    calon = StudentCandidate.query.filter_by(id=candidate_id, is_deleted=False).first_or_404()

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
                default_tenant_id = get_default_tenant_id()
                if default_tenant_id is None:
                    raise ValueError('Tenant default tidak ditemukan.')
                majlis_user = User(
                    tenant_id=default_tenant_id,
                    username=nomor_majelis,
                    email=f"majlis.{calon.id}@sekolah.id",
                    password_hash=generate_password_hash("123456"),
                    role=UserRole.MAJLIS_PARTICIPANT,
                    must_change_password=True
                )
                db.session.add(majlis_user)
                db.session.flush()

            ensure_majlis_participant_acceptance(
                user=majlis_user,
                full_name=calon.full_name,
                phone=nomor_majelis,
                address=calon.address,
                job=calon.personal_job,
            )

            calon.status = RegistrationStatus.ACCEPTED
            db.session.commit()
            flash(f'Peserta Majelis {calon.full_name} berhasil diterima.', 'success')
            return redirect(url_for('staff.ppdb_detail', candidate_id=candidate_id))

        tenant_id = current_user.tenant_id or get_default_tenant_id()
        if tenant_id is None:
            raise ValueError('Tenant default tidak ditemukan.')

        # --- 1. PROSES AKUN ---
        nis_baru = generate_nis()

        # User Wali
        parent_phone = (calon.parent_phone or '').strip()
        if not parent_phone:
            raise ValueError('Nomor Telepon Orang Tua wajib diisi.')

        user_wali = User.query.filter_by(username=parent_phone).first()
        if not user_wali:
            user_wali = User(tenant_id=tenant_id, username=parent_phone, email=f"wali.{nis_baru}@sekolah.id",
                             password_hash=generate_password_hash(parent_phone or "123456"),
                             role=UserRole.WALI_MURID,
                             must_change_password=True)
            db.session.add(user_wali)
            db.session.flush()
        parent_profile = user_wali.parent_profile
        if not parent_profile:
            parent_profile = Parent(
                user_id=user_wali.id,
                full_name=calon.father_name or calon.mother_name or "Wali Murid",
                phone=parent_phone,
                job=calon.father_job,
                address=calon.address
            )
            db.session.add(parent_profile)
            db.session.flush()
        else:
            if not parent_profile.full_name:
                parent_profile.full_name = calon.father_name or calon.mother_name or "Wali Murid"
            if not parent_profile.phone:
                parent_profile.phone = parent_phone
            if not parent_profile.job and calon.father_job:
                parent_profile.job = calon.father_job
            if not parent_profile.address and calon.address:
                parent_profile.address = calon.address

        # User Siswa
        user_siswa = User(tenant_id=tenant_id, username=nis_baru, email=f"{nis_baru}@sekolah.id",
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
        tagihan_list = _apply_candidate_fee_overrides(_candidate_fee_drafts(calon), request.form)

        due_date = local_now() + timedelta(days=14)
        inv_prefix = f"INV/{local_now().strftime('%Y%m')}/{siswa_baru.id}"

        ctr = 1
        for item in tagihan_list:
            fee_type = FeeType.query.filter_by(name=item['nama']).first()
            if not fee_type:
                fee_type = FeeType(name=item['nama'], amount=to_rupiah_int(item['nominal']))
                db.session.add(fee_type)
                db.session.flush()

            new_inv = Invoice(
                invoice_number=f"{inv_prefix}/{ctr}",
                student_id=siswa_baru.id,
                fee_type_id=fee_type.id,
                total_amount=to_rupiah_int(item['nominal']),
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
