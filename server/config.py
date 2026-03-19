from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./spotme.db"
    video_dir: str = "./videos"
    ntfy_topic: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")


def today_eastern() -> str:
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")
