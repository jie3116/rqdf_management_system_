from datetime import datetime
import json
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
    request,
)
from flask_login import (
    login_required,
    current_user,
)
from sqlalchemy import and_, or_

from app.extensions import db
from app.forms import PPDBForm
from app.decorators import role_required
from app.services.majlis_enrollment_service import resolve_majlis_classroom
from app.services.ppdb_config_service import (
    find_matching_ppdb_path,
    get_active_ppdb_period,
    list_configured_ppdb_document_requirements,
    list_configured_ppdb_form_fields,
    list_configured_ppdb_form_sections,
    list_active_ppdb_document_requirements,
    list_active_ppdb_form_fields,
    list_active_ppdb_paths,
    ppdb_fee_preview_by_path,
    ppdb_field_options,
)
from app.services.ppdb_fee_service import get_public_ppdb_fee_preview
from app.utils.tenant import resolve_tenant_id, scoped_classrooms_query
from app.utils.timezone import local_now

# Kita hapus import model Student, Tahfidz, Schedule dll karena tidak dipakai lagi di sini
# Sisakan import yang dipakai untuk PPDB form saja
from app.models import (
    UserRole,
    StudentCandidate,
    ProgramType,
    EducationLevel,
    ScholarshipCategory,
    UniformSize,
    TahfidzSchedule,
    RegistrationStatus,
    Gender,
    ParticipantType,
    TahfidzRecord,
    RecitationRecord,
    TahfidzSummary,
    TahfidzEvaluation,
    Schedule,
    Announcement,
)
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read
from app.utils.roles import get_active_role, set_active_role
from app.utils.tenant_modules import get_tenant_package, role_allowed_for_package

main_bp = Blueprint('main', __name__)


def _render_ppdb_form(form):
    tenant_id = resolve_tenant_id(
        current_user if getattr(current_user, "is_authenticated", False) else None
    )
    active_period = get_active_ppdb_period(tenant_id)
    active_paths = list_active_ppdb_paths(tenant_id, active_period)
    if active_paths:
        form.ppdb_path_id.choices = [(path.id, path.name) for path in active_paths]
    custom_fields = list_configured_ppdb_form_fields(tenant_id, active_period)
    document_requirements = list_configured_ppdb_document_requirements(tenant_id, active_period)
    form_sections = list_configured_ppdb_form_sections(tenant_id, active_period)
    custom_fields_by_section = {}
    for field in custom_fields:
        custom_fields_by_section.setdefault(field.section_id, []).append(field)
    return render_template(
        "public/ppdb_form.html",
        form=form,
        active_ppdb_period=active_period,
        active_ppdb_paths=active_paths,
        ppdb_path_config={
            str(path.id): {
                "program_type": (
                    path.tenant_program.system_type.name
                    if path.tenant_program and path.tenant_program.system_type
                    else (path.program_type.name if path.program_type else "")
                ),
                "education_level": (
                    path.education_level.name
                    if path.education_level
                    else (
                        path.tenant_program.education_level.name
                        if path.tenant_program and path.tenant_program.education_level
                        else ""
                    )
                ),
                "scholarship_category": path.scholarship_category.name if path.scholarship_category else "",
            }
            for path in active_paths
        },
        custom_fields=custom_fields,
        form_sections=form_sections,
        custom_fields_by_section=custom_fields_by_section,
        custom_field_options={field.id: ppdb_field_options(field) for field in custom_fields},
        document_requirements=document_requirements,
        ppdb_fee_preview=get_public_ppdb_fee_preview(tenant_id=tenant_id),
        ppdb_path_fee_preview=ppdb_fee_preview_by_path(tenant_id, active_period),
    )


def _get_majlis_announcements(limit=None):
    profile = current_user.majlis_profile
    parent_profile = current_user.parent_profile if current_user.has_role(UserRole.WALI_MURID) else None
    class_id = profile.majlis_class_id if profile else None

    if class_id is None and profile and getattr(profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(current_user.tenant_id, profile.person_id)
        class_id = majlis_class.id if majlis_class else None

    if class_id is None and parent_profile and getattr(parent_profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(current_user.tenant_id, parent_profile.person_id)
        class_id = majlis_class.id if majlis_class else None

    tenant_id = resolve_tenant_id(current_user, fallback_default=False)
    if tenant_id and class_id:
        scoped_class = scoped_classrooms_query(tenant_id).filter_by(id=class_id).first()
        if scoped_class is None:
            class_id = None

    announcements, _ = get_announcements_for_dashboard(
        current_user,
        class_ids=[class_id],
        user_ids=[current_user.id],
        program_types=[ProgramType.MAJLIS_TALIM.name],
        show_all=(limit is None)
    )
    return announcements


@main_bp.route('/')
def index():
    # Halaman awal langsung arahkan ke Login
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Fungsi Dispatcher: Hanya mengarahkan user ke dashboard spesifik berdasarkan Role.
    """

    active_role = get_active_role(current_user)
    tenant_id = resolve_tenant_id(current_user, fallback_default=False)
    package = get_tenant_package(tenant_id)

    if active_role and not role_allowed_for_package(active_role, package):
        fallback_role = None
        for role in sorted(list(current_user.all_roles()), key=lambda r: r.value):
            if role_allowed_for_package(role, package):
                fallback_role = role
                break

        if fallback_role:
            set_active_role(current_user, fallback_role)
            active_role = fallback_role
            flash(f'Role aktif disesuaikan ke {fallback_role.value} sesuai paket tenant.', 'info')
        else:
            flash('Tidak ada role yang aktif untuk paket modul tenant saat ini.', 'danger')
            return redirect(url_for('auth.login'))

    # 1. Super Admin
    if active_role == UserRole.SUPER_ADMIN:
        return redirect(url_for('admin.manage_tenants'))

    # 2. Admin
    if active_role == UserRole.ADMIN:
        return redirect(url_for('admin.dashboard'))

    # 3. Pimpinan
    elif active_role == UserRole.PIMPINAN:
        return redirect(url_for('admin.leadership_dashboard'))

    # 4. Guru
    elif active_role == UserRole.GURU:
        return redirect(url_for('teacher.dashboard'))

    # 5. Staff TU
    elif active_role == UserRole.TU:
        return redirect(url_for('staff.dashboard'))

    # 6. SISWA
    elif active_role == UserRole.SISWA:
        return redirect(url_for('student.dashboard'))

    # 7. Wali Murid
    elif active_role == UserRole.WALI_MURID:
        return redirect(url_for('parent.dashboard'))

    # 8. Wali Asrama
    elif active_role == UserRole.WALI_ASRAMA:
        return redirect(url_for('boarding.dashboard'))

    # 9. Peserta Majelis Ta'lim (external)
    elif active_role == UserRole.MAJLIS_PARTICIPANT:
        return redirect(url_for('main.majlis_dashboard'))

    # Fallback jika role tidak dikenali
    return render_template('index.html')


@main_bp.route('/majlis/dashboard')
@login_required
@role_required(UserRole.MAJLIS_PARTICIPANT, UserRole.WALI_MURID)
def majlis_dashboard():
    profile = current_user.majlis_profile
    parent_profile = current_user.parent_profile if current_user.has_role(UserRole.WALI_MURID) else None
    if not profile:
        flash("Profil peserta Majelis tidak ditemukan.", "danger")
        if current_user.has_role(UserRole.WALI_MURID):
            return redirect(url_for('parent.join_majlis'))
        return redirect(url_for('auth.logout'))

    summary_filters = [
        and_(
            TahfidzSummary.majlis_participant_id == profile.id,
            TahfidzSummary.participant_type == ParticipantType.EXTERNAL_MAJLIS
        )
    ]
    tahfidz_filters = [
        and_(
            TahfidzRecord.majlis_participant_id == profile.id,
            TahfidzRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS
        )
    ]
    recitation_filters = [
        and_(
            RecitationRecord.majlis_participant_id == profile.id,
            RecitationRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS
        )
    ]
    evaluation_filters = [
        and_(
            TahfidzEvaluation.majlis_participant_id == profile.id,
            TahfidzEvaluation.participant_type == ParticipantType.EXTERNAL_MAJLIS
        )
    ]

    if parent_profile:
        summary_filters.append(
            and_(
                TahfidzSummary.parent_id == parent_profile.id,
                TahfidzSummary.participant_type == ParticipantType.PARENT_MAJLIS
            )
        )
        tahfidz_filters.append(
            and_(
                TahfidzRecord.parent_id == parent_profile.id,
                TahfidzRecord.participant_type == ParticipantType.PARENT_MAJLIS
            )
        )
        recitation_filters.append(
            and_(
                RecitationRecord.parent_id == parent_profile.id,
                RecitationRecord.participant_type == ParticipantType.PARENT_MAJLIS
            )
        )
        evaluation_filters.append(
            and_(
                TahfidzEvaluation.parent_id == parent_profile.id,
                TahfidzEvaluation.participant_type == ParticipantType.PARENT_MAJLIS
            )
        )

    summary = TahfidzSummary.query.filter(or_(*summary_filters)).order_by(TahfidzSummary.updated_at.desc()).first()
    recent_tahfidz = TahfidzRecord.query.filter(or_(*tahfidz_filters)).order_by(TahfidzRecord.date.desc()).limit(10).all()
    recent_recitation = RecitationRecord.query.filter(or_(*recitation_filters)).order_by(RecitationRecord.date.desc()).limit(10).all()
    recent_evaluations = TahfidzEvaluation.query.filter(or_(*evaluation_filters)).order_by(TahfidzEvaluation.date.desc()).limit(10).all()

    majlis_class = profile.majlis_class
    if parent_profile and getattr(parent_profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(current_user.tenant_id, parent_profile.person_id) or majlis_class
    if getattr(profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(current_user.tenant_id, profile.person_id) or majlis_class

    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    if majlis_class:
        schedules = Schedule.query.filter_by(class_id=majlis_class.id, is_deleted=False).order_by(Schedule.start_time).all()
        for sch in schedules:
            if sch.day in weekly_schedule:
                weekly_schedule[sch.day].append(sch)

    top_tab = (request.args.get('top_tab') or 'main').strip().lower()
    show_all_announcements = (request.args.get('ann') or '').strip().lower() == 'all'
    majlis_announcements = _get_majlis_announcements(limit=None if show_all_announcements else 3)
    unread_announcements_count = 0
    _, unread_announcements_count = get_announcements_for_dashboard(
        current_user,
        class_ids=[majlis_class.id if majlis_class else None],
        user_ids=[current_user.id],
        program_types=[ProgramType.MAJLIS_TALIM.name],
        show_all=False
    )
    if top_tab == 'ann':
        mark_announcements_as_read(current_user, majlis_announcements)
        unread_announcements_count = 0

    return render_template(
        'majlis/dashboard.html',
        profile=profile,
        summary=summary,
        recent_tahfidz=recent_tahfidz,
        recent_recitation=recent_recitation,
        recent_evaluations=recent_evaluations,
        majlis_class=majlis_class,
        weekly_schedule=weekly_schedule,
        majlis_announcements=majlis_announcements,
        show_all_announcements=show_all_announcements,
        top_tab=top_tab,
        unread_announcements_count=unread_announcements_count
    )


# ==========================================
# PPDB PUBLIC ROUTE (FORM PENDAFTARAN)
# ==========================================

@main_bp.route('/ppdb', methods=['GET', 'POST'])
def ppdb_register():
    form = PPDBForm()
    tenant_id_for_choices = resolve_tenant_id(
        current_user if getattr(current_user, "is_authenticated", False) else None
    )
    active_period_for_choices = get_active_ppdb_period(tenant_id_for_choices)
    active_paths_for_choices = list_active_ppdb_paths(tenant_id_for_choices, active_period_for_choices)
    if active_paths_for_choices:
        form.ppdb_path_id.choices = [(path.id, path.name) for path in active_paths_for_choices]

    if request.method == 'POST':
        if not form.validate_on_submit():
            # Tampilkan sumber error agar user tahu field yang bermasalah.
            first_field_name = next(iter(form.errors), None)
            if first_field_name and hasattr(form, first_field_name):
                field = getattr(form, first_field_name)
                field_label = field.label.text if getattr(field, "label", None) else first_field_name
                first_error = form.errors[first_field_name][0] if form.errors[first_field_name] else "Input tidak valid."
                flash(f'{field_label}: {first_error}', 'danger')
            else:
                flash('Mohon lengkapi data pendaftaran yang wajib diisi.', 'danger')
            current_app.logger.warning("PPDB form validation errors: %s", form.errors)
            return _render_ppdb_form(form)
        try:
            # Logika berdasarkan program type
            try:
                program_type = ProgramType[form.program_type.data]
            except KeyError:
                flash('Pilihan program tidak valid.', 'danger')
                return _render_ppdb_form(form)

            is_majlis = program_type == ProgramType.MAJLIS_TALIM
            is_rqdf = program_type == ProgramType.RQDF_SORE

            tenant_id = resolve_tenant_id(
                current_user if getattr(current_user, "is_authenticated", False) else None
            )
            if tenant_id is None:
                flash("Tenant default tidak ditemukan. Pendaftaran belum bisa diproses.", "danger")
                return _render_ppdb_form(form)

            active_period = get_active_ppdb_period(tenant_id)
            if active_period and not active_period.public_registration_enabled:
                flash("Pendaftaran PPDB tenant ini sedang ditutup.", "warning")
                return _render_ppdb_form(form)

            active_paths = list_active_ppdb_paths(tenant_id, active_period)
            active_path = None
            if active_period and active_paths:
                selected_path_id = request.form.get('ppdb_path_id', type=int)
                active_path = next((path for path in active_paths if path.id == selected_path_id), None)
                if active_path is None:
                    flash('Jenis program PPDB tidak valid atau sedang tidak aktif.', 'danger')
                    return _render_ppdb_form(form)
                program_type = (
                    active_path.tenant_program.system_type
                    if active_path.tenant_program and active_path.tenant_program.system_type
                    else active_path.program_type
                )
                if active_path.education_level:
                    education_level = active_path.education_level
                elif active_path.tenant_program and active_path.tenant_program.education_level:
                    education_level = active_path.tenant_program.education_level
                elif program_type == ProgramType.MAJLIS_TALIM:
                    education_level = EducationLevel.NON_FORMAL
                else:
                    education_level = EducationLevel[form.education_level.data]
                scholarship_category = active_path.scholarship_category or ScholarshipCategory.NON_BEASISWA
                is_majlis = program_type == ProgramType.MAJLIS_TALIM
                is_rqdf = program_type == ProgramType.RQDF_SORE

            # Validasi kontak berdasarkan jenis program
            if is_majlis:
                contact_phone = form.personal_phone.data
                if not contact_phone:
                    flash("Nomor WhatsApp wajib diisi untuk Majelis Ta'lim", 'danger')
                    return _render_ppdb_form(form)
            else:
                contact_phone = form.parent_phone.data
                if not contact_phone:
                    flash('Nomor Telepon Orang Tua wajib diisi', 'danger')
                    return _render_ppdb_form(form)
                nik_value = (form.nik.data or '').strip()
                kk_number_value = (form.kk_number.data or '').strip()
                if not nik_value or not kk_number_value:
                    flash('Nomor NIK dan Nomor KK wajib diisi.', 'danger')
                    return _render_ppdb_form(form)
                if is_rqdf:
                    if form.tahfidz_schedule.data == TahfidzSchedule.TIDAK_ADA.name:
                        flash('Jadwal kelas RQDF wajib dipilih.', 'danger')
                        return _render_ppdb_form(form)
                    if (form.initial_pledge_amount.data or 0) <= 0:
                        flash('Infaq pembangunan wajib dipilih untuk kelas reguler RQDF.', 'danger')
                        return _render_ppdb_form(form)
            if is_majlis:
                nik_value = (form.nik.data or '').strip() or None
                kk_number_value = (form.kk_number.data or '').strip() or None

            if active_path is None:
                # Untuk Majelis, pakai default yang aman agar tidak tergantung field tersembunyi
                education_level = EducationLevel.NON_FORMAL if is_majlis else EducationLevel[form.education_level.data]
                scholarship_category = ScholarshipCategory.NON_BEASISWA if is_majlis else ScholarshipCategory[
                    form.scholarship_category.data
                ]
                active_path = find_matching_ppdb_path(
                    tenant_id=tenant_id,
                    period=active_period,
                    program_type=program_type,
                    education_level=education_level,
                    scholarship_category=scholarship_category,
                )
                if active_period and active_path is None:
                    flash('Jalur PPDB untuk kombinasi program tersebut tidak aktif pada tenant ini.', 'danger')
                    return _render_ppdb_form(form)

            custom_fields = list_active_ppdb_form_fields(tenant_id, active_period, active_path)
            extra_answers = {}
            for field in custom_fields:
                input_name = f"extra_field_{field.field_key}"
                if field.field_type.name == "BOOLEAN":
                    value = "Ya" if request.form.get(input_name) == "on" else "Tidak"
                else:
                    value = (request.form.get(input_name) or "").strip()
                if field.is_required and not value:
                    flash(f'{field.label} wajib diisi.', 'danger')
                    return _render_ppdb_form(form)
                if field.field_type.name == "SELECT":
                    allowed_options = ppdb_field_options(field)
                    if value and allowed_options and value not in allowed_options:
                        flash(f'Pilihan {field.label} tidak valid.', 'danger')
                        return _render_ppdb_form(form)
                extra_answers[field.field_key] = {
                    "label": field.label,
                    "value": value,
                }

            document_requirements = list_active_ppdb_document_requirements(tenant_id, active_period, active_path)
            document_status = {
                requirement.code: {
                    "name": requirement.name,
                    "required": requirement.is_required,
                    "status": "PENDING",
                }
                for requirement in document_requirements
            }

            candidate = StudentCandidate(
                tenant_id=tenant_id,
                ppdb_period_id=active_period.id if active_period else None,
                ppdb_path_id=active_path.id if active_path else None,
                status=RegistrationStatus.PENDING,
                program_type=program_type,
                education_level=education_level,
                scholarship_category=scholarship_category,
                full_name=form.full_name.data,
                nickname=form.nickname.data,
                nik=nik_value,
                kk_number=kk_number_value,
                gender=Gender[form.gender.data],
                place_of_birth=form.place_of_birth.data,
                date_of_birth=form.date_of_birth.data,
                age=form.age.data,
                address=form.address.data,
                previous_school=form.previous_school.data,
                previous_school_class=form.previous_school_class.data,

                # Data Orang Tua (Optional untuk Majelis)
                father_name=form.father_name.data,
                father_job=form.father_job.data,
                father_income_range=form.father_income_range.data,
                mother_name=form.mother_name.data,
                mother_job=form.mother_job.data,
                mother_income_range=form.mother_income_range.data,

                # Phone logic berdasarkan program
                parent_phone=contact_phone,

                # BARU: Data khusus Majelis Ta'lim
                personal_phone = form.personal_phone.data if is_majlis else None,
                personal_job = form.personal_job.data if is_majlis else None,

                tahfidz_schedule = TahfidzSchedule[form.tahfidz_schedule.data] if is_rqdf else TahfidzSchedule.TIDAK_ADA,
                uniform_size = UniformSize[form.uniform_size.data] if is_rqdf else UniformSize.TIDAK_MEMILIH,
                initial_pledge_amount = form.initial_pledge_amount.data if is_rqdf else 0,
                extra_answers_json=json.dumps(extra_answers, ensure_ascii=False) if extra_answers else None,
                document_status_json=json.dumps(document_status, ensure_ascii=False) if document_status else None,
            )

            db.session.add(candidate)
            db.session.flush()

            year = local_now().year
            if program_type == ProgramType.MAJLIS_TALIM:
                candidate.registration_no = f"MAJ{year}{candidate.id:05d}"  # BARU: Prefix khusus Majelis
            else:
                prefix = active_period.registration_no_prefix if active_period else "REG"
                candidate.registration_no = f"{prefix}{year}{candidate.id:05d}"

            db.session.commit()

            flash(f"Pendaftaran berhasil. Nomor pendaftaran Anda: {candidate.registration_no}", "success")
            return render_template("public/ppdb_success.html", candidate=candidate)

        except Exception:
            db.session.rollback()
            current_app.logger.exception("PPDB registration failed")
            flash("Terjadi kesalahan sistem saat memproses pendaftaran.", "danger")

    return _render_ppdb_form(form)
