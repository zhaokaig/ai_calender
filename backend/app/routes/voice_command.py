from flask import Blueprint, g, jsonify, request

from ..agent.graph import run_voice_command_graph
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

    response = run_voice_command_graph(g.current_user["id"], text, timezone)

    return jsonify(response.to_dict())
