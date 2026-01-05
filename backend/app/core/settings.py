from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://dental_pms:change-me@localhost:5432/dental_pms"

settings = Settings()
