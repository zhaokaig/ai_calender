from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import current_app
from openai import OpenAI, OpenAIError

from .logging_config import get_logger

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
logger = get_logger("asr")


class AudioTranscriptionError(RuntimeError):
    pass


def transcribe_audio(file_storage) -> str:
    filename = file_storage.filename or "audio.webm"
    suffix = Path(filename).suffix.lower() or ".webm"
    logger.info(
        "asr_transcribe_attempt filename=%s suffix=%s model=%s",
        filename,
        suffix,
        current_app.config["ASR_MODEL"],
    )

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.warning("asr_transcribe_failed filename=%s reason=missing_openai_api_key", filename)
        raise ValueError("OPENAI_API_KEY is required for audio transcription")

    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        logger.warning("asr_transcribe_failed filename=%s reason=unsupported_audio_type", filename)
        raise ValueError("unsupported audio file type")

    with NamedTemporaryFile(suffix=suffix) as temp_file:
        file_storage.save(temp_file.name)
        temp_file.seek(0)

        if Path(temp_file.name).stat().st_size == 0:
            logger.warning("asr_transcribe_failed filename=%s reason=empty_file", filename)
            raise ValueError("audio file is empty")

        client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])

        try:
            with open(temp_file.name, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=current_app.config["ASR_MODEL"],
                    file=audio_file,
                )
        except OpenAIError as error:
            logger.exception("asr_transcribe_failed filename=%s reason=openai_error", filename)
            raise AudioTranscriptionError(f"audio transcription failed: {error}") from error

    logger.info("asr_transcribe_success filename=%s text_length=%s", filename, len(transcription.text or ""))

    return transcription.text
