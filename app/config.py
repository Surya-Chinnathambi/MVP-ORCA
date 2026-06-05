from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///data/app.db"
    secret_key: str = "change-me-in-production"
    debug: bool = False

    admin_email: str = "admin@techguard.local"
    admin_password: str = "changeme"

    telegram_bot_token: str = ""
    claude_api_key: str = ""

    # Phase 2 — background workers
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
