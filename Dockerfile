# Gunakan image Python yang ringan
FROM python:3.9-slim

# Set folder kerja di dalam container
WORKDIR /app

# Copy file requirements dulu (agar caching efisien)
COPY requirements.txt .

# Install dependencies (library)
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kodingan ke dalam container
COPY . .

# Buka port 8000 (sesuai settingan flask/gunicorn nanti)
EXPOSE 8000

# Perintah default untuk menjalankan aplikasi
# Ganti 'app.py' dengan nama file utama aplikasi Anda jika beda (misal: run.py)
CMD ["python", "run.py"]