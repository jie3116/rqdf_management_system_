from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from collections import defaultdict
from app.models import (
    Teacher, Student, ClassRoom, TahfidzRecord, TahfidzSummary, RecitationRecord,
    TahfidzEvaluation, TahfidzType, RecitationSource, ParticipantType, Grade,
    EvaluationPeriod,
    GradeType, Subject, Attendance, AttendanceStatus, AcademicYear, Schedule, db, UserRole, MajlisParticipant
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


def _get_class_participants(class_id):
    students = Student.query.filter_by(
        current_class_id=class_id,
        is_deleted=False
    ).order_by(Student.full_name).all()
    majlis_participants = MajlisParticipant.query.filter_by(
        majlis_class_id=class_id,
        is_deleted=False
    ).order_by(MajlisParticipant.full_name).all()
    return students, majlis_participants


def _parse_participant_key(participant_key):
    if not participant_key:
        return None, None

    if '-' in participant_key:
        prefix, raw_id = participant_key.split('-', 1)
        try:
            participant_id = int(raw_id)
        except ValueError:
            return None, None

        if prefix == 'S':
            return ParticipantType.STUDENT, participant_id
        if prefix == 'M':
            return ParticipantType.EXTERNAL_MAJLIS, participant_id
        return None, None

    # Backward-compatible: nilai lama hanya student_id integer
    try:
        return ParticipantType.STUDENT, int(participant_key)
    except (TypeError, ValueError):
        return None, None

@teacher_bp.route('/dashboard')
@login_required
@role_required(UserRole.GURU)
def dashboard():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()

    my_classes = _get_teacher_classes(teacher)
    class_ids = [c.id for c in my_classes]

    total_students = Student.query.filter(
        Student.current_class_id.in_(class_ids),
        Student.is_deleted == False
    ).count() if class_ids else 0

    today = datetime.now().date()
    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_name = today_name_map[today.weekday()]

    todays_schedules = Schedule.query.filter_by(
        teacher_id=teacher.id,
        day=today_name,
        is_deleted=False
    ).order_by(Schedule.start_time).all()

    teaching_assignments = []
    seen_assignments = set()
    all_teacher_schedules = Schedule.query.filter_by(teacher_id=teacher.id, is_deleted=False).all()
    for sch in all_teacher_schedules:
        if not sch.class_room or not sch.subject:
            continue
        key = (sch.class_id, sch.subject_id)
        if key in seen_assignments:
            continue
        seen_assignments.add(key)
        teaching_assignments.append((sch.class_id, sch.class_room.name, sch.subject_id, sch.subject.name))

    homeroom_class = teacher.homeroom_class

    today_tahfidz = TahfidzRecord.query.filter(
        TahfidzRecord.teacher_id == teacher.id,
        db.func.date(TahfidzRecord.date) == today
    ).count()

    today_recitation = RecitationRecord.query.filter(
        RecitationRecord.teacher_id == teacher.id,
        db.func.date(RecitationRecord.date) == today
    ).count()

    recent_tahfidz = TahfidzRecord.query.filter_by(teacher_id=teacher.id)        .order_by(TahfidzRecord.date.desc()).limit(5).all()

    recent_recitation = RecitationRecord.query.filter_by(teacher_id=teacher.id)        .order_by(RecitationRecord.date.desc()).limit(5).all()

    return render_template('teacher/dashboard.html',
                         teacher=teacher,
                         my_classes=my_classes,
                         total_students=total_students,
                         today_tahfidz=today_tahfidz,
                         today_recitation=today_recitation,
                         recent_tahfidz=recent_tahfidz,
                         recent_recitation=recent_recitation,
                         todays_schedules=todays_schedules,
                         homeroom_class=homeroom_class,
                         teaching_assignments=teaching_assignments)


@teacher_bp.route('/input-nilai', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_grades():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    selected_subject_id = request.args.get('subject_id', type=int)
    students = []
    target_class = None
    subject = Subject.query.get(selected_subject_id) if selected_subject_id else None

    if selected_class_id:
        target_class = ClassRoom.query.get(selected_class_id)
        if target_class in my_classes:
            students = Student.query.filter_by(current_class_id=selected_class_id, is_deleted=False).order_by(Student.full_name).all()

    active_year = AcademicYear.query.filter_by(is_active=True).first()
    existing_grades = {}
    if active_year and selected_subject_id and students:
        for g in Grade.query.filter_by(subject_id=selected_subject_id, academic_year_id=active_year.id).filter(Grade.student_id.in_([s.id for s in students])).all():
            existing_grades.setdefault(g.student_id, {})[g.type.name] = g.score
    
    if request.method == 'POST':
        if not active_year:
            flash('Tahun ajaran aktif belum diatur.', 'warning')
            return redirect(url_for('teacher.input_grades', class_id=selected_class_id, subject_id=selected_subject_id))

        grade_type = request.form.get('grade_type')
        notes = request.form.get('notes', '')
        subject_id = selected_subject_id or request.form.get('subject_id', type=int)
        
        success_count = 0
        for student in students:
            score = request.form.get(f'score_{student.id}')
            if not score or not score.strip():
                continue
            try:
                score_float = float(score)
            except ValueError:
                continue

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
                db.session.add(Grade(
                    student_id=student.id,
                    subject_id=subject_id,
                    academic_year_id=active_year.id,
                    teacher_id=teacher.id,
                    type=GradeType[grade_type],
                    score=score_float,
                    notes=notes
                ))
            success_count += 1

        if success_count:
            db.session.commit()
            flash(f'Berhasil menyimpan {success_count} nilai!', 'success')
        else:
            flash('Tidak ada nilai yang berhasil disimpan.', 'warning')

        return redirect(url_for('teacher.input_grades', class_id=selected_class_id, subject_id=selected_subject_id))
    
    return render_template('teacher/input_grades.html',
                           my_classes=my_classes,
                           students=students,
                           target_class=target_class,
                           subject=subject,
                           existing_grades=existing_grades)


@teacher_bp.route('/input-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke halaqoh tersebut.", "danger")

    if request.method == 'POST':
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        jenis_setoran = request.form.get('jenis_setoran') or request.form.get('type')  # backward-compatible

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        notes = request.form.get('notes')

        tajwid_errors = int(request.form.get('tajwid_errors') or 0)
        makhraj_errors = int(request.form.get('makhraj_errors') or 0)
        tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if jenis_setoran not in [t.name for t in TahfidzType]:
            flash("Jenis setoran tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        final_surah_name = start_surah if(not end_surah or start_surah == end_surah) else f"{start_surah} - {end_surah}"

        total_errors = tajwid_errors + makhraj_errors + tahfidz_errors
        calculated_score = max(0, 100 - (total_errors * 2))
        score = int(request.form.get('score_preview') or calculated_score)
        quality = request.form.get('quality')

        new_record = TahfidzRecord(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type,
            teacher_id=teacher.id,
            type=TahfidzType[jenis_setoran],
            juz=0,
            surah=final_surah_name,
            ayat_start=int(ayat_start),
            ayat_end=int(ayat_end),
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            tahfidz_errors=tahfidz_errors,
            score=score,
            quality=quality,
            notes=notes,
            date=datetime.now()
        )
        db.session.add(new_record)

        summary = TahfidzSummary.query.filter_by(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type
        ).first()
        if not summary:
            summary = TahfidzSummary(
                student_id=student_id,
                majlis_participant_id=majlis_participant_id,
                participant_type=participant_type
            )
            db.session.add(summary)

        if jenis_setoran == 'ZIYADAH':
            summary.last_surah = final_surah_name
            summary.last_ayat = int(ayat_end)

        db.session.commit()
        flash('Setoran tahfidz berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

    return render_template('teacher/input_tahfidz.html',
                           my_classes=my_classes,
                           students=students,
                           majlis_participants=majlis_participants,
                           selected_class=selected_class,
                           tahfidz_types=TahfidzType)


@teacher_bp.route('/input-bacaan', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_recitation():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        form_class_id = request.form.get('class_id', type=int)
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        recitation_source = request.form.get('recitation_source', 'QURAN')

        active_class_id = form_class_id or selected_class_id

        if recitation_source not in [s.name for s in RecitationSource]:
            flash("Sumber bacaan tidak valid.", "danger")
            return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if participant_type == ParticipantType.STUDENT:
            student = Student.query.filter_by(id=student_id, is_deleted=False).first()
            if not student:
                flash("Data siswa tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))
            if active_class_id and student.current_class_id != active_class_id:
                flash("Siswa tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))
        else:
            participant = MajlisParticipant.query.filter_by(id=majlis_participant_id, is_deleted=False).first()
            if not participant:
                flash("Data peserta majlis tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))
            if active_class_id and participant.majlis_class_id != active_class_id:
                flash("Peserta majlis tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        book_name = request.form.get('book_name')
        page_start = request.form.get('page_start')
        page_end = request.form.get('page_end')
        notes = request.form.get('notes')

        try:
            tajwid_errors = int(request.form.get('tajwid_errors') or 0)
            makhraj_errors = int(request.form.get('makhraj_errors') or 0)
        except ValueError:
            flash("Input jumlah kesalahan harus berupa angka.", "danger")
            return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        final_surah_name = None
        final_ayat_start = None
        final_ayat_end = None
        final_page_start = None
        final_page_end = None

        if recitation_source == 'QURAN':
            if not start_surah or not ayat_start or not ayat_end:
                flash("Untuk setoran Al-Qur'an, surat dan ayat wajib diisi.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            try:
                final_ayat_start = int(ayat_start)
                final_ayat_end = int(ayat_end)
            except ValueError:
                flash("Ayat awal/akhir harus berupa angka.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            if final_ayat_end < final_ayat_start:
                flash("Ayat akhir tidak boleh lebih kecil dari ayat awal.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            final_surah_name = start_surah if (not end_surah or start_surah == end_surah) else f"{start_surah} - {end_surah}"

        else:
            if not book_name:
                flash("Nama kitab/buku wajib diisi untuk setoran jenis kitab.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            try:
                final_page_start = int(page_start) if page_start else None
                final_page_end = int(page_end) if page_end else None
            except ValueError:
                flash("Halaman awal/akhir harus berupa angka.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            if final_page_start and final_page_end and final_page_end < final_page_start:
                flash("Halaman akhir tidak boleh lebih kecil dari halaman awal.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        score = max(0, 100 - ((tajwid_errors + makhraj_errors) * 2))

        new_record = RecitationRecord(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type,
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
        return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

    return render_template('teacher/input_recitation.html',
                           my_classes=my_classes,
                           students=students,
                           majlis_participants=majlis_participants,
                           selected_class=selected_class,
                           recitation_sources=RecitationSource)


@teacher_bp.route('/input-evaluasi-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz_evaluation():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        form_class_id = request.form.get('class_id', type=int)
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        period_type = request.form.get('period_type')
        period_label = request.form.get('period_label')
        notes = request.form.get('notes')

        active_class_id = form_class_id or selected_class_id

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        if period_type not in [p.name for p in EvaluationPeriod]:
            flash("Periode evaluasi tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if participant_type == ParticipantType.STUDENT:
            student = Student.query.filter_by(id=student_id, is_deleted=False).first()
            if not student:
                flash("Data siswa tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
            if active_class_id and student.current_class_id != active_class_id:
                flash("Siswa tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
        else:
            participant = MajlisParticipant.query.filter_by(id=majlis_participant_id, is_deleted=False).first()
            if not participant:
                flash("Data peserta majlis tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
            if active_class_id and participant.majlis_class_id != active_class_id:
                flash("Peserta majlis tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        try:
            makhraj_errors = int(request.form.get('makhraj_errors') or 0)
            tajwid_errors = int(request.form.get('tajwid_errors') or 0)
            harakat_errors = int(request.form.get('harakat_errors') or 0)
            tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)
        except ValueError:
            flash("Input jumlah kesalahan harus berupa angka.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        total_errors = makhraj_errors + tajwid_errors + harakat_errors + tahfidz_errors
        score = max(0, 100 - (total_errors * 2))

        new_evaluation = TahfidzEvaluation(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type,
            teacher_id=teacher.id,
            period_type=EvaluationPeriod[period_type],
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
        return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

    return render_template('teacher/input_tahfidz_evaluation.html',
                           my_classes=my_classes,
                           students=students,
                           majlis_participants=majlis_participants,
                           selected_class=selected_class,
                           EvaluationPeriod=EvaluationPeriod)


@teacher_bp.route('/siswa-wali-kelas')
@login_required
@role_required(UserRole.GURU)
def homeroom_students():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    homeroom_classes = ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id, is_deleted=False).order_by(ClassRoom.name).all()

    if not homeroom_classes:
        flash("Anda belum ditugaskan sebagai wali kelas.", "warning")
        return redirect(url_for('teacher.dashboard'))

    selected_class_id = request.args.get('class_id', type=int) or homeroom_classes[0].id
    selected_class = next((c for c in homeroom_classes if c.id == selected_class_id), homeroom_classes[0])

    students = Student.query.filter_by(current_class_id=selected_class.id, is_deleted=False).order_by(Student.full_name).all()

    return render_template('teacher/homeroom_students.html',
                         teacher=teacher,
                         students=students,
                         homeroom_class=selected_class,
                         homeroom_classes=homeroom_classes)


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
    homeroom_classes = ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id, is_deleted=False).all()

    if not homeroom_classes:
        flash("Hanya wali kelas yang dapat mencetak raport.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    if student.current_class_id not in [c.id for c in homeroom_classes]:
        flash("Siswa tidak ada di kelas perwalian Anda.", "danger")
        return redirect(url_for('teacher.homeroom_students'))

    active_year = AcademicYear.query.filter_by(is_active=True).first()
    final_report = []
    if active_year:
        grades = Grade.query.filter_by(student_id=student.id, academic_year_id=active_year.id).all()
        grouped = defaultdict(lambda: defaultdict(list))
        for g in grades:
            grouped[g.subject][g.type.name].append(g.score)

        for sub, data in grouped.items():
            tugas_uh = data.get('TUGAS', []) + data.get('UH', [])
            avg_tugas = sum(tugas_uh) / len(tugas_uh) if tugas_uh else 0
            avg_uts = sum(data.get('UTS', [])) / len(data.get('UTS', [])) if data.get('UTS') else 0
            avg_uas = sum(data.get('UAS', [])) / len(data.get('UAS', [])) if data.get('UAS') else 0
            final_score = round((avg_tugas * 0.3) + (avg_uts * 0.3) + (avg_uas * 0.4), 2)
            predikat = 'A' if final_score >= 85 else 'B' if final_score >= 75 else 'C' if final_score >= 65 else 'D'
            final_report.append({'subject': sub.name, 'kkm': sub.kkm or 70, 'final': final_score, 'predikat': predikat})

    attendance_stats = {'sakit': 0, 'izin': 0, 'alpa': 0}
    if active_year:
        attendances = Attendance.query.filter_by(student_id=student.id, academic_year_id=active_year.id).all()
        for a in attendances:
            if a.status.name == 'SAKIT':
                attendance_stats['sakit'] += 1
            elif a.status.name == 'IZIN':
                attendance_stats['izin'] += 1
            elif a.status.name == 'ALPHA':
                attendance_stats['alpa'] += 1

    return render_template('teacher/print_report.html',
                          student=student,
                          teacher=teacher,
                          academic_year=active_year,
                          final_report=final_report,
                          attendance_stats=attendance_stats)


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
