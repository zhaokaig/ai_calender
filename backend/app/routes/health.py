from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health_check():
    return jsonify(
        {
            "status": "ok",
            "service": current_app.config["APP_NAME"],
            "environment": current_app.config["ENVIRONMENT"],
        }
    )
