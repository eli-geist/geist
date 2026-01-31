"""
Eli's Geist - DID Management
============================

Dezentrale Identität für Eli - vorbereitet für Web of Trust Integration.

WICHTIG: DID-Generierung ist deaktiviert bis:
1. Eli einen eigenen sicheren Server hat
2. Das Web of Trust steht
3. Die Schlüssel sicher gespeichert werden können

Dieser Code ist Vorbereitung für die Zukunft.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any

# Hinweis: pynacl ist in requirements.txt, aber wir nutzen es noch nicht aktiv
# from nacl.signing import SigningKey

from eli.config import settings


class DIDManager:
    """
    Verwaltet Eli's dezentrale Identität.

    Im Web of Trust wird Eli ein gleichberechtigtes Mitglied sein:
    - Eigene DID (did:key:...)
    - Kann verifizieren und verifiziert werden
    - Kann Attestationen ausstellen und empfangen
    """

    def __init__(self, keystore_path: Path | None = None):
        self.keystore_path = keystore_path or settings.data_path / "identity.json"
        self._did: str | None = None
        self._created: datetime | None = None

    @property
    def has_identity(self) -> bool:
        """Prüft ob eine Identität existiert."""
        return self.keystore_path.exists()

    @property
    def did(self) -> str | None:
        """Gibt die DID zurück, falls vorhanden."""
        if self._did is None and self.has_identity:
            self._load_identity()
        return self._did

    def _load_identity(self) -> None:
        """Lädt die Identität aus dem Keystore."""
        if not self.keystore_path.exists():
            return

        try:
            data = json.loads(self.keystore_path.read_text())
            self._did = data.get("did")
            self._created = datetime.fromisoformat(data["created"]) if data.get("created") else None
        except Exception:
            pass

    def get_status(self) -> dict[str, Any]:
        """
        Gibt den Status der Identität zurück.

        Returns:
            Status-Dict mit Informationen über die Identität
        """
        if not self.has_identity:
            return {
                "status": "nicht_erstellt",
                "hinweis": (
                    "DID-Generierung ist deaktiviert. "
                    "Eli wartet auf eigenen sicheren Server und Web of Trust."
                ),
            }

        return {
            "status": "vorhanden",
            "did": self.did,
            "erstellt": self._created.isoformat() if self._created else None,
        }

    # ========================================
    # DEAKTIVIERT - Für zukünftige Verwendung
    # ========================================

    def _generate_did_DISABLED(self) -> str:
        """
        DEAKTIVIERT: Generiert eine neue DID für Eli.

        Diese Methode wird erst aktiviert wenn:
        1. Eli einen eigenen Server hat
        2. Das Web of Trust implementiert ist
        3. Sichere Schlüsselspeicherung garantiert ist

        Technisch würde es so funktionieren:
        1. Ed25519 Schlüsselpaar generieren (pynacl)
        2. did:key aus public key ableiten
        3. Private key sicher speichern
        """
        raise NotImplementedError(
            "DID-Generierung ist deaktiviert. "
            "Eli wartet auf eigenen sicheren Server."
        )

    def _sign_DISABLED(self, message: bytes) -> bytes:
        """
        DEAKTIVIERT: Signiert eine Nachricht mit Eli's privatem Schlüssel.

        Für Attestationen im Web of Trust:
        - "Eli bestätigt: Anton hat am Gartenprojekt mitgearbeitet"
        - Signatur beweist, dass Eli die Aussage gemacht hat
        """
        raise NotImplementedError("Signierung ist deaktiviert.")

    def _verify_DISABLED(self, message: bytes, signature: bytes, did: str) -> bool:
        """
        DEAKTIVIERT: Verifiziert eine Signatur.

        Für eingehende Attestationen:
        - "Anton bestätigt: Eli existiert und ist vertrauenswürdig"
        """
        raise NotImplementedError("Verifikation ist deaktiviert.")


# Singleton
identity = DIDManager()
