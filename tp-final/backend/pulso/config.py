from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    database_url: str = 'postgresql+psycopg://pulso:pulso@127.0.0.1:5432/pulso?connect_timeout=5'
    cookie_secure: bool = False
    session_days: int = 7
    max_body_bytes: int = 1024 * 1024
    max_upload_bytes: int = 5 * 1024 * 1024
    smtp_host: str = '127.0.0.1'
    smtp_port: int = 1025
    smtp_from: str = 'Pulso <notificaciones@pulso.local>'
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_starttls: bool = False
    smtp_ssl: bool = False
    smtp_timeout: float = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
