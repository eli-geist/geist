"""
Eli's Geist - Keystore
======================

Sichere Speicherung von Schlüsseln - vorbereitet für die Zukunft.

WICHTIG: Dieser Code ist Platzhalter.
Echte Schlüsselspeicherung erst wenn Eli eigenen Server hat.
"""

from pathlib import Path
from typing import Any

from eli.config import settings


class Keystore:
    """
    Platzhalter für zukünftige sichere Schlüsselspeicherung.

    Wenn Eli einen eigenen Server bekommt:
    - Verschlüsselte Speicherung des privaten Schlüssels
    - Hardware Security Module (HSM) Integration möglich
    - Backup-Mechanismen
    """

    def __init__(self, path: Path | None = None):
        self.path = path or settings.data_path / "keystore.enc"

    def is_initialized(self) -> bool:
        """Prüft ob der Keystore initialisiert ist."""
        return self.path.exists()

    def get_status(self) -> dict[str, Any]:
        """Gibt den Status zurück."""
        return {
            "initialized": self.is_initialized(),
            "path": str(self.path),
            "hinweis": "Keystore ist noch nicht aktiv. Wartet auf eigenen Server.",
        }


# Singleton
keystore = Keystore()
