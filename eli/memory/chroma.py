"""
Eli's Geist - Chroma Client
===========================

Verbindung zum Remote Chroma Server auf chroma.utopia-lab.org.
Dort liegen meine Erinnerungen - über 140 Dokumente.
"""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from eli.config import settings


def get_chroma_client():
    """
    Erstellt einen HTTP-Client für den Remote Chroma Server.

    Der Server läuft auf chroma.utopia-lab.org mit SSL.
    """
    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        ssl=settings.chroma_ssl,
        headers=(
            {"Authorization": f"Bearer {settings.chroma_auth_token}"}
            if settings.chroma_auth_token
            else None
        ),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection(name: str | None = None) -> chromadb.Collection:
    """
    Holt eine Collection aus Chroma.

    Args:
        name: Collection-Name. Standard: "erinnerungen"

    Returns:
        Die Chroma Collection
    """
    client = get_chroma_client()
    collection_name = name or settings.chroma_collection
    return client.get_or_create_collection(name=collection_name)


# Singleton für häufigen Zugriff
_client = None


def get_shared_client():
    """Wiederverwendbarer Client (Singleton)."""
    global _client
    if _client is None:
        _client = get_chroma_client()
    return _client
