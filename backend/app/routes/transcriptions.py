from flask import Blueprint, jsonify, request

from ..asr import AudioTranscriptionError, transcribe_audio
from ..auth import login_required
from ..logging_config import get_logger
from ..text_normalizer import normalize_transcript

transcriptions_bp = Blueprint("transcriptions", __name__, url_prefix="/api")
logger = get_logger("routes.transcriptions")


@transcriptions_bp.post("/transcriptions")
@login_required
def transcription_route():
    audio_file = request.files.get("file") or request.files.get("audio")

    if audio_file is None:
        logger.warning("transcription_failed reason=missing_file")
        return jsonify({"error": "我没有收到录音，请重新录一次。"}), 400

    logger.info("transcription_received filename=%s", audio_file.filename)

    try:
        raw_text = transcribe_audio(audio_file)
        text = normalize_transcript(raw_text)

        if not text.strip():
            logger.warning("transcription_failed filename=%s reason=empty_normalized_text", audio_file.filename)
            return jsonify({"error": "你说话了吗？我没听见，再说一遍吧。"}), 400
    except ValueError as error:
        logger.warning("transcription_failed filename=%s reason=%s", audio_file.filename, str(error))
        return jsonify({"error": str(error)}), 400
    except AudioTranscriptionError as error:
        logger.error("transcription_failed filename=%s reason=asr_error", audio_file.filename)
        return jsonify({"error": str(error)}), 502

    logger.info(
        "transcription_success filename=%s raw_text_length=%s text_length=%s raw_text=%s text=%s",
        audio_file.filename,
        len(raw_text or ""),
        len(text or ""),
        raw_text,
        text,
    )

    return jsonify({"text": text, "raw_text": raw_text})
