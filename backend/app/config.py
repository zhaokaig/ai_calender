import os


class Config:
    APP_NAME = os.getenv("APP_NAME", "ai-calender")
    ENVIRONMENT = os.getenv("APP_ENV", "development")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "instance/ai_calender.sqlite")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    ACCESS_TOKEN_MAX_AGE = int(os.getenv("ACCESS_TOKEN_MAX_AGE", "604800"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ASR_MODEL = os.getenv("ASR_MODEL", "gpt-4o-mini-transcribe")
    AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0"))
