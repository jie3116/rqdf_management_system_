import json
import re
from datetime import datetime

from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.extensions import db
from app.services.ppdb_config_service import (
    create_default_ppdb_period,
    get_active_ppdb_period,
    list_active_tenant_programs,
    ppdb_field_options,
    seed_default_ppdb_paths,
    seed_default_tenant_programs,
)
from app.models import (
    EducationLevel,
    PpdbDocumentRequirement,
    PpdbFeeItem,
    PpdbFieldType,
    PpdbFormField,
    PpdbFormSection,
    PpdbPath,
    PpdbPeriod,
    PpdbPeriodStatus,
    ProgramType,
    ScholarshipCategory,
    TenantProgram,
)
from app.utils.money import to_rupiah_int
from app.utils.programs import system_program_label, system_program_label_choices
from app.utils.tenant import resolve_tenant_id


def _current_tenant_id():
    return resolve_tenant_id(current_user)

def _parse_rupiah_input(raw_value, default_value):
    if raw_value is None:
        return default_value
    digits = ''.join(ch for ch in str(raw_value) if ch.isdigit())
    if not digits:
        return default_value
    return to_rupiah_int(digits, default=default_value)


def _normalize_config_key(raw_value, fallback_prefix):
    value = (raw_value or '').strip().lower()
    value = re.sub(r'[^a-z0-9_]+', '_', value)
    value = re.sub(r'_+', '_', value).strip('_')
    if not value:
        value = f"{fallback_prefix}_{int(datetime.utcnow().timestamp())}"
    return value[:80]


def _parse_lines_json(raw_value):
    values = []
    for line in (raw_value or '').splitlines():
        item = line.strip()
        if item:
            values.append(item)
    return json.dumps(values, ensure_ascii=False) if values else None


def ppdb_settings_view(settings_endpoint='admin.ppdb_settings', form_builder_endpoint='admin.ppdb_form_builder'):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        try:
            if action == 'create_default_period':
                period = get_active_ppdb_period(tenant_id)
                if period is None:
                    period = create_default_ppdb_period(tenant_id)
                    db.session.commit()
                    flash(f'Periode {period.name} dan jalur PPDB default berhasil dibuat.', 'success')
                else:
                    created = seed_default_ppdb_paths(tenant_id, period)
                    db.session.commit()
                    flash(f'Jalur default diperiksa. {created} jalur baru ditambahkan.', 'success')
            elif action == 'update_period':
                period_id = request.form.get('period_id', type=int)
                period = PpdbPeriod.query.filter_by(id=period_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                period.name = (request.form.get('name') or '').strip() or period.name
                period.academic_year_label = (request.form.get('academic_year_label') or '').strip() or None
                period.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
                period.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
                period.registration_no_prefix = ((request.form.get('registration_no_prefix') or 'REG').strip().upper())[:10]
                period.public_registration_enabled = request.form.get('public_registration_enabled') == 'on'
                status_name = request.form.get('status') or PpdbPeriodStatus.DRAFT.name
                period.status = PpdbPeriodStatus[status_name]
                if period.end_date < period.start_date:
                    raise ValueError('Tanggal selesai tidak boleh sebelum tanggal mulai.')
                db.session.commit()
                flash('Pengaturan periode PPDB berhasil disimpan.', 'success')
            elif action == 'update_paths':
                period_id = request.form.get('period_id', type=int)
                period = PpdbPeriod.query.filter_by(id=period_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                paths = PpdbPath.query.filter_by(
                    tenant_id=tenant_id,
                    period_id=period.id,
                    is_deleted=False,
                ).all()
                for path in paths:
                    path.is_active = request.form.get(f'path_active_{path.id}') == 'on'
                    quota_raw = (request.form.get(f'path_quota_{path.id}') or '').strip()
                    path.quota = int(quota_raw) if quota_raw else None
                    if path.quota is not None and path.quota < 0:
                        raise ValueError('Kuota jalur tidak boleh negatif.')
                db.session.commit()
                flash('Status jalur PPDB berhasil diperbarui.', 'success')
            elif action == 'seed_tenant_programs':
                created = seed_default_tenant_programs(tenant_id)
                db.session.commit()
                flash(f'Program tenant default diperiksa. {created} program baru ditambahkan.', 'success')
            elif action == 'add_tenant_program':
                code = _normalize_config_key(request.form.get('code'), 'program').upper()[:40]
                name = (request.form.get('name') or '').strip()
                if not name:
                    raise ValueError('Nama program tenant wajib diisi.')
                system_type = ProgramType[request.form.get('system_type')]
                education_raw = request.form.get('education_level') or ''
                program = TenantProgram(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    system_type=system_type,
                    education_level=EducationLevel[education_raw] if education_raw else None,
                    category=(request.form.get('category') or '').strip() or None,
                    sort_order=request.form.get('sort_order', type=int) or 0,
                    is_active=True,
                )
                db.session.add(program)
                db.session.commit()
                flash('Program tenant berhasil ditambahkan.', 'success')
            elif action == 'toggle_tenant_program':
                program_id = request.form.get('tenant_program_id', type=int)
                program = TenantProgram.query.filter_by(
                    id=program_id,
                    tenant_id=tenant_id,
                    is_deleted=False,
                ).first_or_404()
                program.is_active = request.form.get('is_active') == 'on'
                program.sort_order = request.form.get('sort_order', type=int) or 0
                db.session.commit()
                flash('Program tenant berhasil diperbarui.', 'success')
            elif action == 'add_path':
                period_id = request.form.get('period_id', type=int)
                period = PpdbPeriod.query.filter_by(id=period_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                code = _normalize_config_key(request.form.get('code'), 'path').upper()[:30]
                name = (request.form.get('name') or '').strip()
                if not name:
                    raise ValueError('Nama jenis program wajib diisi.')
                tenant_program_id = request.form.get('tenant_program_id', type=int)
                tenant_program = TenantProgram.query.filter_by(
                    id=tenant_program_id,
                    tenant_id=tenant_id,
                    is_deleted=False,
                ).first_or_404()
                program_type = tenant_program.system_type
                education_raw = request.form.get('education_level') or ''
                scholarship_raw = request.form.get('scholarship_category') or ''
                path = PpdbPath(
                    tenant_id=tenant_id,
                    period_id=period.id,
                    tenant_program_id=tenant_program.id,
                    code=code,
                    name=name,
                    program_type=program_type,
                    education_level=EducationLevel[education_raw] if education_raw else tenant_program.education_level,
                    scholarship_category=ScholarshipCategory[scholarship_raw] if scholarship_raw else None,
                    quota=request.form.get('quota', type=int),
                    sort_order=request.form.get('sort_order', type=int) or 0,
                    is_active=True,
                )
                db.session.add(path)
                db.session.commit()
                flash('Jenis program PPDB berhasil ditambahkan.', 'success')
            elif action == 'delete_path':
                path_id = request.form.get('path_id', type=int)
                path = PpdbPath.query.filter_by(id=path_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                path.is_deleted = True
                db.session.commit()
                flash('Jenis program PPDB dihapus.', 'success')
            elif action == 'add_fee_item':
                path_id = request.form.get('path_id', type=int)
                path = PpdbPath.query.filter_by(id=path_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                name = (request.form.get('name') or '').strip()
                if not name:
                    raise ValueError('Nama item biaya wajib diisi.')
                amount = _parse_rupiah_input(request.form.get('amount'), 0)
                if amount < 0:
                    raise ValueError('Nominal biaya tidak boleh negatif.')
                db.session.add(
                    PpdbFeeItem(
                        tenant_id=tenant_id,
                        period_id=path.period_id,
                        path_id=path.id,
                        name=name,
                        amount=amount,
                        sort_order=request.form.get('sort_order', type=int) or 0,
                        is_active=True,
                    )
                )
                db.session.commit()
                flash('Item biaya PPDB berhasil ditambahkan.', 'success')
            elif action == 'toggle_fee_item':
                fee_item_id = request.form.get('fee_item_id', type=int)
                item = PpdbFeeItem.query.filter_by(id=fee_item_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                item.is_active = request.form.get('is_active') == 'on'
                item.amount = _parse_rupiah_input(request.form.get('amount'), item.amount)
                db.session.commit()
                flash('Item biaya PPDB berhasil diperbarui.', 'success')
            elif action == 'delete_fee_item':
                fee_item_id = request.form.get('fee_item_id', type=int)
                item = PpdbFeeItem.query.filter_by(id=fee_item_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                item.is_deleted = True
                db.session.commit()
                flash('Item biaya PPDB dihapus.', 'success')
            elif action == 'add_form_field':
                period_id = request.form.get('period_id', type=int)
                period = PpdbPeriod.query.filter_by(id=period_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                label = (request.form.get('label') or '').strip()
                if not label:
                    raise ValueError('Label field wajib diisi.')
                field_type = PpdbFieldType[request.form.get('field_type') or PpdbFieldType.TEXT.name]
                field = PpdbFormField(
                    tenant_id=tenant_id,
                    period_id=period.id,
                    path_id=request.form.get('path_id', type=int) or None,
                    field_key=_normalize_config_key(request.form.get('field_key') or label, 'field'),
                    label=label,
                    field_type=field_type,
                    is_required=request.form.get('is_required') == 'on',
                    options_json=_parse_lines_json(request.form.get('options')) if field_type == PpdbFieldType.SELECT else None,
                    sort_order=request.form.get('sort_order', type=int) or 0,
                    is_active=True,
                )
                if field_type == PpdbFieldType.SELECT and not field.options_json:
                    raise ValueError('Field pilihan wajib memiliki minimal satu opsi.')
                db.session.add(field)
                db.session.commit()
                flash('Field tambahan PPDB berhasil ditambahkan.', 'success')
            elif action == 'toggle_form_field':
                field_id = request.form.get('field_id', type=int)
                field = PpdbFormField.query.filter_by(id=field_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                field.is_active = request.form.get('is_active') == 'on'
                field.is_required = request.form.get('is_required') == 'on'
                db.session.commit()
                flash('Field tambahan PPDB berhasil diperbarui.', 'success')
            elif action == 'delete_form_field':
                field_id = request.form.get('field_id', type=int)
                field = PpdbFormField.query.filter_by(id=field_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                field.is_deleted = True
                db.session.commit()
                flash('Field tambahan PPDB dihapus.', 'success')
            elif action == 'add_document_requirement':
                period_id = request.form.get('period_id', type=int)
                period = PpdbPeriod.query.filter_by(id=period_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
                name = (request.form.get('name') or '').strip()
                if not name:
                    raise ValueError('Nama dokumen wajib diisi.')
                requirement = PpdbDocumentRequirement(
                    tenant_id=tenant_id,
                    period_id=period.id,
                    path_id=request.form.get('path_id', type=int) or None,
                    code=_normalize_config_key(request.form.get('code') or name, 'doc')[:50],
                    name=name,
                    is_required=request.form.get('is_required') == 'on',
                    allowed_file_types=(request.form.get('allowed_file_types') or '').strip() or None,
                    max_file_size_kb=request.form.get('max_file_size_kb', type=int),
                    sort_order=request.form.get('sort_order', type=int) or 0,
                    is_active=True,
                )
                db.session.add(requirement)
                db.session.commit()
                flash('Persyaratan dokumen berhasil ditambahkan.', 'success')
            elif action == 'toggle_document_requirement':
                requirement_id = request.form.get('requirement_id', type=int)
                requirement = PpdbDocumentRequirement.query.filter_by(
                    id=requirement_id,
                    tenant_id=tenant_id,
                    is_deleted=False,
                ).first_or_404()
                requirement.is_active = request.form.get('is_active') == 'on'
                requirement.is_required = request.form.get('is_required') == 'on'
                db.session.commit()
                flash('Persyaratan dokumen berhasil diperbarui.', 'success')
            elif action == 'delete_document_requirement':
                requirement_id = request.form.get('requirement_id', type=int)
                requirement = PpdbDocumentRequirement.query.filter_by(
                    id=requirement_id,
                    tenant_id=tenant_id,
                    is_deleted=False,
                ).first_or_404()
                requirement.is_deleted = True
                db.session.commit()
                flash('Persyaratan dokumen dihapus.', 'success')
            else:
                flash('Aksi pengaturan PPDB tidak dikenali.', 'warning')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal menyimpan pengaturan PPDB: {e}', 'danger')
        return redirect(url_for(settings_endpoint))

    periods = (
        PpdbPeriod.query.filter_by(tenant_id=tenant_id, is_deleted=False)
        .order_by(PpdbPeriod.start_date.desc(), PpdbPeriod.id.desc())
        .all()
    )
    active_period = get_active_ppdb_period(tenant_id)
    selected_period = active_period or (periods[0] if periods else None)
    active_tenant_programs = list_active_tenant_programs(tenant_id)
    tenant_programs = (
        TenantProgram.query.filter_by(tenant_id=tenant_id, is_deleted=False)
        .order_by(TenantProgram.sort_order.asc(), TenantProgram.name.asc())
        .all()
    )
    paths = []
    custom_fields = []
    document_requirements = []
    fee_items_by_path = {}
    if selected_period:
        paths = (
            PpdbPath.query.filter_by(tenant_id=tenant_id, period_id=selected_period.id, is_deleted=False)
            .order_by(PpdbPath.sort_order.asc(), PpdbPath.name.asc())
            .all()
        )
        custom_fields = (
            PpdbFormField.query.filter_by(tenant_id=tenant_id, period_id=selected_period.id, is_deleted=False)
            .order_by(PpdbFormField.sort_order.asc(), PpdbFormField.label.asc())
            .all()
        )
        document_requirements = (
            PpdbDocumentRequirement.query.filter_by(
                tenant_id=tenant_id,
                period_id=selected_period.id,
                is_deleted=False,
            )
            .order_by(PpdbDocumentRequirement.sort_order.asc(), PpdbDocumentRequirement.name.asc())
            .all()
        )
        fee_items = (
            PpdbFeeItem.query.filter_by(tenant_id=tenant_id, period_id=selected_period.id, is_deleted=False)
            .order_by(PpdbFeeItem.sort_order.asc(), PpdbFeeItem.name.asc())
            .all()
        )
        for item in fee_items:
            fee_items_by_path.setdefault(item.path_id, []).append(item)

    return render_template(
        'staff/ppdb/settings.html',
        periods=periods,
        selected_period=selected_period,
        paths=paths,
        statuses=PpdbPeriodStatus,
        field_types=PpdbFieldType,
        custom_fields=custom_fields,
        custom_field_options={field.id: ppdb_field_options(field) for field in custom_fields},
        document_requirements=document_requirements,
        fee_items_by_path=fee_items_by_path,
        tenant_programs=tenant_programs,
        active_tenant_programs=active_tenant_programs,
        program_types=ProgramType,
        system_program_label=system_program_label,
        system_program_label_choices=system_program_label_choices(),
        education_levels=EducationLevel,
        scholarship_categories=ScholarshipCategory,
        settings_endpoint=settings_endpoint,
        form_builder_endpoint=form_builder_endpoint,
    )


def ppdb_form_builder_view(
    path_id,
    settings_endpoint='admin.ppdb_settings',
    form_builder_endpoint='admin.ppdb_form_builder',
):
    tenant_id = _current_tenant_id()
    if tenant_id is None:
        flash('Tenant default tidak ditemukan.', 'danger')
        return redirect(url_for('main.dashboard'))

    path = PpdbPath.query.filter_by(id=path_id, tenant_id=tenant_id, is_deleted=False).first_or_404()
    period = PpdbPeriod.query.filter_by(id=path.period_id, tenant_id=tenant_id, is_deleted=False).first_or_404()

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip()
        try:
            if action == 'add_section':
                title = (request.form.get('title') or '').strip()
                if not title:
                    raise ValueError('Judul section wajib diisi.')
                db.session.add(
                    PpdbFormSection(
                        tenant_id=tenant_id,
                        period_id=period.id,
                        path_id=path.id,
                        title=title,
                        description=(request.form.get('description') or '').strip() or None,
                        sort_order=request.form.get('sort_order', type=int) or 0,
                        is_active=True,
                    )
                )
                db.session.commit()
                flash('Section form berhasil ditambahkan.', 'success')
            elif action == 'update_section':
                section_id = request.form.get('section_id', type=int)
                section = PpdbFormSection.query.filter_by(
                    id=section_id,
                    tenant_id=tenant_id,
                    path_id=path.id,
                    is_deleted=False,
                ).first_or_404()
                section.title = (request.form.get('title') or '').strip() or section.title
                section.description = (request.form.get('description') or '').strip() or None
                section.sort_order = request.form.get('sort_order', type=int) or 0
                section.is_active = request.form.get('is_active') == 'on'
                db.session.commit()
                flash('Section form berhasil diperbarui.', 'success')
            elif action == 'delete_section':
                section_id = request.form.get('section_id', type=int)
                section = PpdbFormSection.query.filter_by(
                    id=section_id,
                    tenant_id=tenant_id,
                    path_id=path.id,
                    is_deleted=False,
                ).first_or_404()
                fields = PpdbFormField.query.filter_by(
                    tenant_id=tenant_id,
                    section_id=section.id,
                    is_deleted=False,
                ).all()
                for field in fields:
                    field.section_id = None
                section.is_deleted = True
                db.session.commit()
                flash('Section dihapus. Field di dalamnya dipindah ke tanpa section.', 'success')
            elif action == 'add_builder_field':
                label = (request.form.get('label') or '').strip()
                if not label:
                    raise ValueError('Label pertanyaan wajib diisi.')
                field_type = PpdbFieldType[request.form.get('field_type') or PpdbFieldType.TEXT.name]
                section_id = request.form.get('section_id', type=int)
                section = None
                if section_id:
                    section = PpdbFormSection.query.filter_by(
                        id=section_id,
                        tenant_id=tenant_id,
                        path_id=path.id,
                        is_deleted=False,
                    ).first_or_404()
                field = PpdbFormField(
                    tenant_id=tenant_id,
                    period_id=period.id,
                    path_id=path.id,
                    section_id=section.id if section else None,
                    field_key=_normalize_config_key(request.form.get('field_key') or label, 'field'),
                    label=label,
                    field_type=field_type,
                    is_required=request.form.get('is_required') == 'on',
                    options_json=_parse_lines_json(request.form.get('options')) if field_type == PpdbFieldType.SELECT else None,
                    sort_order=request.form.get('sort_order', type=int) or 0,
                    is_active=True,
                )
                if field_type == PpdbFieldType.SELECT and not field.options_json:
                    raise ValueError('Pertanyaan pilihan wajib memiliki minimal satu opsi.')
                db.session.add(field)
                db.session.commit()
                flash('Pertanyaan form berhasil ditambahkan.', 'success')
            elif action == 'update_builder_field':
                field_id = request.form.get('field_id', type=int)
                field = PpdbFormField.query.filter_by(
                    id=field_id,
                    tenant_id=tenant_id,
                    path_id=path.id,
                    is_deleted=False,
                ).first_or_404()
                field.label = (request.form.get('label') or '').strip() or field.label
                field.is_required = request.form.get('is_required') == 'on'
                field.is_active = request.form.get('is_active') == 'on'
                field.sort_order = request.form.get('sort_order', type=int) or 0
                section_id = request.form.get('section_id', type=int)
                if section_id:
                    section = PpdbFormSection.query.filter_by(
                        id=section_id,
                        tenant_id=tenant_id,
                        path_id=path.id,
                        is_deleted=False,
                    ).first_or_404()
                    field.section_id = section.id
                else:
                    field.section_id = None
                db.session.commit()
                flash('Pertanyaan form berhasil diperbarui.', 'success')
            elif action == 'delete_builder_field':
                field_id = request.form.get('field_id', type=int)
                field = PpdbFormField.query.filter_by(
                    id=field_id,
                    tenant_id=tenant_id,
                    path_id=path.id,
                    is_deleted=False,
                ).first_or_404()
                field.is_deleted = True
                db.session.commit()
                flash('Pertanyaan form dihapus.', 'success')
            else:
                flash('Aksi form builder tidak dikenali.', 'warning')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal menyimpan form builder: {e}', 'danger')
        return redirect(url_for(form_builder_endpoint, path_id=path.id))

    sections = (
        PpdbFormSection.query.filter_by(tenant_id=tenant_id, path_id=path.id, is_deleted=False)
        .order_by(PpdbFormSection.sort_order.asc(), PpdbFormSection.title.asc())
        .all()
    )
    fields = (
        PpdbFormField.query.filter_by(tenant_id=tenant_id, path_id=path.id, is_deleted=False)
        .order_by(PpdbFormField.section_id.asc().nullsfirst(), PpdbFormField.sort_order.asc(), PpdbFormField.label.asc())
        .all()
    )
    fields_by_section = {}
    for field in fields:
        fields_by_section.setdefault(field.section_id, []).append(field)

    return render_template(
        'staff/ppdb/form_builder.html',
        period=period,
        path=path,
        sections=sections,
        fields=fields,
        fields_by_section=fields_by_section,
        field_types=PpdbFieldType,
        custom_field_options={field.id: ppdb_field_options(field) for field in fields},
        settings_endpoint=settings_endpoint,
    )

