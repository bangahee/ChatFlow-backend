from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: SecretStr = SecretStr("change-me")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=1440, gt=0)
    database_url: str = "sqlite:///./chatflow.db"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5-nano"
    openai_timeout_seconds: float = Field(default=20, gt=0)
    openai_max_retries: int = Field(default=3, ge=0)
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized, unique origins from the comma-delimited setting."""
        origins: list[str] = []
        for origin in self.cors_origins.split(","):
            normalized = origin.strip().rstrip("/")
            if normalized and normalized not in origins:
                origins.append(normalized)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
