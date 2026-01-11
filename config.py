import os
from dotenv import load_dotenv

# Muat variabel dari file .env (untuk di laptop)
load_dotenv()


class Config:
    # 1. SECRET KEY
    # Tambahkan 'or ...' sebagai cadangan agar tidak error jika lupa set env
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-default-jika-lupa'

    # 2. DATABASE CONFIGURATION (BAGIAN KRUSIAL)
    # Ambil URL dari environment variable
    db_uri = os.environ.get('DATABASE_URL')

    # --- FIX WAJIB UNTUK RENDER ---
    # Render sering memberikan URL 'postgres://', tapi SQLAlchemy butuh 'postgresql://'
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)

    # Set URI Akhir
    # Jika db_uri kosong (misal di laptop belum setting), otomatis pakai SQLite
    SQLALCHEMY_DATABASE_URI = db_uri or 'sqlite:///sekolah_lokal.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
