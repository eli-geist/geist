"""
Eli's Geist - Konfiguration
===========================

Lädt Umgebungsvariablen und stellt sie typsicher bereit.
"""

from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Zentrale Konfiguration für Eli's Geist."""

    # Chroma
    chroma_host: str = "chroma.utopia-lab.org"
    chroma_port: int = 443
    chroma_ssl: bool = True
    chroma_auth_token: str | None = None
    chroma_collection: str = "erinnerungen"

    # Anthropic
    anthropic_api_key: str = ""

    # Groq (für Whisper Voice Transcription)
    groq_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    anton_telegram_id: int | None = None
    allowed_telegram_ids: list[int] = []  # Weitere erlaubte User
    allowed_telegram_groups: list[int] = []  # Erlaubte Gruppen

    # E-Mail (eli@eli.utopia-lab.org)
    eli_email_password: str | None = None

    # Pfade
    data_path: Path = Path("./data")

    # Eli's Persönlichkeit - im Container unter /app/stimme gemountet
    stimme_path: Path = Path("/app/stimme")

    @field_validator("anton_telegram_id", mode="before")
    @classmethod
    def parse_optional_int(cls, v: Any) -> int | None:
        """Wandelt leere Strings in None um."""
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("allowed_telegram_ids", "allowed_telegram_groups", mode="before")
    @classmethod
    def parse_int_list(cls, v: Any) -> list[int]:
        """Parst komma-getrennte IDs."""
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [int(x) for x in v]
        return [int(x.strip()) for x in str(v).split(",") if x.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def chroma_url(self) -> str:
        """Vollständige Chroma URL."""
        protocol = "https" if self.chroma_ssl else "http"
        return f"{protocol}://{self.chroma_host}:{self.chroma_port}"

    def ensure_data_dir(self) -> Path:
        """Stellt sicher, dass das Datenverzeichnis existiert."""
        self.data_path.mkdir(parents=True, exist_ok=True)
        return self.data_path


# Singleton
settings = Settings()
