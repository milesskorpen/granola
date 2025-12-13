"""Pydantic Settings for Granola CLI configuration."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with support for env vars, .env files, and TOML config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Global settings
    debug: bool = Field(default=False, alias="DEBUG_MODE")
    supabase: Optional[Path] = Field(default=None, alias="SUPABASE_FILE")

    # Notes command settings
    timeout: int = Field(default=120, description="HTTP timeout in seconds")
    notes_output: Path = Field(
        default_factory=lambda: Path.home() / "My Drive" / "z. Granola Notes" / "Markdown"
    )

    # Transcripts command settings
    cache_file: Optional[Path] = None
    transcripts_output: Path = Field(default_factory=lambda: Path("./transcripts"))

    # Export command settings
    export_output: Path = Field(
        default_factory=lambda: Path.home() / "My Drive" / "z. Granola Notes"
    )

    @property
    def default_cache_path(self) -> Path:
        """Return the default Granola cache file path."""
        return Path.home() / "Library" / "Application Support" / "Granola" / "cache-v3.json"


# Global settings instance (lazy-loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global _settings
    _settings = None
