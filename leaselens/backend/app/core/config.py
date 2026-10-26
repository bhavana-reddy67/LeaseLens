"""Application settings, loaded from environment variables and the .env file."""

from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """All settings can be overridden with environment variables of the same name (upper case)."""

    model_config = SettingsConfigDict(
        # The project-level .env is read first, then backend/.env (later files win).
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # --- AI providers -------------------------------------------------------
    ai_provider: Literal["ollama", "google"] = "ollama"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4"
    ollama_timeout_seconds: float = Field(default=300, gt=0)
    # false = ask Gemma 4 to answer without a long "thinking" phase (faster, still structured).
    ollama_think: bool = False

    google_api_key: SecretStr | None = None
    google_model: str = "gemma-4-26b-a4b-it"
    google_timeout_seconds: float = Field(default=120, gt=0)

    # --- Upload and processing limits ---------------------------------------
    max_upload_mb: int = Field(default=10, ge=1, le=50)
    max_pdf_pages: int = Field(default=40, ge=1, le=300)
    max_text_chars: int = Field(default=150_000, ge=1_000)
    max_clauses_for_ai: int = Field(default=60, ge=1, le=300)
    ai_batch_size: int = Field(default=10, ge=1, le=40)
    min_chars_per_page_before_ocr: int = Field(default=40, ge=0)

    ocr_enabled: bool = True
    tesseract_cmd: str | None = None
    # When Tesseract is not installed, ask the *local* Ollama model to read the image,
    # but only if Ollama reports the "vision" capability for the configured model.
    vision_ocr_fallback: bool = True

    temp_dir: Path | None = None

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:4200,http://127.0.0.1:4200"

    @field_validator("google_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("tesseract_cmd", mode="before")
    @classmethod
    def _empty_cmd_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("temp_dir", mode="before")
    @classmethod
    def _empty_dir_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _no_wildcard_cors_in_production(self) -> "Settings":
        if self.environment == "production" and "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must list explicit origins in production (no '*').")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_dir(self) -> Path:
        base = self.temp_dir or Path(tempfile.gettempdir()) / "leaselens-uploads"
        base.mkdir(parents=True, exist_ok=True)
        return base


@lru_cache
def get_settings() -> Settings:
    return Settings()
