from app.utils.timezone import local_now


def generate_invoice_number(fee_type_id, student_id, sequence=None):
    """
    Format standar invoice (maksimal <= 50 karakter):
    INV/YYMMDDHHMMSSfff/F{fee_type_id}/S{student_id}[/N{sequence}]
    """
    timestamp = local_now().strftime("%y%m%d%H%M%S%f")[:15]
    invoice_number = f"INV/{timestamp}/F{int(fee_type_id)}/S{int(student_id)}"
    if sequence is not None:
        invoice_number = f"{invoice_number}/N{int(sequence)}"
    return invoice_number
