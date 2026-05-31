from flask import Blueprint, g, jsonify, request

from ..agent.graph import run_voice_command_graph
from ..auth import login_required
from ..logging_config import get_logger

voice_command_bp = Blueprint("voice_command", __name__, url_prefix="/api")
logger = get_logger("routes.voice_command")


@voice_command_bp.post("/voice-command")
@login_required
def voice_command_route():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    timezone = data.get("timezone", "Asia/Shanghai")

    if not isinstance(text, str) or not text.strip():
        logger.warning("voice_command_failed user_id=%s reason=missing_text", g.current_user["id"])
        return jsonify({"error": "我还没收到要处理的内容，请说一句日程需求或输入文字。"}), 400

    logger.info(
        "voice_command_received user_id=%s text_length=%s timezone=%s text=%s",
        g.current_user["id"],
        len(text.strip()),
        timezone,
        text.strip(),
    )
    response = run_voice_command_graph(g.current_user["id"], text, timezone)
    logger.info(
        "voice_command_finished user_id=%s status=%s intent=%s",
        g.current_user["id"],
        response.status,
        response.intent,
    )

    return jsonify(response.to_dict())
