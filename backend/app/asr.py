import base64
import mimetypes
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import current_app
from openai import OpenAI, OpenAIError

from .logging_config import get_logger

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
AUDIO_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
}
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

    if not current_app.config.get("DASHSCOPE_API_KEY"):
        logger.warning("asr_transcribe_failed filename=%s reason=missing_dashscope_api_key", filename)
        raise ValueError("语音服务还没有配置好，暂时不能识别录音。")

    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        logger.warning("asr_transcribe_failed filename=%s reason=unsupported_audio_type", filename)
        raise ValueError("这个录音格式我暂时识别不了，换一种方式再试试吧。")

    with NamedTemporaryFile(suffix=suffix) as temp_file:
        file_storage.save(temp_file.name)
        temp_file.seek(0)

        if Path(temp_file.name).stat().st_size == 0:
            logger.warning("asr_transcribe_failed filename=%s reason=empty_file", filename)
            raise ValueError("你说话了吗？我没听见，再说一遍吧。")

        mime_type = _get_audio_mime_type(file_storage.mimetype, suffix)
        data_uri = _build_audio_data_uri(temp_file.name, mime_type)
        client = OpenAI(
            api_key=current_app.config["DASHSCOPE_API_KEY"],
            base_url=current_app.config["DASHSCOPE_BASE_URL"],
        )

        try:
            completion = client.chat.completions.create(
                model=current_app.config["ASR_MODEL"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": data_uri,
                                },
                            }
                        ],
                    }
                ],
                stream=False,
                extra_body={
                    "asr_options": {
                        "enable_itn": current_app.config["ASR_ENABLE_ITN"],
                    }
                },
            )
        except OpenAIError as error:
            logger.exception("asr_transcribe_failed filename=%s reason=openai_error", filename)
            raise AudioTranscriptionError("刚才没能听清这段录音，请再说一遍吧。") from error

    text = completion.choices[0].message.content or ""

    if not text.strip():
        logger.warning("asr_transcribe_failed filename=%s reason=empty_transcript", filename)
        raise ValueError("你说话了吗？我没听见，再说一遍吧。")

    logger.info("asr_transcribe_success filename=%s text_length=%s", filename, len(text))

    return text


def _build_audio_data_uri(file_path: str, mime_type: str) -> str:
    audio_base64 = base64.b64encode(Path(file_path).read_bytes()).decode()
    return f"data:{mime_type};base64,{audio_base64}"


def _get_audio_mime_type(upload_mime_type: str | None, suffix: str) -> str:
    if upload_mime_type and upload_mime_type.startswith("audio/"):
        return upload_mime_type

    return AUDIO_MIME_TYPES.get(suffix) or mimetypes.types_map.get(suffix) or "audio/webm"
