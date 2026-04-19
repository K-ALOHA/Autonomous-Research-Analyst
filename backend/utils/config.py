from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="autonomous-research-analyst-backend", alias="APP_NAME")
    environment: Literal["local", "development", "staging", "production"] = Field(
        default="local", alias="ENV"
    )

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    cors_allow_origins: str = Field(default="*", alias="CORS_ALLOW_ORIGINS")

    database_url: str = Field(default="sqlite+aiosqlite:///./ara.db", alias="DATABASE_URL")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    # Required by OpenRouter for attribution / rankings (sent on every request).
    openrouter_site_url: str = Field(default="http://localhost", alias="OPENROUTER_SITE_URL")
    openrouter_app_name: str = Field(default="autonomous-research-analyst", alias="OPENROUTER_APP_NAME")
    tavily_api_key: Optional[str] = Field(default=None, alias="TAVILY_API_KEY")
    planner_model: str = Field(default="deepseek/deepseek-chat", alias="PLANNER_MODEL")
    analyst_model: str = Field(default="deepseek/deepseek-chat", alias="ANALYST_MODEL")

    langfuse_public_key: Optional[str] = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: Optional[str] = Field(default=None, alias="LANGFUSE_HOST")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
