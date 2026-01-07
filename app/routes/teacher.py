from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models import (
    UserRole, Teacher, Student, Grade, Subject,
    TahfidzRecord, TahfidzType, TahfidzSummary,
    ClassRoom, Schedule, GradeType, AcademicYear, Attendance, AttendanceStatus
)
from app.decorators import role_required


# Kita namakan blueprintnya 'teacher' agar konsisten
teacher_bp = Blueprint('teacher', __name__)


# ==========================================
# 1. DASHBOARD GURU
# ==========================================
@teacher_bp.route('/dashboard')
@login_required
@role_required(UserRole.GURU)
def dashboard():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()

    # 1. JADWAL HARI INI
    days_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_name = days_map[datetime.now().weekday()]

    todays_schedules = Schedule.query.filter_by(
        teacher_id=teacher.id,
        day=today_name
    ).order_by(Schedule.start_time).all()

    # 2. LOGIC PENGAJAR (Untuk Menu Input Nilai)
    # Mencari daftar unik: Kelas apa dan Mapel apa yang diajar guru ini
    teaching_assignments = db.session.query(
        ClassRoom.id, ClassRoom.name, Subject.id, Subject.name
    ).join(Schedule, Schedule.class_id == ClassRoom.id) \
        .join(Subject, Schedule.subject_id == Subject.id) \
        .filter(Schedule.teacher_id == teacher.id) \
        .distinct().all()

    # 3. LOGIC WALI KELAS
    homeroom_class = ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id).first()

    return render_template('teacher/dashboard.html',
                           teacher=teacher,
                           todays_schedules=todays_schedules,
                           teaching_assignments=teaching_assignments,
                           homeroom_class=homeroom_class)


# ==========================================
# 2. INPUT NILAI AKADEMIK (BATCH INPUT)
# ==========================================
@teacher_bp.route('/input-nilai/<int:class_id>/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_grades(class_id, subject_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()

    # SECURITY: Pastikan guru benar-benar mengajar di kelas & mapel ini
    is_authorized = Schedule.query.filter_by(
        teacher_id=teacher.id, class_id=class_id, subject_id=subject_id
    ).first()

    if not is_authorized:
        flash("Akses Ditolak: Anda tidak memiliki jadwal di kelas ini.", "danger")
        return redirect(url_for('teacher.dashboard'))

    target_class = ClassRoom.query.get_or_404(class_id)
    subject = Subject.query.get_or_404(subject_id)
    students = Student.query.filter_by(current_class_id=class_id).order_by(Student.full_name).all()

    # Cek Tahun Ajaran Aktif
    active_year = AcademicYear.query.filter_by(is_active=True).first()
    if not active_year:
        flash("Tahun ajaran aktif belum disetting Admin.", "warning")
        return redirect(url_for('teacher.dashboard'))

    # --- HANDLE POST (SIMPAN) ---
    if request.method == 'POST':
        grade_type_str = request.form.get('grade_type')  # TUGAS, UH, UTS, UAS
        grade_type = GradeType[grade_type_str]

        saved_count = 0
        try:
            for student in students:
                # Name di HTML: score_{student_id}
                input_name = f"score_{student.id}"
                score_val = request.form.get(input_name)

                # Jika input tidak kosong, simpan/update
                if score_val and score_val.strip() != '':
                    # Cek nilai lama
                    grade = Grade.query.filter_by(
                        student_id=student.id,
                        subject_id=subject.id,
                        academic_year_id=active_year.id,
                        type=grade_type
                    ).first()

                    if not grade:
                        grade = Grade(
                            student_id=student.id,
                            subject_id=subject.id,
                            academic_year_id=active_year.id,
                            teacher_id=teacher.id,
                            type=grade_type
                        )
                        db.session.add(grade)

                    grade.score = float(score_val)
                    saved_count += 1

            db.session.commit()
            flash(f"Berhasil menyimpan {saved_count} nilai {grade_type.value}.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

        return redirect(url_for('teacher.input_grades', class_id=class_id, subject_id=subject_id))

    # --- HANDLE GET (VIEW) ---
    # Ambil nilai yang sudah ada supaya tampil di form
    existing_grades = {}
    raw_grades = Grade.query.filter_by(
        subject_id=subject.id,
        academic_year_id=active_year.id
    ).filter(Grade.student_id.in_([s.id for s in students])).all()

    for g in raw_grades:
        if g.student_id not in existing_grades:
            existing_grades[g.student_id] = {}
        existing_grades[g.student_id][g.type.name] = g.score

    return render_template('teacher/input_grades.html',
                           teacher=teacher,
                           target_class=target_class,
                           subject=subject,
                           students=students,
                           existing_grades=existing_grades,
                           GradeType=GradeType)


# ==========================================
# 3. INPUT TAHFIDZ (DIPERBAHARUI)
# ==========================================
# app/routes/teacher.py

@teacher_bp.route('/input-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()

    # 1. AMBIL DAFTAR HALAQOH (KELAS) GURU TERSEBUT
    # Logic: Cari kelas di mana guru ini punya Jadwal (Schedule) atau dia sebagai Wali Kelas
    # Kita gunakan set/distinct agar tidak duplikat
    my_classes = db.session.query(ClassRoom).join(Schedule).filter(
        Schedule.teacher_id == teacher.id
    ).distinct().all()

    # Jika guru tidak punya jadwal tapi wali kelas, tambahkan kelas walinya
    if teacher.homeroom_class and teacher.homeroom_class not in my_classes:
        my_classes.append(teacher.homeroom_class)

    # 2. LOGIC FILTER SISWA BERDASARKAN KELAS YG DIPILIH
    selected_class_id = request.args.get('class_id')
    students = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        # Pastikan guru punya akses ke kelas ini (Security Check)
        if selected_class in my_classes:
            students = Student.query.filter_by(
                current_class_id=selected_class_id,
                is_deleted=False
            ).order_by(Student.full_name).all()
        else:
            flash("Anda tidak memiliki akses ke halaqoh tersebut.", "danger")
    else:
        # Jika belum pilih, defaultnya kosong atau pilih kelas pertama jika ada
        if my_classes:
            # Opsional: redirect otomatis ke kelas pertama
            # return redirect(url_for('teacher.input_tahfidz', class_id=my_classes[0].id))
            pass

    # 3. HANDLE POST (SIMPAN DATA)
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        jenis_setoran = request.form.get('type')

        # Ambil nama surat dari dropdown (bukan ketik manual lagi)
        start_surah = request.form.get('start_surah_name')  # Al-Fatihah
        end_surah = request.form.get('end_surah_name')  # An-Nas

        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        quality = request.form.get('quality')
        notes = request.form.get('notes')

        # Logic Nama Surat
        if not end_surah or start_surah == end_surah:
            final_surah_name = start_surah
        else:
            final_surah_name = f"{start_surah} - {end_surah}"

        # Simpan
        new_record = TahfidzRecord(
            student_id=student_id,
            teacher_id=teacher.id,
            type=TahfidzType[jenis_setoran],
            juz=0,  # Bisa ditambahkan logic auto-detect juz via JS nanti
            surah=final_surah_name,
            ayat_start=int(ayat_start),
            ayat_end=int(ayat_end),
            quality=quality,
            notes=notes,
            date=datetime.now()
        )
        db.session.add(new_record)

        # Update Summary (Logic Ziyadah)
        if jenis_setoran == 'ZIYADAH':
            summary = TahfidzSummary.query.filter_by(student_id=student_id).first()
            if not summary:
                summary = TahfidzSummary(student_id=student_id)
                db.session.add(summary)
            summary.last_surah = end_surah if end_surah else start_surah
            summary.last_ayat = int(ayat_end)

        db.session.commit()
        flash('Setoran berhasil disimpan!', 'success')

        # Redirect tetap di halaqoh yang sama agar enak input murid selanjutnya
        return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

    return render_template('teacher/input_tahfidz.html',
                           my_classes=my_classes,
                           students=students,
                           selected_class=selected_class)


# ==========================================
# 4. FITUR WALI KELAS
# ==========================================
@teacher_bp.route('/wali-kelas/siswa')
@login_required
@role_required(UserRole.GURU)
def homeroom_students():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    homeroom_class = ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id).first()

    if not homeroom_class:
        flash("Anda tidak terdaftar sebagai Wali Kelas.", "warning")
        return redirect(url_for('teacher.dashboard'))

    return render_template('teacher/homeroom_students.html',
                           c_class=homeroom_class,
                           students=homeroom_class.students)


# --- A. FUNGSI UTAMA: MENGOLAH NILAI ---

def calculate_student_grades(student_id):
    student = Student.query.get_or_404(student_id)
    active_year = AcademicYear.query.filter_by(is_active=True).first()

    if not active_year:
        return None, None, None  # Return 3 value sekarang

    # 1. AMBIL NILAI AKADEMIK (Logic Lama)
    raw_grades = Grade.query.filter_by(
        student_id=student.id,
        academic_year_id=active_year.id
    ).all()

    report_data = {}
    for g in raw_grades:
        subj_name = g.subject.name
        if subj_name not in report_data:
            report_data[subj_name] = {'TUGAS': [], 'UH': [], 'UTS': 0, 'UAS': 0, 'KKM': g.subject.kkm}

        if g.type.name in ['TUGAS', 'UH']:
            report_data[subj_name][g.type.name].append(g.score)
        elif g.type.name in ['UTS', 'UAS']:
            report_data[subj_name][g.type.name] = g.score

    final_report = []
    for subj_name, data in report_data.items():
        avg_tugas = sum(data['TUGAS']) / len(data['TUGAS']) if data['TUGAS'] else 0
        avg_uh = sum(data['UH']) / len(data['UH']) if data['UH'] else 0

        if data['TUGAS'] and data['UH']:
            nilai_harian = (avg_tugas + avg_uh) / 2
        else:
            nilai_harian = avg_tugas if data['TUGAS'] else avg_uh

        nilai_uts = data['UTS']
        nilai_uas = data['UAS']
        final_score = (nilai_harian * 0.3) + (nilai_uts * 0.3) + (nilai_uas * 0.4)

        if final_score >= 92:
            predikat = 'A'
        elif final_score >= 83:
            predikat = 'B'
        elif final_score >= 75:
            predikat = 'C'
        else:
            predikat = 'D'

        final_report.append({
            'subject': subj_name,
            'kkm': data['KKM'],
            'harian': round(nilai_harian, 0),
            'uts': nilai_uts,
            'uas': nilai_uas,
            'final': round(final_score, 0),
            'predikat': predikat
        })

    # 2. HITUNG ABSENSI (LOGIC BARU)
    # Kita hitung berapa kali Sakit, Izin, Alpa di tahun ajaran ini
    attendance_stats = {
        'sakit': Attendance.query.filter_by(student_id=student.id, academic_year_id=active_year.id,
                                            status=AttendanceStatus.SAKIT).count(),
        'izin': Attendance.query.filter_by(student_id=student.id, academic_year_id=active_year.id,
                                           status=AttendanceStatus.IZIN).count(),
        'alpa': Attendance.query.filter_by(student_id=student.id, academic_year_id=active_year.id,
                                           status=AttendanceStatus.ALPA).count(),
    }

    return final_report, active_year, attendance_stats

# --- B. ROUTE CETAK RAPORT UTAMA (RINGKAS) ---
@teacher_bp.route('/wali-kelas/raport/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def print_report_card(student_id):
    # Validasi Wali Kelas
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)
    if student.current_class.homeroom_teacher_id != teacher.id:
        flash("Akses Ditolak.", "danger")
        return redirect(url_for('teacher.dashboard'))

    # Panggil fungsi helper hitung-hitungan di atas
    final_report, active_year, attendance_stats = calculate_student_grades(student_id)

    if final_report is None:
        return "Tahun ajaran belum aktif", 404

    return render_template('teacher/print_report.html',
                           student=student,
                           final_report=final_report,
                           academic_year=active_year,
                           attendance_stats=attendance_stats)  # Kirim ke HTML


# --- C. ROUTE CETAK LAMPIRAN (DETAIL) ---
@teacher_bp.route('/wali-kelas/lampiran/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def print_attachment(student_id):
    # Validasi Wali Kelas (Sama)
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)

    final_report, active_year, attendance_stats = calculate_student_grades(student_id)

    return render_template('teacher/print_attachment.html',
                           student=student,
                           final_report=final_report,
                           academic_year=active_year,
                           attendance_stats=attendance_stats)


@teacher_bp.route('/input-absensi/<int:class_id>', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_attendance(class_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    target_class = ClassRoom.query.get_or_404(class_id)
    active_year = AcademicYear.query.filter_by(is_active=True).first()

    # 1. Validasi Akses (Hanya Guru yg punya Jadwal atau Wali Kelas)
    has_schedule = Schedule.query.filter_by(teacher_id=teacher.id, class_id=class_id).first()
    is_homeroom = (target_class.homeroom_teacher_id == teacher.id)

    if not has_schedule and not is_homeroom:
        flash("Akses Ditolak: Anda tidak mengajar di kelas ini.", "danger")
        return redirect(url_for('teacher.dashboard'))

    # 2. Setup Tanggal
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # 3. Ambil Siswa Aktif di Kelas Tersebut
    students = Student.query.filter_by(current_class_id=class_id, is_deleted=False).order_by(Student.full_name).all()

    # 4. HANDLE POST (SIMPAN DATA)
    if request.method == 'POST':
        saved_count = 0
        try:
            for student in students:
                # Ambil input dari form (format name="status_ID")
                status_val = request.form.get(f"status_{student.id}")
                note_val = request.form.get(f"note_{student.id}")

                if status_val:
                    # Cek apakah data lama sudah ada? (Update vs Insert)
                    attendance = Attendance.query.filter_by(
                        student_id=student.id,
                        date=selected_date,
                        class_id=class_id
                    ).first()

                    if not attendance:
                        attendance = Attendance(
                            student_id=student.id,
                            class_id=class_id,
                            teacher_id=teacher.id,
                            date=selected_date,
                            academic_year_id=active_year.id if active_year else None
                        )
                        db.session.add(attendance)

                    # Update data
                    attendance.status = AttendanceStatus[status_val]  # Convert string ke Enum
                    attendance.notes = note_val
                    attendance.teacher_id = teacher.id  # Update siapa yang edit terakhir
                    saved_count += 1

            db.session.commit()
            flash(f"Absensi tanggal {date_str} berhasil disimpan.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

        return redirect(url_for('teacher.input_attendance', class_id=class_id, date=date_str))

    # 5. HANDLE GET (TAMPILKAN DATA EXISTING)
    # Agar radio button ter-centang sesuai data database
    existing_data = {}
    records = Attendance.query.filter_by(class_id=class_id, date=selected_date).all()
    for r in records:
        existing_data[r.student_id] = {'status': r.status.name, 'notes': r.notes}

    return render_template('teacher/input_attendance.html',
                           target_class=target_class,
                           students=students,
                           selected_date=date_str,
                           existing_data=existing_data,
                           AttendanceStatus=AttendanceStatus)  # Kirim Enum ke template