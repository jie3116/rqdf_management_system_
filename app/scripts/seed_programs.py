from app import create_app
from app.extensions import db
from app.models import EducationLevel, Program, ProgramCategory, Tenant


PROGRAM_DEFINITIONS = (
    {
        "code": "SEKOLAH_SD",
        "name": "Sekolah SD",
        "category": ProgramCategory.FORMAL,
        "education_level": EducationLevel.SD,
        "report_schema": "ACADEMIC",
        "organization_unit": "SEKOLAH",
    },
    {
        "code": "SEKOLAH_SMP",
        "name": "Sekolah SMP",
        "category": ProgramCategory.FORMAL,
        "education_level": EducationLevel.SMP,
        "report_schema": "ACADEMIC",
        "organization_unit": "SEKOLAH",
    },
    {
        "code": "SEKOLAH_SMA",
        "name": "Sekolah SMA",
        "category": ProgramCategory.FORMAL,
        "education_level": EducationLevel.SMA,
        "report_schema": "ACADEMIC",
        "organization_unit": "SEKOLAH",
    },
    {
        "code": "PESANTREN",
        "name": "Pesantren",
        "category": ProgramCategory.NON_FORMAL,
        "education_level": None,
        "report_schema": "PESANTREN",
        "organization_unit": "BOARDING",
    },
    {
        "code": "RUMAH_QURAN",
        "name": "Rumah Quran",
        "category": ProgramCategory.NON_FORMAL,
        "education_level": None,
        "report_schema": "RUMAH_QURAN",
        "organization_unit": "TAHFIDZ",
    },
    {
        "code": "MAJLIS_TALIM",
        "name": "Majlis Ta'lim",
        "category": ProgramCategory.NON_FORMAL,
        "education_level": None,
        "report_schema": "MAJLIS",
        "organization_unit": "MAJLIS",
    },
    {
        "code": "BAHASA",
        "name": "Program Bahasa",
        "category": ProgramCategory.NON_FORMAL,
        "education_level": None,
        "report_schema": "BAHASA",
        "organization_unit": "BAHASA",
    },
)


def seed_programs():
    app = create_app()
    with app.app_context():
        tenants = Tenant.query.order_by(Tenant.id.asc()).all()
        created = 0
        updated = 0

        for tenant in tenants:
            for item in PROGRAM_DEFINITIONS:
                program = Program.query.filter_by(
                    tenant_id=tenant.id,
                    code=item["code"],
                ).first()

                if program is None:
                    program = Program(tenant_id=tenant.id, code=item["code"])
                    db.session.add(program)
                    created += 1
                else:
                    updated += 1

                program.name = item["name"]
                program.category = item["category"]
                program.education_level = item["education_level"]
                program.report_schema = item["report_schema"]
                program.organization_unit = item["organization_unit"]
                program.is_active = True

        db.session.commit()
        print(f"Programs seeded. created={created} updated={updated} tenants={len(tenants)}")


if __name__ == "__main__":
    seed_programs()
