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

    # Stage 21 — security hardening
    encryption_key: str = ""          # Fernet 32-byte URL-safe base64 key
    session_idle_timeout: int = 1800  # seconds before idle session expires
    sso_enabled: bool = False
    sso_client_id: str = ""
    sso_client_secret: str = ""
    sso_tenant_id: str = ""

    # Stage 29 — deployment & operations
    environment: str = "dev"          # dev | test | prod
    backup_dir: str = "data/backups"
    audit_retention_days: int = 365


settings = Settings()
