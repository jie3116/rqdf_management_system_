import re
from pathlib import Path
from flask import current_app


ALLOWED_DOCUMENT_EXTENSIONS = {"txt", "md", "pdf", "docx"}
MAX_CONTEXT_CHARACTERS = 12000


def allowed_document(filename):
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    return suffix in ALLOWED_DOCUMENT_EXTENSIONS


def extract_document_text(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        return _extract_pdf_text(path)

    if suffix == ".docx":
        return _extract_docx_text(path)

    raise ValueError("Format dokumen belum didukung.")


def build_ai_prompt(request_type, document, parameters):
    label = _request_type_label(request_type)
    params = "\n".join(
        f"- {key.replace('_', ' ').title()}: {value}"
        for key, value in (parameters or {}).items()
        if value not in (None, "")
    )
    context = (document.extracted_text or "")[:MAX_CONTEXT_CHARACTERS]
    return (
        "Anda adalah asisten guru. Gunakan hanya konteks dokumen yang diberikan.\n"
        f"Tugas: {label}\n"
        f"Judul dokumen: {document.title}\n"
        f"Parameter:\n{params or '- Tidak ada parameter tambahan'}\n\n"
        f"Konteks dokumen:\n{context}"
    )


def generate_teacher_draft(request_type, document, parameters):
    text = _normalize_text(document.extracted_text or "")
    if not text:
        return "Dokumen belum memiliki teks yang bisa diproses. Upload dokumen TXT, MD, PDF, atau DOCX yang berisi teks."

    key_points = _extract_key_points(text)
    subject = parameters.get("subject") or "Mata pelajaran"
    grade = parameters.get("grade") or "Kelas"

    if request_type == "summary":
        return _summary_output(document.title, key_points)
    if request_type == "questions":
        count = _safe_int(parameters.get("question_count"), 5)
        return _questions_output(subject, grade, key_points, count)
    if request_type == "lesson_material":
        return _lesson_material_output(subject, grade, key_points)
    if request_type == "learning_ideas":
        return _learning_ideas_output(subject, grade, key_points)

    return _summary_output(document.title, key_points)


def generate_ai_assistant_output(request_type, document, parameters):
    provider = (current_app.config.get("AI_ASSISTANT_PROVIDER") or "local").strip().lower()
    if provider == "openai" and current_app.config.get("OPENAI_API_KEY"):
        try:
            return _generate_with_openai(request_type, document, parameters), "openai", None
        except Exception as exc:
            local_output = generate_teacher_draft(request_type, document, parameters)
            fallback_notice = (
                "Catatan: request ke OpenAI gagal, sehingga draft ini dibuat dengan generator lokal.\n"
                f"Detail teknis: {exc}\n\n"
            )
            return fallback_notice + local_output, "local_fallback", str(exc)

    return generate_teacher_draft(request_type, document, parameters), "local", None


def ai_provider_status():
    provider = (current_app.config.get("AI_ASSISTANT_PROVIDER") or "local").strip().lower()
    if provider == "openai":
        if current_app.config.get("OPENAI_API_KEY"):
            return {
                "provider": "openai",
                "label": "OpenAI aktif",
                "detail": current_app.config.get("OPENAI_MODEL") or "default model",
                "is_external": True,
            }
        return {
            "provider": "local",
            "label": "Mode lokal",
            "detail": "OPENAI_API_KEY belum diset",
            "is_external": False,
        }
    return {
        "provider": "local",
        "label": "Mode lokal",
        "detail": "AI_ASSISTANT_PROVIDER belum diset ke openai",
        "is_external": False,
    }


def _extract_pdf_text(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Ekstraksi PDF membutuhkan dependency pypdf.") from exc

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _extract_docx_text(path):
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Ekstraksi DOCX membutuhkan dependency python-docx.") from exc

    document = Document(str(path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs)


def _generate_with_openai(request_type, document, parameters):
    from openai import OpenAI

    client = OpenAI(api_key=current_app.config.get("OPENAI_API_KEY"))
    prompt = build_ai_prompt(request_type, document, parameters)
    response = client.responses.create(
        model=current_app.config.get("OPENAI_MODEL") or "gpt-5.2",
        instructions=_system_instructions(),
        input=prompt,
        max_output_tokens=int(current_app.config.get("OPENAI_MAX_OUTPUT_TOKENS") or 2500),
    )
    output_text = (getattr(response, "output_text", None) or "").strip()
    if not output_text:
        raise RuntimeError("OpenAI tidak mengembalikan teks output.")
    return output_text


def _system_instructions():
    return (
        "Anda adalah AI Assistant untuk guru di aplikasi manajemen sekolah. "
        "Jawab dalam bahasa Indonesia yang jelas, praktis, dan siap diedit guru. "
        "Gunakan hanya konteks dokumen yang diberikan. Jika informasi tidak tersedia di dokumen, "
        "tulis bahwa informasi tersebut tidak ditemukan dalam dokumen. "
        "Untuk soal, sertakan kunci jawaban dan pembahasan singkat. "
        "Untuk materi ajar, gunakan struktur yang rapi dengan tujuan, materi inti, aktivitas, dan asesmen."
    )


def _normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def _extract_key_points(text, limit=8):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []
    for sentence in sentences:
        value = sentence.strip()
        if len(value) < 40:
            continue
        cleaned.append(value[:260])
        if len(cleaned) >= limit:
            break
    if cleaned:
        return cleaned
    return [text[:260]]


def _summary_output(title, key_points):
    bullets = "\n".join(f"- {point}" for point in key_points)
    return (
        f"## Ringkasan Dokumen: {title}\n\n"
        "### Poin Penting\n"
        f"{bullets}\n\n"
        "### Rekomendasi Penggunaan\n"
        "- Jadikan poin penting di atas sebagai pengantar diskusi kelas.\n"
        "- Minta siswa memberi contoh penerapan sesuai materi.\n"
        "- Tutup pembelajaran dengan refleksi singkat."
    )


def _questions_output(subject, grade, key_points, count):
    items = []
    for index in range(1, count + 1):
        point = key_points[(index - 1) % len(key_points)]
        items.append(
            f"{index}. Berdasarkan materi {subject} untuk {grade}, apa gagasan utama dari pernyataan berikut?\n"
            f"   \"{point}\"\n"
            "   A. Gagasan utama sesuai konteks dokumen\n"
            "   B. Informasi yang tidak berkaitan\n"
            "   C. Kesimpulan tanpa dasar dokumen\n"
            "   D. Pernyataan yang berlawanan\n"
            "   Kunci: A\n"
            "   Pembahasan: Jawaban A paling sesuai karena merujuk langsung pada isi dokumen."
        )
    return "## Draft Soal\n\n" + "\n\n".join(items)


def _lesson_material_output(subject, grade, key_points):
    bullets = "\n".join(f"- {point}" for point in key_points[:6])
    return (
        f"## Draft Materi Ajar {subject} - {grade}\n\n"
        "### Tujuan Pembelajaran\n"
        "- Siswa memahami konsep utama dari dokumen.\n"
        "- Siswa mampu menjelaskan kembali materi dengan bahasa sendiri.\n\n"
        "### Materi Inti\n"
        f"{bullets}\n\n"
        "### Aktivitas Kelas\n"
        "- Apersepsi: guru mengaitkan materi dengan pengalaman siswa.\n"
        "- Diskusi: siswa membaca poin materi dan menyusun pertanyaan.\n"
        "- Penutup: siswa menulis satu kesimpulan dan satu hal yang belum dipahami."
    )


def _learning_ideas_output(subject, grade, key_points):
    return (
        f"## Ide Pembelajaran {subject} - {grade}\n\n"
        "1. Diskusi Berpasangan\n"
        f"   Gunakan topik: {key_points[0]}\n\n"
        "2. Peta Konsep\n"
        "   Siswa membuat hubungan antar gagasan utama dari dokumen.\n\n"
        "3. Kuis Cepat\n"
        "   Guru menyiapkan pertanyaan singkat berdasarkan ringkasan dokumen.\n\n"
        "4. Refleksi Akhir\n"
        "   Siswa menulis penerapan materi dalam kehidupan sehari-hari."
    )


def _request_type_label(request_type):
    labels = {
        "summary": "Ringkas dokumen",
        "questions": "Buat soal",
        "lesson_material": "Buat materi ajar",
        "learning_ideas": "Buat ide pembelajaran",
    }
    return labels.get(request_type, request_type)


def _safe_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 1), 25)
