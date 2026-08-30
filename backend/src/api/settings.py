from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment or local env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        env_prefix="WALT_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    openai_api_key: SecretStr | None = None
    openai_realtime_model: str = "gpt-realtime-2.1"
    openai_realtime_voice: str = "marin"
    openai_realtime_vad_threshold: float = Field(default=0.9, ge=0, le=1)
    openai_realtime_noise_reduction: Literal["near_field", "far_field"] = "far_field"
    daytona_api_key: SecretStr | None = None
    daytona_api_url: str | None = None
    daytona_snapshot: str | None = None
    demo_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    expiry_sweep_seconds: float = Field(default=5, gt=0, le=60)
    novnc_port: int = Field(default=6080, ge=1, le=65535)
    seed_path: str = "/opt/atomic/dist/seed.json"
    start_command: str = "start-demo"
    browser_action_timeout_seconds: int = Field(default=15, ge=1, le=60)
    atomic_origin: str = "http://127.0.0.1:8080"
    screenshot_quality: int = Field(default=70, ge=20, le=95)
    screenshot_scale: float = Field(default=0.75, gt=0, le=1)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""
    return Settings()
