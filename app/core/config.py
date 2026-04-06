from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/emaildb"
    REDIS_URL: str = "redis://localhost:6379"
    RESEND_API_KEY: str = "re_placeholder"
    RESEND_FROM_EMAIL: str = "noreply@example.com"
    REDIS_CHANNEL: str = "email_notifications"
    WORKER_COUNT: int = 5
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0  # seconds, doubled each retry
    DEAD_LETTER_CHANNEL: str = "email_notifications_dlq"
    LOG_LEVEL: str = "INFO"


settings = Settings()
