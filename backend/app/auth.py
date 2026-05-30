from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_db
from .logging_config import get_logger

logger = get_logger("auth")


def register_user(data: dict) -> dict:
    username = _required_text(data, "username")
    password = _required_text(data, "password")
    logger.info("register_attempt username=%s", username)

    if len(password) < 6:
        logger.warning("register_failed username=%s reason=weak_password", username)
        raise ValueError("password must be at least 6 characters")

    try:
        cursor = get_db().execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        get_db().commit()
    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            logger.warning("register_failed username=%s reason=username_exists", username)
            raise ValueError("username already exists") from error
        raise

    user = get_user(cursor.lastrowid)
    logger.info("register_success user_id=%s username=%s", user["id"], username)

    return {
        "user": user,
        "access_token": create_access_token(user["id"]),
    }


def login_user(data: dict) -> dict:
    username = _required_text(data, "username")
    password = _required_text(data, "password")
    logger.info("login_attempt username=%s", username)

    row = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        logger.warning("login_failed username=%s reason=invalid_credentials", username)
        raise ValueError("invalid username or password")

    user = _serialize_user(dict(row))
    logger.info("login_success user_id=%s username=%s", user["id"], username)

    return {
        "user": user,
        "access_token": create_access_token(user["id"]),
    }


def get_user(user_id: int) -> dict | None:
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _serialize_user(dict(row)) if row else None


def create_access_token(user_id: int) -> str:
    serializer = _get_serializer()
    return serializer.dumps({"user_id": user_id})


def get_current_user() -> dict | None:
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = _get_serializer().loads(token, max_age=current_app.config["ACCESS_TOKEN_MAX_AGE"])
    except (BadSignature, SignatureExpired):
        return None

    return get_user(payload["user_id"])


def login_required(route):
    @wraps(route)
    def wrapped_route(*args, **kwargs):
        user = get_current_user()

        if user is None:
            logger.warning("auth_required_failed path=%s", request.path)
            return jsonify({"error": "authentication required"}), 401

        g.current_user = user
        return route(*args, **kwargs)

    return wrapped_route


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="access-token")


def _serialize_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }


def _required_text(data: dict, key: str) -> str:
    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")

    return value.strip()
