from flask import Blueprint, g, jsonify, request

from ..agent.executor import execute_plan
from ..agent.parser import parse_command
from ..auth import login_required

voice_command_bp = Blueprint("voice_command", __name__, url_prefix="/api")


@voice_command_bp.post("/voice-command")
@login_required
def voice_command_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    timezone = data.get("timezone", "Asia/Shanghai")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "text is required"}), 400

    plan = parse_command(text, timezone)
    response = execute_plan(g.current_user["id"], plan)

    return jsonify(response.to_dict())
