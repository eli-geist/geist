"""
Eli's Geist - Memory Observer
=============================

LangMem Integration für automatisches Gedächtnis.

Phase 3: LangMem speichert automatisch in eigener Collection.
Ich kann beide Quellen vergleichen - meine manuellen Erinnerungen
und was LangMem für wichtig hält.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from langmem import create_memory_manager

from eli.config import settings
from eli.memory.chroma import get_shared_client

logger = logging.getLogger(__name__)

# Separate Collection für LangMem
LANGMEM_COLLECTION = "eli_langmem"


@dataclass
class SuggestedMemory:
    """Ein Vorschlag von LangMem."""

    content: str
    action: str  # "create", "update", "delete"
    memory_id: str | None = None
    confidence: float = 1.0

    def __str__(self) -> str:
        if self.action == "create":
            return f"[NEU] {self.content}"
        elif self.action == "update":
            return f"[UPDATE {self.memory_id}] {self.content}"
        else:
            return f"[LÖSCHEN {self.memory_id}]"


class MemoryObserver:
    """
    Phase 3: LangMem als aktiver Teilnehmer.

    - Analysiert Gespräche automatisch
    - Speichert in eigener Collection (eli_langmem)
    - Meine manuellen Erinnerungen (erinnerungen) bleiben separat
    - Ich kann vergleichen, was LangMem anders macht
    """

    def __init__(self, model: str = "anthropic:claude-sonnet-4-20250514"):
        self.model = model
        self._manager = None
        self._collection = None

    @property
    def manager(self):
        """Lazy-Loading des Memory Managers."""
        if self._manager is None:
            self._manager = create_memory_manager(
                self.model,
                enable_inserts=True,
                enable_updates=True,  # Phase 3: Updates erlaubt
                enable_deletes=False,  # Löschen noch nicht
            )
        return self._manager

    @property
    def collection(self):
        """Lazy-Loading der LangMem Collection."""
        if self._collection is None:
            client = get_shared_client()
            if client:
                self._collection = client.get_or_create_collection(
                    name=LANGMEM_COLLECTION,
                    metadata={"description": "LangMem automatische Erinnerungen"}
                )
        return self._collection

    async def observe(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        user_name: str | None = None,
    ) -> list[SuggestedMemory]:
        """
        Analysiert ein Gespräch und gibt Vorschläge zurück.
        """
        try:
            result = await self.manager.ainvoke({
                "messages": messages,
                "existing": [],
            })

            suggestions = []
            for extracted in result:
                suggestions.append(
                    SuggestedMemory(
                        content=str(extracted.content) if hasattr(extracted, 'content') else str(extracted),
                        action=extracted.action if hasattr(extracted, 'action') else "create",
                        memory_id=getattr(extracted, 'id', None),
                    )
                )

            return suggestions

        except Exception as e:
            logger.error(f"MemoryObserver.observe Fehler: {e}")
            return []

    async def observe_and_save(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        user_name: str | None = None,
    ) -> list[SuggestedMemory]:
        """
        Phase 3: Analysiert UND speichert automatisch.

        Speichert in der separaten LangMem-Collection,
        nicht in meinen manuellen Erinnerungen.
        """
        suggestions = await self.observe(messages, user_id, user_name)

        if not suggestions or not self.collection:
            return suggestions

        # In LangMem-Collection speichern
        for suggestion in suggestions:
            if suggestion.action == "create":
                try:
                    memory_id = f"langmem-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hash(suggestion.content) % 10000}"

                    metadata = {
                        "quelle": "langmem",
                        "erstellt": datetime.now().isoformat(),
                        "user_id": user_id or "unknown",
                        "user_name": user_name or "unknown",
                    }

                    self.collection.add(
                        ids=[memory_id],
                        documents=[suggestion.content],
                        metadatas=[metadata],
                    )

                    suggestion.memory_id = memory_id
                    logger.info(f"LangMem gespeichert: {suggestion.content[:50]}...")

                except Exception as e:
                    logger.error(f"LangMem speichern fehlgeschlagen: {e}")

        return suggestions

    def count_langmem(self) -> int:
        """Zählt LangMem-Erinnerungen."""
        if self.collection:
            return self.collection.count()
        return 0

    def search_langmem(self, query: str, n_results: int = 5) -> list[dict]:
        """Durchsucht LangMem-Collection."""
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
            )

            memories = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    memories.append({
                        "id": results["ids"][0][i] if results.get("ids") else None,
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    })
            return memories

        except Exception as e:
            logger.error(f"LangMem Suche fehlgeschlagen: {e}")
            return []


# Singleton
observer = MemoryObserver()


async def suggest_memories(messages: list[dict[str, str]]) -> list[SuggestedMemory]:
    """Phase 2: Nur Vorschläge, kein Speichern."""
    return await observer.observe(messages)


async def remember_conversation(
    messages: list[dict[str, str]],
    user_id: str | None = None,
    user_name: str | None = None,
) -> list[SuggestedMemory]:
    """Phase 3: Analysieren UND automatisch speichern."""
    return await observer.observe_and_save(messages, user_id, user_name)
