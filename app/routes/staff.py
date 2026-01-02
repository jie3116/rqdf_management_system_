from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import UserRole, Student, Invoice, Transaction, PaymentStatus
from app.forms import PaymentForm
from app.decorators import role_required
from datetime import datetime

staff_bp = Blueprint('staff', __name__)


@staff_bp.route('/dashboard')
@login_required
@role_required(UserRole.TU)
def dashboard():
    return render_template('staff/dashboard.html')


@staff_bp.route('/kasir', methods=['GET'])
@login_required
@role_required(UserRole.TU)
def cashier_search():
    # Halaman pencarian siswa untuk bayar
    query = request.args.get('q')
    students = []
    if query:
        # Cari berdasarkan Nama atau NIS
        students = Student.query.filter(
            (Student.full_name.ilike(f'%{query}%')) |
            (Student.nis.ilike(f'%{query}%'))
        ).all()

    return render_template('staff/cashier_search.html', students=students, query=query)


@staff_bp.route('/kasir/bayar/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.TU)
def cashier_pay(student_id):
    student = Student.query.get_or_404(student_id)
    # Ambil tagihan yang BELUM lunas saja (UNPAID atau PARTIAL)
    unpaid_invoices = Invoice.query.filter(
        Invoice.student_id == student.id,
        Invoice.status != PaymentStatus.PAID
    ).all()

    form = PaymentForm()

    # LOGIKA PEMBAYARAN
    if request.method == 'POST':
        # Kita perlu tahu invoice mana yang dibayar (dikirim via Hidden Input atau Query Param)
        invoice_id = request.form.get('invoice_id')
        invoice = Invoice.query.get(invoice_id)

        if invoice and form.validate_on_submit():
            bayar = form.amount.data

            # Cek apakah kelebihan bayar?
            sisa_tagihan = invoice.total_amount - invoice.paid_amount
            if bayar > sisa_tagihan:
                flash(f'Gagal! Pembayaran melebihi sisa tagihan (Maks: {sisa_tagihan})', 'danger')
            else:
                # 1. Catat Transaksi
                trx = Transaction(
                    invoice_id=invoice.id,
                    amount=bayar,
                    method=form.method.data,
                    pic_id=current_user.id  # Staff yang login
                )
                db.session.add(trx)

                # 2. Update Invoice
                invoice.paid_amount += bayar

                if invoice.paid_amount >= invoice.total_amount:
                    invoice.status = PaymentStatus.PAID
                else:
                    invoice.status = PaymentStatus.PARTIAL

                db.session.commit()
                flash(f'Pembayaran Rp {bayar:,.0f} Berhasil diterima!', 'success')
                return redirect(url_for('staff.cashier_pay', student_id=student.id))

    return render_template('staff/cashier_payment.html', student=student, invoices=unpaid_invoices, form=form)