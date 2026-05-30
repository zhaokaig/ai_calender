from flask import current_app
from openai import OpenAI, OpenAIError

from .logging_config import get_logger

logger = get_logger("text_normalizer")


def normalize_transcript(text: str) -> str:
    original_text = text.strip()

    if not original_text:
        return original_text

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.info("transcript_normalize_skipped reason=missing_api_key")
        return original_text

    logger.info(
        "transcript_normalize_attempt text_length=%s model=%s",
        len(original_text),
        current_app.config["AGENT_MODEL"],
    )

    client = OpenAI(
        api_key=current_app.config["OPENAI_API_KEY"],
        base_url=current_app.config["OPENAI_BASE_URL"],
    )

    try:
        completion = client.chat.completions.create(
            model=current_app.config["AGENT_MODEL"],
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是语音转文字后的文本清洗器。"
                        "删除口癖、重复词、无意义停顿和语气词，让文本更结构化、流畅。"
                        "必须保留所有人名、公司名、地点、事件名、时间、日期、数字和动作词。"
                        "不要纠正可能的错别字、谐音词或专有名词，不要新增信息。"
                        "如果一句话里有多条日程指令，用清楚的逗号或分号分隔。"
                        "只输出清洗后的中文文本，不要解释。"
                    ),
                },
                {
                    "role": "user",
                    "content": original_text,
                },
            ],
        )
    except OpenAIError:
        logger.exception("transcript_normalize_failed reason=openai_error")
        return original_text

    normalized_text = (completion.choices[0].message.content or "").strip()

    if not normalized_text:
        logger.warning("transcript_normalize_empty fallback=original")
        return original_text

    logger.info(
        "transcript_normalize_success original_length=%s normalized_length=%s original_text=%s normalized_text=%s",
        len(original_text),
        len(normalized_text),
        original_text,
        normalized_text,
    )

    return normalized_text
