# Gunakan image Python yang ringan
FROM python:3.10-slim

# Set folder kerja di dalam container
WORKDIR /app

# Copy file requirements dulu (agar caching efisien)
COPY requirements.txt .

# Install dependencies (library)
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kodingan ke dalam container
COPY . .

# Buka port 8000 (sesuai settingan flask/gunicorn)
EXPOSE 8000

# Perintah default untuk menjalankan aplikasi
CMD ["python", "run.py"]