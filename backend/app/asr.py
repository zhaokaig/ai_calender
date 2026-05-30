from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import current_app
from openai import OpenAI, OpenAIError

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}


class AudioTranscriptionError(RuntimeError):
    pass


def transcribe_audio(file_storage) -> str:
    if not current_app.config.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required for audio transcription")

    filename = file_storage.filename or "audio.webm"
    suffix = Path(filename).suffix.lower() or ".webm"

    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError("unsupported audio file type")

    with NamedTemporaryFile(suffix=suffix) as temp_file:
        file_storage.save(temp_file.name)
        temp_file.seek(0)

        if Path(temp_file.name).stat().st_size == 0:
            raise ValueError("audio file is empty")

        client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])

        try:
            with open(temp_file.name, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=current_app.config["ASR_MODEL"],
                    file=audio_file,
                )
        except OpenAIError as error:
            current_app.logger.exception("OpenAI audio transcription failed")
            raise AudioTranscriptionError(f"audio transcription failed: {error}") from error

    return transcription.text
