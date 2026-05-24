from app.models import ProgramType


SYSTEM_PROGRAM_LABELS = {
    ProgramType.SEKOLAH_FULLDAY: "Sekolah Formal",
    ProgramType.RQDF_SORE: "Rumah Qur'an",
    ProgramType.TAKHOSUS_TAHFIDZ: "Tahfidz Intensif",
    ProgramType.MAJLIS_TALIM: "Majelis / Kelas Dewasa",
    ProgramType.BAHASA: "Program Bahasa",
}


def system_program_label(program_type):
    if not program_type:
        return "-"
    if isinstance(program_type, str):
        try:
            program_type = ProgramType[program_type]
        except KeyError:
            return program_type.replace("_", " ").title()
    return SYSTEM_PROGRAM_LABELS.get(program_type, program_type.value)


def system_program_label_choices():
    return [(program_type, system_program_label(program_type)) for program_type in ProgramType]
