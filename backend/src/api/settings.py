from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_ai import ModelSettings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WALT_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    ai_model: str | None = None
    ai_temperature: float | None = Field(default=None, ge=0, le=2)
    ai_max_tokens: int | None = Field(default=None, gt=0)

    @property
    def ai_model_settings(self) -> ModelSettings:
        """Build the provider-neutral settings passed to a Pydantic AI agent."""
        settings = ModelSettings()
        if self.ai_temperature is not None:
            settings["temperature"] = self.ai_temperature
        if self.ai_max_tokens is not None:
            settings["max_tokens"] = self.ai_max_tokens
        return settings


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""
    return Settings()
