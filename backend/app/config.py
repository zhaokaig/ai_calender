import os

from .env import load_env_file

load_env_file()


def _env(name: str):
    value = os.getenv(name)

    if value in (None, "", "replace-with-your-dashscope-api-key"):
        return None

    return value


class Config:
    APP_NAME = os.getenv("APP_NAME", "ai-calender")
    ENVIRONMENT = os.getenv("APP_ENV", "development")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "instance/ai_calender.sqlite")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    ACCESS_TOKEN_MAX_AGE = int(os.getenv("ACCESS_TOKEN_MAX_AGE", "604800"))
    DASHSCOPE_API_KEY = _env("DASHSCOPE_API_KEY")
    DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    OPENAI_API_KEY = _env("AGENT_API_KEY") or DASHSCOPE_API_KEY or _env("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or DASHSCOPE_BASE_URL
    ASR_MODEL = os.getenv("ASR_MODEL", "qwen3-asr-flash-2026-02-10")
    ASR_ENABLE_ITN = os.getenv("ASR_ENABLE_ITN", "false").lower() == "true"
    AGENT_MODEL = os.getenv("AGENT_MODEL", "qwen-plus")
    AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "instance/ai_calender.log")
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "1048576"))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "3"))
