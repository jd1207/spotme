from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    whoop_client_id: str = ""
    whoop_client_secret: str = ""
    whoop_access_token: str = ""
    database_url: str = "sqlite:///./spotme.db"
    video_dir: str = "./videos"
    ntfy_topic: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
