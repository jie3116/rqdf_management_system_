from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from collections import defaultdict
from app.models import (
    Teacher, Student, ClassRoom, TahfidzRecord, TahfidzSummary, RecitationRecord,
    TahfidzEvaluation, TahfidzType, RecitationSource, ParticipantType, Grade, 
    GradeType, Subject, Attendance, AttendanceStatus, AcademicYear, db, UserRole
)
from app.decorators import role_required

teacher_bp = Blueprint('teacher', __name__)


def _get_teacher_classes(teacher):
    """Helper: Ambil semua kelas yang diajar atau dibina guru ini."""
    classes = set()
    
    # 1. Kelas sebagai Wali Kelas
    if teacher.homeroom_class:
        classes.add(teacher.homeroom_class)
    
    # 2. Kelas dari Jadwal Mengajar (jika ada relasi schedule)
    # classes.update(teacher.teaching_schedules) 
    
    # 3. Semua kelas untuk sementara (bisa dibatasi nanti)
    all_classes = ClassRoom.query.filter_by(is_deleted=False).all()
    classes.update(all_classes)
    
    return list(classes)


@teacher_bp.route('/dashboard')
@login_required
@role_required(UserRole.GURU)
def dashboard():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Quick Stats
    my_classes = _get_teacher_classes(teacher)
    class_ids = [c.id for c in my_classes]
    
    # Hitung siswa aktif di kelas yang diajar
    total_students = Student.query.filter(
        Student.current_class_id.in_(class_ids),
        Student.is_deleted == False
    ).count() if class_ids else 0
    
    # Tahfidz records hari ini
    today = datetime.now().date()
    today_tahfidz = TahfidzRecord.query.filter(
        TahfidzRecord.teacher_id == teacher.id,
        db.func.date(TahfidzRecord.date) == today
    ).count()
    
    # Recitation records hari ini  
    today_recitation = RecitationRecord.query.filter(
        RecitationRecord.teacher_id == teacher.id,
        db.func.date(RecitationRecord.date) == today
    ).count()
    
    # Recent activities (gabungan tahfidz + recitation)
    recent_tahfidz = TahfidzRecord.query.filter_by(teacher_id=teacher.id)\
        .order_by(TahfidzRecord.date.desc()).limit(5).all()
    
    recent_recitation = RecitationRecord.query.filter_by(teacher_id=teacher.id)\
        .order_by(RecitationRecord.date.desc()).limit(5).all()

    return render_template('teacher/dashboard.html',
                         teacher=teacher,
                         my_classes=my_classes,
                         total_students=total_students,
                         today_tahfidz=today_tahfidz,
                         today_recitation=today_recitation,
                         recent_tahfidz=recent_tahfidz,
                         recent_recitation=recent_recitation)


@teacher_bp.route('/input-nilai', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_grades():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)
    
    selected_class_id = request.args.get('class_id')
    selected_subject_id = request.args.get('subject_id')
    students = []
    selected_class = None
    subjects = Subject.query.filter_by(is_deleted=False).all()
    
    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students = Student.query.filter_by(
                current_class_id=selected_class_id,
                is_deleted=False
            ).order_by(Student.full_name).all()
    
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        grade_type = request.form.get('grade_type')
        notes = request.form.get('notes', '')
        
        active_year = AcademicYear.query.filter_by(is_active=True).first()
        if not active_year:
            flash('Tahun ajaran aktif belum diatur.', 'warning')
            return redirect(url_for('teacher.input_grades'))
        
        success_count = 0
        for student in students:
            score_key = f'score_{student.id}'
            score = request.form.get(score_key)
            
            if score and score.strip():
                try:
                    score_float = float(score)
                    
                    # Cek apakah sudah ada nilai untuk kombinasi ini
                    existing = Grade.query.filter_by(
                        student_id=student.id,
                        subject_id=subject_id,
                        academic_year_id=active_year.id,
                        type=GradeType[grade_type],
                        teacher_id=teacher.id
                    ).first()
                    
                    if existing:
                        existing.score = score_float
                        existing.notes = notes
                    else:
                        new_grade = Grade(
                            student_id=student.id,
                            subject_id=subject_id,
                            academic_year_id=active_year.id,
                            teacher_id=teacher.id,
                            type=GradeType[grade_type],
                            score=score_float,
                            notes=notes
                        )
                        db.session.add(new_grade)
                    
                    success_count += 1
                except ValueError:
                    continue
        
        if success_count > 0:
            db.session.commit()
            flash(f'Berhasil menyimpan {success_count} nilai!', 'success')
        else:
            flash('Tidak ada nilai yang berhasil disimpan.', 'warning')
        
        return redirect(url_for('teacher.input_grades', 
                              class_id=selected_class_id, 
                              subject_id=selected_subject_id))
    
    return render_template('teacher/input_grades.html',
                         my_classes=my_classes,
                         students=students,
                         selected_class=selected_class,
                         subjects=subjects,
                         selected_subject_id=selected_subject_id,
                         grade_types=GradeType)


@teacher_bp.route('/input-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id')
    students = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students = Student.query.filter_by(
                current_class_id=selected_class_id,
                is_deleted=False
            ).order_by(Student.full_name).all()
        else:
            flash("Anda tidak memiliki akses ke halaqoh tersebut.", "danger")

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        jenis_setoran = request.form.get('jenis_setoran')  # ZIYADAH atau MURAJAAH

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        notes = request.form.get('notes')
        
        tajwid_errors = int(request.form.get('tajwid_errors') or 0)
        makhraj_errors = int(request.form.get('makhraj_errors') or 0)
        tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)

        # Validasi jenis setoran
        if jenis_setoran not in [t.name for t in TahfidzType]:
            flash("Jenis setoran tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        # Logic nama surah final
        final_surah_name = None
        if not end_surah or start_surah == end_surah:
            final_surah_name = start_surah
        else:
            final_surah_name = f"{start_surah} - {end_surah}"

        # Hitung skor berdasarkan kesalahan
        total_errors = tajwid_errors + makhraj_errors + tahfidz_errors
        score = max(0, 100 - (total_errors * 2))

        new_record = TahfidzRecord(
            student_id=student_id,
            participant_type=ParticipantType.STUDENT,
            teacher_id=teacher.id,
            type=TahfidzType[jenis_setoran],
            juz=0,  # Bisa ditambahkan logic auto-detect juz via JS nanti
            surah=final_surah_name,
            ayat_start=int(ayat_start),
            ayat_end=int(ayat_end),
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            tahfidz_errors=tahfidz_errors,
            score=score,
            notes=notes,
            date=datetime.now()
        )
        db.session.add(new_record)

        # Update Summary
        summary = TahfidzSummary.query.filter_by(
            student_id=student_id, 
            participant_type=ParticipantType.STUDENT
        ).first()
        if not summary:
            summary = TahfidzSummary(
                student_id=student_id,
                participant_type=ParticipantType.STUDENT
            )
            db.session.add(summary)

        # Update last_surah dan last_ayat jika ini Ziyadah
        if jenis_setoran == 'ZIYADAH':
            summary.last_surah = final_surah_name
            summary.last_ayat = int(ayat_end)

        db.session.commit()
        flash('Setoran tahfidz berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

    return render_template('teacher/input_tahfidz.html',
                           my_classes=my_classes,
                           students=students,
                           selected_class=selected_class,
                           tahfidz_types=TahfidzType)


@teacher_bp.route('/input-bacaan', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_recitation():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id')
    students = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students = Student.query.filter_by(
                current_class_id=selected_class_id,
                is_deleted=False
            ).order_by(Student.full_name).all()
        else:
            flash("Anda tidak memiliki akses ke halaqoh tersebut.", "danger")

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        recitation_source = request.form.get('recitation_source', 'QURAN')

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        book_name = request.form.get('book_name')
        page_start = request.form.get('page_start')
        page_end = request.form.get('page_end')
        notes = request.form.get('notes')
        tajwid_errors = int(request.form.get('tajwid_errors') or 0)
        makhraj_errors = int(request.form.get('makhraj_errors') or 0)

        final_surah_name = None
        final_ayat_start = None
        final_ayat_end = None
        final_page_start = None
        final_page_end = None

        # Validasi recitation source
        if recitation_source not in [s.name for s in RecitationSource]:
            flash("Sumber bacaan tidak valid.", "danger")
            return redirect(url_for('teacher.input_recitation', class_id=selected_class_id))

        if recitation_source == 'QURAN':
            if not end_surah or start_surah == end_surah:
                final_surah_name = start_surah
            else:
                final_surah_name = f"{start_surah} - {end_surah}"
            final_ayat_start = int(ayat_start)
            final_ayat_end = int(ayat_end)
        else:  # BOOK
            final_page_start = int(page_start) if page_start else None
            final_page_end = int(page_end) if page_end else None

        score = max(0, 100 - ((tajwid_errors + makhraj_errors) * 2))

        new_record = RecitationRecord(
            student_id=student_id,
            participant_type=ParticipantType.STUDENT,
            teacher_id=teacher.id,
            recitation_source=RecitationSource[recitation_source],
            surah=final_surah_name,
            ayat_start=final_ayat_start,
            ayat_end=final_ayat_end,
            book_name=book_name,
            page_start=final_page_start,
            page_end=final_page_end,
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            score=score,
            notes=notes,
            date=datetime.now()
        )
        db.session.add(new_record)
        db.session.commit()
        flash('Setoran bacaan berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_recitation', class_id=selected_class_id))

    return render_template('teacher/input_recitation.html',
                           my_classes=my_classes,
                           students=students,
                           selected_class=selected_class,
                           recitation_sources=RecitationSource)


@teacher_bp.route('/input-evaluasi-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz_evaluation():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id')
    students = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students = Student.query.filter_by(
                current_class_id=selected_class_id,
                is_deleted=False
            ).order_by(Student.full_name).all()

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        period_type = request.form.get('period_type')
        period_label = request.form.get('period_label')
        
        makhraj_errors = int(request.form.get('makhraj_errors') or 0)
        tajwid_errors = int(request.form.get('tajwid_errors') or 0)
        harakat_errors = int(request.form.get('harakat_errors') or 0)
        tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)
        notes = request.form.get('notes')

        total_errors = makhraj_errors + tajwid_errors + harakat_errors + tahfidz_errors
        score = max(0, 100 - (total_errors * 2))

        new_evaluation = TahfidzEvaluation(
            student_id=student_id,
            participant_type=ParticipantType.STUDENT,
            teacher_id=teacher.id,
            period_type=period_type,
            period_label=period_label,
            makhraj_errors=makhraj_errors,
            tajwid_errors=tajwid_errors,
            harakat_errors=harakat_errors,
            tahfidz_errors=tahfidz_errors,
            score=score,
            notes=notes,
            date=datetime.now()
        )
        db.session.add(new_evaluation)
        db.session.commit()
        
        flash('Evaluasi tahfidz berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=selected_class_id))

    return render_template('teacher/input_tahfidz_evaluation.html',
                           my_classes=my_classes,
                           students=students,
                           selected_class=selected_class)


@teacher_bp.route('/siswa-wali-kelas')
@login_required
@role_required(UserRole.GURU)
def homeroom_students():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    if not teacher.homeroom_class:
        flash("Anda belum ditugaskan sebagai wali kelas.", "warning")
        return redirect(url_for('teacher.dashboard'))
    
    students = Student.query.filter_by(
        current_class_id=teacher.homeroom_class.id,
        is_deleted=False
    ).order_by(Student.full_name).all()
    
    return render_template('teacher/homeroom_students.html',
                         teacher=teacher,
                         students=students,
                         homeroom_class=teacher.homeroom_class)


@teacher_bp.route('/hitung-nilai-siswa/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def calculate_student_grades(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)
    
    # Cek akses
    my_classes = _get_teacher_classes(teacher)
    if student.current_class not in my_classes:
        flash("Anda tidak memiliki akses ke siswa tersebut.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    active_year = AcademicYear.query.filter_by(is_active=True).first()
    if not active_year:
        flash('Tahun ajaran aktif belum diatur.', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Ambil semua nilai siswa di tahun aktif
    grades = Grade.query.filter_by(
        student_id=student_id,
        academic_year_id=active_year.id
    ).all()
    
    # Group by subject
    grades_by_subject = defaultdict(list)
    for grade in grades:
        grades_by_subject[grade.subject].append(grade)
    
    # Hitung rata-rata per mapel
    subject_averages = {}
    for subject, subject_grades in grades_by_subject.items():
        type_scores = defaultdict(list)
        for grade in subject_grades:
            type_scores[grade.type].append(grade.score)
        
        # Rata-rata per tipe
        type_averages = {}
        for grade_type, scores in type_scores.items():
            type_averages[grade_type.value] = sum(scores) / len(scores)
        
        # Bobot sederhana (bisa dikustomisasi)
        weights = {'Tugas': 0.3, 'UH': 0.2, 'UTS': 0.25, 'UAS': 0.25}
        
        total_weighted = 0
        total_weight = 0
        for type_name, avg_score in type_averages.items():
            weight = weights.get(type_name, 0)
            total_weighted += avg_score * weight
            total_weight += weight
        
        if total_weight > 0:
            subject_averages[subject.name] = round(total_weighted / total_weight, 2)
        else:
            subject_averages[subject.name] = 0
    
    return render_template('teacher/student_grades_calculation.html',
                         student=student,
                         grades_by_subject=grades_by_subject,
                         subject_averages=subject_averages,
                         active_year=active_year)


@teacher_bp.route('/cetak-raport/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def print_report_card(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Cek akses wali kelas
    if not teacher.homeroom_class:
        flash("Hanya wali kelas yang dapat mencetak raport.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    if student.current_class_id != teacher.homeroom_class.id:
        flash("Siswa tidak ada di kelas Anda.", "danger")
        return redirect(url_for('teacher.homeroom_students'))
    
    # Logic cetak raport (simplified)
    active_year = AcademicYear.query.filter_by(is_active=True).first()
    
    return render_template('teacher/print_report_card.html',
                         student=student,
                         teacher=teacher,
                         active_year=active_year)


@teacher_bp.route('/cetak-lampiran/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def print_attachment(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)
    
    # Get tahfidz records for attachment
    tahfidz_records = TahfidzRecord.query.filter_by(
        student_id=student_id,
        participant_type=ParticipantType.STUDENT
    ).order_by(TahfidzRecord.date.desc()).all()
    
    # Get recitation records
    recitation_records = RecitationRecord.query.filter_by(
        student_id=student_id,
        participant_type=ParticipantType.STUDENT
    ).order_by(RecitationRecord.date.desc()).all()
    
    return render_template('teacher/print_attachment.html',
                         student=student,
                         teacher=teacher,
                         tahfidz_records=tahfidz_records,
                         recitation_records=recitation_records)


@teacher_bp.route('/input-absensi', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_attendance():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)
    
    selected_class_id = request.args.get('class_id')
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    students = []
    selected_class = None
    existing_attendance = {}
    
    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students = Student.query.filter_by(
                current_class_id=selected_class_id,
                is_deleted=False
            ).order_by(Student.full_name).all()
            
            # Cek absensi yang sudah ada
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            attendances = Attendance.query.filter_by(
                class_id=selected_class_id,
                date=date_obj,
                participant_type=ParticipantType.STUDENT
            ).all()
            
            existing_attendance = {att.student_id: att.status for att in attendances}
    
    if request.method == 'POST':
        date_str = request.form.get('attendance_date')
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        active_year = AcademicYear.query.filter_by(is_active=True).first()
        
        for student in students:
            status_key = f'status_{student.id}'
            status = request.form.get(status_key)
            notes_key = f'notes_{student.id}'
            notes = request.form.get(notes_key, '')
            
            if status:
                # Cek apakah sudah ada record
                existing = Attendance.query.filter_by(
                    student_id=student.id,
                    class_id=selected_class_id,
                    date=date_obj,
                    participant_type=ParticipantType.STUDENT
                ).first()
                
                if existing:
                    existing.status = AttendanceStatus[status]
                    existing.notes = notes
                else:
                    new_attendance = Attendance(
                        student_id=student.id,
                        participant_type=ParticipantType.STUDENT,
                        class_id=selected_class_id,
                        teacher_id=teacher.id,
                        academic_year_id=active_year.id if active_year else None,
                        date=date_obj,
                        status=AttendanceStatus[status],
                        notes=notes
                    )
                    db.session.add(new_attendance)
        
        db.session.commit()
        flash('Absensi berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_attendance', 
                              class_id=selected_class_id, 
                              date=date_str))
    
    return render_template('teacher/input_attendance.html',
                         my_classes=my_classes,
                         students=students,
                         selected_class=selected_class,
                         selected_date=selected_date,
                         existing_attendance=existing_attendance,
                         attendance_statuses=AttendanceStatus)