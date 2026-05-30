import os


class Config:
    APP_NAME = os.getenv("APP_NAME", "ai-calender")
    ENVIRONMENT = os.getenv("APP_ENV", "development")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "instance/ai_calender.sqlite")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    ACCESS_TOKEN_MAX_AGE = int(os.getenv("ACCESS_TOKEN_MAX_AGE", "604800"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ASR_MODEL = os.getenv("ASR_MODEL", "qwen3-asr-flash-2026-02-10")
    AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "instance/ai_calender.log")
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "1048576"))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "3"))
