import os


class Config:
    APP_NAME = os.getenv("APP_NAME", "ai-calender")
    ENVIRONMENT = os.getenv("APP_ENV", "development")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "instance/ai_calender.sqlite")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    ACCESS_TOKEN_MAX_AGE = int(os.getenv("ACCESS_TOKEN_MAX_AGE", "604800"))
    LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    LLM_API_URL = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
