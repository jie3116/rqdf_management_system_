import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse

import jwt
from flask import current_app


MEETING_PROVIDER_JITSI = "JITSI"
MEETING_PROVIDER_EXTERNAL = "EXTERNAL"
MEETING_PROVIDER_LIVEKIT = "LIVEKIT"

MEETING_PROVIDER_OPTIONS = (
    MEETING_PROVIDER_JITSI,
    MEETING_PROVIDER_EXTERNAL,
    MEETING_PROVIDER_LIVEKIT,
)

MEETING_BACKEND_PUBLIC = "public_jitsi"
MEETING_BACKEND_JAAS = "jaas"
MEETING_BACKEND_SELF_HOST = "self_host"


def _slug_token(value):
    token = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip()).strip("-").lower()
    return token or "room"


def _runtime_config():
    return {
        "backend": (current_app.config.get("ONLINE_MEETING_BACKEND") or MEETING_BACKEND_PUBLIC).strip().lower(),
        "jitsi_public_base": (current_app.config.get("JITSI_PUBLIC_BASE_URL") or "https://meet.jit.si").rstrip("/"),
        "jitsi_self_host_base": (current_app.config.get("JITSI_SELF_HOST_BASE_URL") or "").rstrip("/"),
        "jaas_domain": (current_app.config.get("JITSI_JAAS_DOMAIN") or "8x8.vc").strip(),
        "jaas_app_id": (current_app.config.get("JITSI_JAAS_APP_ID") or "").strip(),
        "jaas_kid": (current_app.config.get("JITSI_JAAS_KID") or "").strip(),
        "jaas_private_key": (current_app.config.get("JITSI_JAAS_PRIVATE_KEY") or "").replace("\\n", "\n"),
        "jaas_ttl_seconds": int(current_app.config.get("JITSI_JAAS_TOKEN_TTL_SECONDS") or 7200),
        "jaas_room_claim": (current_app.config.get("JITSI_JAAS_ROOM_CLAIM_MODE") or "wildcard").strip().lower(),
    }


def _detect_backend_label(runtime):
    backend = runtime["backend"]
    if backend == MEETING_BACKEND_JAAS:
        return "Jitsi as a Service (JWT)"
    if backend == MEETING_BACKEND_SELF_HOST:
        return "Jitsi Self-Host"
    return "Jitsi Public"


def normalize_provider(raw_provider, meeting_url=None):
    provider = (raw_provider or "").strip().upper()
    if provider in MEETING_PROVIDER_OPTIONS:
        return provider

    haystack = f"{raw_provider or ''} {meeting_url or ''}".lower()
    if "jitsi" in haystack or "meet.jit.si" in haystack or "8x8.vc" in haystack:
        return MEETING_PROVIDER_JITSI
    if "livekit" in haystack:
        return MEETING_PROVIDER_LIVEKIT
    return MEETING_PROVIDER_EXTERNAL


def _extract_room_from_url(meeting_url):
    raw = (meeting_url or "").strip()
    if not raw:
        return None
    if raw.startswith("livekit://"):
        return raw.replace("livekit://", "", 1).strip() or None
    parsed = urlparse(raw)
    if not parsed.path:
        return None
    path = parsed.path.strip("/")
    if not path:
        return None
    parts = [token for token in path.split("/") if token]
    if len(parts) >= 2 and parts[0].startswith("vpaas-magic-cookie-"):
        return parts[-1]
    room = parts[-1]
    room = room.split("?")[0].split("#")[0].strip()
    return room or None


def _build_room_name(class_name, session_title):
    return f"rqdf-{_slug_token(class_name)}-{_slug_token(session_title)}"


def _build_url(base_url, room_name):
    safe_room = quote(room_name or "rqdf-room")
    return f"{base_url}/{safe_room}"


def _build_jaas_room_name(app_id, room_name):
    clean_room = room_name.strip("/")
    return f"{app_id}/{clean_room}"


def _is_jaas_config_ready(runtime):
    return bool(runtime["jaas_app_id"] and runtime["jaas_kid"] and runtime["jaas_private_key"])


def _build_jaas_jwt(runtime, room_name, display_name, is_moderator, user_id, email=None):
    now = datetime.now(timezone.utc)
    nbf = int(now.timestamp())
    exp = int((now + timedelta(seconds=max(300, runtime["jaas_ttl_seconds"]))).timestamp())
    room_claim = "*"
    if runtime["jaas_room_claim"] == "exact":
        room_claim = _build_jaas_room_name(runtime["jaas_app_id"], room_name)

    payload = {
        "aud": "jitsi",
        "iss": "chat",
        "sub": runtime["jaas_app_id"],
        "room": room_claim,
        "nbf": nbf,
        "exp": exp,
        "context": {
            "user": {
                "id": str(user_id or _slug_token(display_name or "user")),
                "name": (display_name or "Peserta").strip(),
                "email": (email or "").strip() or None,
                "moderator": "true" if is_moderator else "false",
            },
            "features": {
                "livestreaming": False,
                "recording": False,
                "transcription": False,
                "outbound-call": False,
            },
            "room": {
                "regex": False,
            },
        },
    }
    if payload["context"]["user"]["email"] is None:
        payload["context"]["user"].pop("email")

    token = jwt.encode(
        payload,
        runtime["jaas_private_key"],
        algorithm="RS256",
        headers={"kid": runtime["jaas_kid"], "typ": "JWT"},
    )
    return token


def resolve_provider_and_url(provider_raw, meeting_url_raw, class_name, session_title):
    provider = normalize_provider(provider_raw, meeting_url_raw)
    meeting_url = (meeting_url_raw or "").strip()

    if provider == MEETING_PROVIDER_JITSI:
        room_name = _extract_room_from_url(meeting_url)
        if not room_name:
            room_name = _build_room_name(class_name, session_title)

        runtime = _runtime_config()
        if runtime["backend"] == MEETING_BACKEND_JAAS and runtime["jaas_app_id"]:
            room_path = _build_jaas_room_name(runtime["jaas_app_id"], room_name)
            return provider, _build_url(f"https://{runtime['jaas_domain']}", room_path)

        if runtime["backend"] == MEETING_BACKEND_SELF_HOST and runtime["jitsi_self_host_base"]:
            return provider, _build_url(runtime["jitsi_self_host_base"], room_name)

        return provider, _build_url(runtime["jitsi_public_base"], room_name)

    if provider == MEETING_PROVIDER_LIVEKIT:
        room_name = _extract_room_from_url(meeting_url) or _build_room_name(class_name, session_title)
        return provider, f"livekit://{room_name}"

    return provider, meeting_url


def build_join_payload(session, display_name, is_moderator=False, user_id=None, email=None):
    provider = normalize_provider(getattr(session, "meeting_provider", None), getattr(session, "meeting_url", None))
    meeting_url = (getattr(session, "meeting_url", None) or "").strip()
    title = getattr(session, "title", "Sesi Online")

    if provider == MEETING_PROVIDER_JITSI:
        room_name = _extract_room_from_url(meeting_url) or _build_room_name(
            getattr(getattr(session, "class_room", None), "name", "kelas"),
            title,
        )
        runtime = _runtime_config()
        backend_label = _detect_backend_label(runtime)

        if runtime["backend"] == MEETING_BACKEND_JAAS:
            if not _is_jaas_config_ready(runtime):
                return {
                    "provider": provider,
                    "mode": "misconfigured",
                    "label": backend_label,
                    "message": "Konfigurasi JaaS JWT belum lengkap. Isi APP_ID, KID, dan PRIVATE_KEY.",
                    "upgrade_hint": "Set env JITSI_JAAS_APP_ID, JITSI_JAAS_KID, JITSI_JAAS_PRIVATE_KEY.",
                }
            token = _build_jaas_jwt(
                runtime=runtime,
                room_name=room_name,
                display_name=display_name,
                is_moderator=is_moderator,
                user_id=user_id,
                email=email,
            )
            room_path = _build_jaas_room_name(runtime["jaas_app_id"], room_name)
            external_url = _build_url(f"https://{runtime['jaas_domain']}", room_path)
            return {
                "provider": provider,
                "mode": "embed_jaas_api",
                "label": backend_label,
                "api_domain": runtime["jaas_domain"],
                "api_script_url": f"https://{runtime['jaas_domain']}/{runtime['jaas_app_id']}/external_api.js",
                "room_name": room_path,
                "jwt": token,
                "display_name": (display_name or "Peserta").strip(),
                "external_url": external_url,
                "upgrade_hint": "Jalur LiveKit tetap siap lewat provider abstraction dan token endpoint terpisah.",
            }

        if runtime["backend"] == MEETING_BACKEND_SELF_HOST and runtime["jitsi_self_host_base"]:
            external_url = _build_url(runtime["jitsi_self_host_base"], room_name)
            return {
                "provider": provider,
                "mode": "embed_jitsi",
                "label": backend_label,
                "embed_url": external_url,
                "room_name": room_name,
                "external_url": external_url,
                "upgrade_hint": "Gunakan secure domain/prosody auth di server Jitsi untuk kontrol moderator.",
            }

        external_url = _build_url(runtime["jitsi_public_base"], room_name)
        return {
            "provider": provider,
            "mode": "external",
            "label": backend_label,
            "room_name": room_name,
            "external_url": external_url,
            "message": "Public Jitsi disarankan dibuka di tab baru untuk menghindari batasan embed demo.",
            "upgrade_hint": "Mode public untuk demo; produksi disarankan JaaS JWT atau self-host secure domain.",
        }

    if provider == MEETING_PROVIDER_LIVEKIT:
        room_name = _extract_room_from_url(meeting_url) or (meeting_url.replace("livekit://", "", 1) if meeting_url else "")
        return {
            "provider": provider,
            "mode": "livekit_placeholder",
            "label": "LiveKit",
            "room_name": room_name or "rqdf-room",
            "message": "Provider LiveKit sudah disiapkan, namun token server belum diaktifkan.",
            "upgrade_hint": "Langkah upgrade: tambahkan endpoint token LiveKit dan SDK client tanpa ubah entitas sesi.",
        }

    return {
        "provider": MEETING_PROVIDER_EXTERNAL,
        "mode": "external",
        "label": "External Meeting",
        "external_url": meeting_url,
        "message": "Sesi ini memakai provider eksternal.",
        "upgrade_hint": "Bisa dimigrasikan bertahap ke Jitsi JWT-ready atau LiveKit.",
    }
