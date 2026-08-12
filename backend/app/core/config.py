"""Application settings, loaded from the environment.

Every configurable value lives here. Nothing reads os.environ directly.
See backend/README.md for the full variable reference.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://mediagent:dev@localhost:5432/mediagent"

    # --- auth -------------------------------------------------------------
    jwt_secret: str = "dev-only-not-a-real-secret"
    jwt_expire_minutes: int = 60

    # --- model routing ----------------------------------------------------
    # Format: "<provider>:<model>", e.g. "ollama:llama3.1:8b" or
    # "anthropic:claude-opus-5". See docs/LLM_PROVIDER_STRATEGY.md.
    llm_mechanical: str = "ollama:llama3.1:8b"
    llm_conversational: str = "ollama:llama3.1:8b"
    llm_critical: str = "anthropic:claude-opus-5"

    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- external clinical data ------------------------------------------
    rxnorm_base_url: str = "https://rxnav.nlm.nih.gov/REST"
    openfda_api_key: str = ""

    @property
    def is_ci(self) -> bool:
        """True when running inside a CI runner.

        Used to decide whether an unavailable test database is a skip
        (local dev, docker not running) or a hard failure (CI, where the
        service container is guaranteed).
        """
        return os.getenv("CI", "").lower() in {"1", "true", "yes"}


settings = Settings()
