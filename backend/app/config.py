import os


class Config:
    APP_NAME = os.getenv("APP_NAME", "ai-calender")
    ENVIRONMENT = os.getenv("APP_ENV", "development")
