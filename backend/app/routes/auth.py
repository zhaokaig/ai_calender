from flask import Blueprint, jsonify, request

from ..auth import login_user, register_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register_route():
    data = request.get_json(silent=True) or {}

    try:
        result = register_user(data)
    except ValueError as error:
        return _error(str(error), 400)

    return jsonify(result), 201


@auth_bp.post("/login")
def login_route():
    data = request.get_json(silent=True) or {}

    try:
        result = login_user(data)
    except ValueError as error:
        return _error(str(error), 401)

    return jsonify(result)


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code
