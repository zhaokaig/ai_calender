from flask import Blueprint, jsonify, request

from ..asr import AudioTranscriptionError, transcribe_audio
from ..auth import login_required
from ..logging_config import get_logger

transcriptions_bp = Blueprint("transcriptions", __name__, url_prefix="/api")
logger = get_logger("routes.transcriptions")


@transcriptions_bp.post("/transcriptions")
@login_required
def transcription_route():
    audio_file = request.files.get("file") or request.files.get("audio")

    if audio_file is None:
        logger.warning("transcription_failed reason=missing_file")
        return jsonify({"error": "file is required"}), 400

    logger.info("transcription_received filename=%s", audio_file.filename)

    try:
        text = transcribe_audio(audio_file)
    except ValueError as error:
        logger.warning("transcription_failed filename=%s reason=%s", audio_file.filename, str(error))
        return jsonify({"error": str(error)}), 400
    except AudioTranscriptionError as error:
        logger.error("transcription_failed filename=%s reason=asr_error", audio_file.filename)
        return jsonify({"error": str(error)}), 502

    logger.info("transcription_success filename=%s text_length=%s", audio_file.filename, len(text or ""))

    return jsonify({"text": text})
