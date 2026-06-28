def bump_user_token_version(user):
    current_version = int(getattr(user, "token_version", None) or 0)
    user.token_version = current_version + 1
    return user.token_version


def set_user_password_and_invalidate_tokens(user, raw_password, *, must_change_password=None):
    if hasattr(user, "set_password"):
        user.set_password(raw_password)
    else:
        from werkzeug.security import generate_password_hash

        user.password_hash = generate_password_hash(raw_password)

    bump_user_token_version(user)

    if must_change_password is not None:
        user.must_change_password = must_change_password

    return user


def validate_mobile_token_version(payload, user):
    payload_version = (payload or {}).get("ver")
    if payload_version is None:
        return False

    try:
        token_version = int(payload_version)
        user_version = int(getattr(user, "token_version", None) or 0)
    except (TypeError, ValueError):
        return False

    return token_version == user_version
