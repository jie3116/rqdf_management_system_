import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError("FATAL: SECRET_KEY tidak ditemukan di environment variables!")

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    AUTH_RATE_LIMIT_ENABLED = os.environ.get('AUTH_RATE_LIMIT_ENABLED', 'true').strip().lower() in {
        '1', 'true', 'yes', 'on'
    }
    AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('AUTH_RATE_LIMIT_WINDOW_SECONDS', '300'))
    AUTH_RATE_LIMIT_IDENTIFIER_ATTEMPTS = int(os.environ.get('AUTH_RATE_LIMIT_IDENTIFIER_ATTEMPTS', '5'))
    AUTH_RATE_LIMIT_IDENTIFIER_IP_ATTEMPTS = int(os.environ.get('AUTH_RATE_LIMIT_IDENTIFIER_IP_ATTEMPTS', '5'))
    AUTH_RATE_LIMIT_IP_ATTEMPTS = int(os.environ.get('AUTH_RATE_LIMIT_IP_ATTEMPTS', '30'))
    AUTH_RATE_LIMIT_CLEANUP_PROBABILITY = float(os.environ.get('AUTH_RATE_LIMIT_CLEANUP_PROBABILITY', '0.01'))
    AUTH_RATE_LIMIT_HASH_PEPPER = os.environ.get('AUTH_RATE_LIMIT_HASH_PEPPER', '')

    # Online meeting backend options:
    # - public_jitsi (default, demo)
    # - jaas (8x8.vc + JWT)
    # - self_host (Jitsi secure domain milik sendiri)
    ONLINE_MEETING_BACKEND = os.environ.get('ONLINE_MEETING_BACKEND', 'public_jitsi')
    JITSI_PUBLIC_BASE_URL = os.environ.get('JITSI_PUBLIC_BASE_URL', 'https://meet.jit.si')
    JITSI_SELF_HOST_BASE_URL = os.environ.get('JITSI_SELF_HOST_BASE_URL', '')

    # JaaS JWT (8x8.vc)
    JITSI_JAAS_DOMAIN = os.environ.get('JITSI_JAAS_DOMAIN', '8x8.vc')
    JITSI_JAAS_APP_ID = os.environ.get('JITSI_JAAS_APP_ID', '')
    JITSI_JAAS_KID = os.environ.get('JITSI_JAAS_KID', '')
    JITSI_JAAS_PRIVATE_KEY = os.environ.get('JITSI_JAAS_PRIVATE_KEY', '')
    JITSI_JAAS_TOKEN_TTL_SECONDS = int(os.environ.get('JITSI_JAAS_TOKEN_TTL_SECONDS', '7200'))
    JITSI_JAAS_ROOM_CLAIM_MODE = os.environ.get('JITSI_JAAS_ROOM_CLAIM_MODE', 'wildcard')

    # AI Assistant
    AI_ASSISTANT_PROVIDER = os.environ.get('AI_ASSISTANT_PROVIDER', 'local').strip().lower()
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-5.2')
    OPENAI_MAX_OUTPUT_TOKENS = int(os.environ.get('OPENAI_MAX_OUTPUT_TOKENS', '2500'))
