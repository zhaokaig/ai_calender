from flask import Blueprint, jsonify, request

from ..asr import transcribe_audio
from ..auth import login_required

transcriptions_bp = Blueprint("transcriptions", __name__, url_prefix="/api")


@transcriptions_bp.post("/transcriptions")
@login_required
def transcription_route():
    audio_file = request.files.get("file")

    if audio_file is None:
        return jsonify({"error": "file is required"}), 400

    try:
        text = transcribe_audio(audio_file)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 502

    return jsonify({"text": text})
