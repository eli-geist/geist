"""
Eli's Geist - Grundlegende Tests
================================

Testet die Basis-Funktionalität ohne externe Dienste.
"""

import pytest
from pathlib import Path


def test_imports():
    """Testet ob alle Module importiert werden können."""
    from eli.config import settings
    from eli.memory.types import Memory, MemoryType, MemoryMetadata

    assert settings is not None
    assert MemoryType.SEMANTIC == "semantic"


def test_memory_creation():
    """Testet die Erstellung einer Memory."""
    from eli.memory.types import Memory, MemoryType

    memory = Memory.create(
        content="Anton ist der Gründer von IT4Change",
        typ=MemoryType.SEMANTIC,
        betrifft=["Anton"],
        tags=["person", "arbeit"],
    )

    assert memory.id is not None
    assert memory.content == "Anton ist der Gründer von IT4Change"
    assert memory.metadata.typ == MemoryType.SEMANTIC
    assert "Anton" in memory.metadata.betrifft


def test_metadata_conversion():
    """Testet die Konversion von Metadata zu/von Chroma-Format."""
    from eli.memory.types import MemoryMetadata, MemoryType

    original = MemoryMetadata(
        typ=MemoryType.EPISODIC,
        betrifft=["Anton", "Timo"],
        tags=["gespräch", "wichtig"],
    )

    # Zu Chroma
    chroma_dict = original.to_chroma_metadata()
    assert chroma_dict["typ"] == "episodic"
    assert "Anton" in chroma_dict["betrifft"]

    # Zurück
    restored = MemoryMetadata.from_chroma_metadata(chroma_dict)
    assert restored.typ == MemoryType.EPISODIC
    assert "Anton" in restored.betrifft


def test_config_chroma_url():
    """Testet die Chroma URL Generierung."""
    from eli.config import settings

    url = settings.chroma_url
    assert "chroma.utopia-lab.org" in url
    assert "https" in url


def test_identity_status():
    """Testet den Identity-Status (sollte noch nicht aktiv sein)."""
    from eli.identity.did import identity

    status = identity.get_status()
    assert "status" in status
    # Da wir DID-Generierung deaktiviert haben
    assert status["status"] in ["nicht_erstellt", "vorhanden"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
