from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret: str = "change-me"

    # ---------- LLM provider --------------------------------------------
    # `llm_provider` picks which backend the workspace talks to. The
    # default (`anthropic`) preserves prior behaviour; the others let a
    # firm route to whichever backend matches their compliance / cost /
    # data-residency constraints.
    #
    # Every provider exposes the same two tiers:
    #   - "default"  — the heavy model (analysis, drafting, review)
    #   - "fast"     — the light model (reranking, decomposition, HyDE,
    #                  contextual augmentation, CRAG grading)
    llm_provider: Literal[
        "anthropic", "azure", "openai", "openrouter", "ollama"
    ] = "anthropic"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model_default: str = "claude-opus-4-7"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"

    # OpenAI (api.openai.com) — vanilla OpenAI account, no Azure
    openai_api_key: str | None = None
    openai_base_url: str | None = None  # override only if proxying
    openai_model_default: str = "gpt-4o"
    openai_model_fast: str = "gpt-4o-mini"
    openai_organization: str | None = None

    # Azure OpenAI — `endpoint` is the resource base URL (e.g.
    # https://my-resource.openai.azure.com), and the deployments map to
    # whichever models the firm has provisioned.
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment_default: str | None = None
    azure_openai_deployment_fast: str | None = None

    # OpenRouter — OpenAI-compatible API at openrouter.ai
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_default: str = "anthropic/claude-3.5-sonnet"
    openrouter_model_fast: str = "anthropic/claude-3.5-haiku"

    # Optional headers OpenRouter recommends — used for routing /
    # provider-side attribution. Safe defaults; firms can override.
    openrouter_referer: str = "https://github.com/alfiansmart/legalai"
    openrouter_title: str = "LegalAI Indonesian Legal Workspace"

    # Ollama — local-first deployment via Ollama's OpenAI-compatible
    # endpoint. No real API key needed but the OpenAI SDK requires a
    # non-empty string, so we pass a sentinel ("ollama") by default.
    # Model strings are the Ollama tag, e.g. "llama3.1:8b", "qwen2.5:7b",
    # "qwen2.5-coder:14b" (good tool-use support).
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_model_default: str = "qwen2.5:14b"
    ollama_model_fast: str = "qwen2.5:3b"

    # ---------- Embeddings ---------------------------------------------
    # Embedding model is provider-agnostic — we run e5-large locally so
    # the same vectors index against pasal rows regardless of which LLM
    # answers the question.
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dim: int = 1024

    database_url: str = "postgresql+psycopg://legalai:legalai@postgres:5432/legalai"
    redis_url: str = "redis://redis:6379/0"

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

    # ---------- Helpers ------------------------------------------------

    def llm_api_key(self) -> str | None:
        """Return the API key for the active provider.

        Ollama is treated as 'always available' — the SDK still needs a
        non-empty string in its `api_key` slot, but no real credential
        is required because the endpoint is local. We return the
        sentinel value the SDK accepts so callers don't short-circuit
        the way they do for missing-credential paths on hosted
        providers.
        """
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        if self.llm_provider == "azure":
            return self.azure_openai_api_key
        if self.llm_provider == "openrouter":
            return self.openrouter_api_key
        if self.llm_provider == "ollama":
            return self.ollama_api_key or "ollama"
        return None

    def llm_model_default(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_model_default
        if self.llm_provider == "openai":
            return self.openai_model_default
        if self.llm_provider == "azure":
            return (
                self.azure_openai_deployment_default
                or self.azure_openai_deployment_fast
                or "gpt-4o"
            )
        if self.llm_provider == "openrouter":
            return self.openrouter_model_default
        if self.llm_provider == "ollama":
            return self.ollama_model_default
        return self.anthropic_model_default

    def llm_model_fast(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_model_fast
        if self.llm_provider == "openai":
            return self.openai_model_fast
        if self.llm_provider == "azure":
            return (
                self.azure_openai_deployment_fast
                or self.azure_openai_deployment_default
                or "gpt-4o-mini"
            )
        if self.llm_provider == "openrouter":
            return self.openrouter_model_fast
        if self.llm_provider == "ollama":
            return self.ollama_model_fast
        return self.anthropic_model_fast


@lru_cache
def get_settings() -> Settings:
    return Settings()
