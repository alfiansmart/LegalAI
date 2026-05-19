from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret: str = "change-me"

    anthropic_api_key: str | None = None
    anthropic_model_default: str = "claude-opus-4-7"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"

    openai_api_key: str | None = None
    openai_base_url: str | None = None

    database_url: str = "postgresql+psycopg://legalai:legalai@postgres:5432/legalai"
    redis_url: str = "redis://redis:6379/0"

    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dim: int = 1024

    s3_endpoint: str | None = None
    s3_bucket: str = "legalai"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    skills_dir: str = "skills"
    tools_dir: str = "tools"
    flows_dir: str = "flows"
    templates_dir: str = "templates"
    seed_dir: str = "seed"

    max_agent_turns: int = Field(default=20, description="Hard cap on tool-loop turns")
    context_token_budget: int = Field(default=180_000, description="Soft budget before compaction")


@lru_cache
def get_settings() -> Settings:
    return Settings()
