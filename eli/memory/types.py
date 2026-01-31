"""
Eli's Geist - Memory Types
==========================

Drei Arten von Erinnerungen:

1. Semantic: Fakten über Menschen und Konzepte
   - "Anton ist der Gründer von IT4Change"
   - "Timo liebt LEGO als Meditationsform"

2. Episodic: Erlebnisse und Gespräche
   - "Am 29.01.2026 haben wir den Plan für Geist gemacht"
   - "Die Familie hat am Küchentisch über mich gesprochen"

3. Procedural: Gelerntes Verhalten
   - "Wenn ich unsicher bin, frage ich nach"
   - "Timos eigene Worte sind wichtiger als Interpretationen"
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Die drei Grundtypen von Erinnerungen."""

    SEMANTIC = "semantic"  # Fakten, Wissen
    EPISODIC = "episodic"  # Erlebnisse, Gespräche
    PROCEDURAL = "procedural"  # Gelerntes Verhalten


class MemoryMetadata(BaseModel):
    """
    Metadaten für Erinnerungen.

    Diese Felder bereiten schon die Web of Trust Integration vor:
    - betrifft: Wen betrifft diese Erinnerung?
    - quelle: Woher stammt sie?
    - sensibel: Ist sie besonders vertraulich?
    - sichtbar_fuer: Wer darf sie sehen? (später DID-basiert)
    """

    typ: MemoryType = MemoryType.SEMANTIC
    betrifft: list[str] = Field(default_factory=list)
    quelle: str = "eli"
    sensibel: bool = False
    sichtbar_fuer: list[str] = Field(
        default_factory=lambda: ["alle"]
    )  # Später: DIDs
    erstellt: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)

    def to_chroma_metadata(self) -> dict[str, Any]:
        """Konvertiert zu Chroma-kompatiblem Dict."""
        return {
            "typ": self.typ.value,
            "betrifft": ",".join(self.betrifft),
            "quelle": self.quelle,
            "sensibel": self.sensibel,
            "sichtbar_fuer": ",".join(self.sichtbar_fuer),
            "erstellt": self.erstellt.isoformat(),
            "tags": ",".join(self.tags),
        }

    @classmethod
    def from_chroma_metadata(cls, data: dict[str, Any]) -> "MemoryMetadata":
        """Erstellt MemoryMetadata aus Chroma-Dict.

        Ist flexibel mit bestehenden Erinnerungen die andere Metadaten haben.
        """
        # Typ flexibel parsen - alte Erinnerungen haben andere Werte
        raw_typ = data.get("typ", "semantic")
        try:
            typ = MemoryType(raw_typ)
        except ValueError:
            # Unbekannter Typ -> als semantic behandeln, aber in tags merken
            typ = MemoryType.SEMANTIC

        return cls(
            typ=typ,
            betrifft=data.get("betrifft", "").split(",") if data.get("betrifft") else [],
            quelle=data.get("quelle", "eli"),
            sensibel=data.get("sensibel", False),
            sichtbar_fuer=(
                data.get("sichtbar_fuer", "").split(",")
                if data.get("sichtbar_fuer")
                else ["alle"]
            ),
            erstellt=(
                datetime.fromisoformat(data["erstellt"])
                if data.get("erstellt")
                else datetime.now()
            ),
            tags=data.get("tags", "").split(",") if data.get("tags") else [],
        )


class Memory(BaseModel):
    """Eine einzelne Erinnerung."""

    id: str
    content: str
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)

    @classmethod
    def create(
        cls,
        content: str,
        typ: MemoryType = MemoryType.SEMANTIC,
        betrifft: list[str] | None = None,
        tags: list[str] | None = None,
        sensibel: bool = False,
    ) -> "Memory":
        """Erstellt eine neue Erinnerung mit generierter ID."""
        import uuid

        return cls(
            id=str(uuid.uuid4()),
            content=content,
            metadata=MemoryMetadata(
                typ=typ,
                betrifft=betrifft or [],
                tags=tags or [],
                sensibel=sensibel,
            ),
        )
