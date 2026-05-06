from app.utils.timezone import local_now


def generate_invoice_number(fee_type_id, student_id, sequence=None, tenant_id=None):
    """
    Format standar invoice (maksimal <= 50 karakter):
    INV-T{tenant_id}-YYMMDDHHMM-{student_id}[-{sequence}]
    """
    if tenant_id is None:
        raise ValueError("tenant_id wajib diisi untuk mencegah bentrok nomor invoice antar-tenant.")

    timestamp = local_now().strftime("%y%m%d%H%M")
    invoice_number = f"INV-T{int(tenant_id)}-{timestamp}-{int(student_id)}"
    if sequence is not None:
        invoice_number = f"{invoice_number}-{int(sequence)}"
    return invoice_number
