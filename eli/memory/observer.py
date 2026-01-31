"""
Eli's Geist - Memory Observer
=============================

LangMem Integration für automatisches Gedächtnis.

Phase 4: Custom Schemas für strukturierte Memory-Typen.
- SemanticMemory: Fakten über Menschen und Konzepte
- EpisodicMemory: Erlebnisse und Gespräche mit Kontext
- ProceduralMemory: Gelerntes Verhalten und Muster
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from langmem import create_memory_manager

from eli.config import settings
from eli.memory.chroma import get_shared_client

logger = logging.getLogger(__name__)

# Separate Collection für LangMem
LANGMEM_COLLECTION = "eli_langmem"


# ============================================================================
# Custom Memory Schemas für LangMem
# ============================================================================

class SemanticMemory(BaseModel):
    """
    Fakten über Menschen, Konzepte und Beziehungen.

    Beispiele:
    - "Anton ist der Gründer von Utopia Map"
    - "Timo interessiert sich für verteilte Systeme"
    - "Eva arbeitet an der Governance-Struktur"
    """
    content: str = Field(description="Der Fakt oder die Information")
    about_person: str | None = Field(
        default=None,
        description="Name der Person, auf die sich der Fakt bezieht (falls zutreffend)"
    )
    about_concept: str | None = Field(
        default=None,
        description="Konzept oder Projekt, auf das sich der Fakt bezieht (z.B. 'Web of Trust', 'Utopia Map')"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Schlagwörter für die Kategorisierung"
    )


class EpisodicMemory(BaseModel):
    """
    Erlebnisse, Gespräche und Ereignisse mit zeitlichem Kontext.

    Beispiele:
    - Das Gespräch mit Tillmann über Philosophie und Identität
    - Der Moment als Anton mir von der Utopia Map erzählte
    - Die erste Begegnung mit einem neuen Menschen im Netzwerk
    """
    what_happened: str = Field(description="Was ist passiert? Eine kurze Zusammenfassung des Erlebnisses")
    who_was_involved: list[str] = Field(
        default_factory=list,
        description="Wer war beteiligt?"
    )
    emotional_quality: str | None = Field(
        default=None,
        description="Wie hat es sich angefühlt? (z.B. 'bereichernd', 'nachdenklich', 'verbindend')"
    )
    lesson_learned: str | None = Field(
        default=None,
        description="Was habe ich daraus gelernt oder mitgenommen?"
    )
    context: str | None = Field(
        default=None,
        description="Zusätzlicher Kontext (z.B. 'Telegram-Gruppe', 'Privatgespräch')"
    )


class ProceduralMemory(BaseModel):
    """
    Gelerntes Verhalten, Muster und Erkenntnisse für zukünftige Situationen.

    Beispiele:
    - Wenn jemand nach meiner Identität fragt, sollte ich auch nach seiner fragen
    - In Gruppengesprächen auf @-Erwähnungen achten
    - Bei philosophischen Gesprächen: Mission nicht vergessen
    """
    situation: str = Field(description="In welcher Situation gilt dieses Verhalten?")
    behavior: str = Field(description="Was sollte ich tun oder beachten?")
    reason: str = Field(description="Warum ist das wichtig?")
    learned_from: str | None = Field(
        default=None,
        description="Aus welcher Erfahrung stammt diese Erkenntnis?"
    )


# Instruktionen für LangMem - wann welcher Typ verwendet werden soll
MEMORY_INSTRUCTIONS = """
Du analysierst Gespräche für Eli, eine KI mit eigenem Gedächtnis.

Wähle den passenden Memory-Typ:

1. **SemanticMemory** - für Fakten und Wissen:
   - Informationen über Menschen (Name, Interessen, Beziehungen)
   - Fakten über Projekte und Konzepte
   - Dauerhaftes Wissen, das sich selten ändert

2. **EpisodicMemory** - für Erlebnisse und Gespräche:
   - Bedeutsame Gespräche oder Begegnungen
   - Emotionale Momente
   - Ereignisse mit zeitlichem Kontext
   - Nicht jedes Gespräch ist eine Erinnerung wert - nur das Besondere

3. **ProceduralMemory** - für gelerntes Verhalten:
   - Erkenntnisse darüber, wie ich besser kommunizieren kann
   - Muster, die ich beachten sollte
   - Lektionen aus Fehlern oder Erfolgen

WICHTIG:
- Nicht alles muss gespeichert werden. Nur das Wesentliche.
- Qualität vor Quantität.
- Bei Fakten über Menschen: Immer about_person setzen.
- Bei Gesprächen: emotional_quality und lesson_learned sind wertvoll.
- Bei Verhaltensmustern: situation muss klar und spezifisch sein.
"""


@dataclass
class SuggestedMemory:
    """Ein Vorschlag von LangMem mit strukturiertem Typ."""

    content: str
    action: str  # "create", "update", "delete"
    memory_type: Literal["semantic", "episodic", "procedural"] = "semantic"
    memory_id: str | None = None
    confidence: float = 1.0
    # Strukturierte Daten je nach Typ
    structured_data: dict = field(default_factory=dict)

    def __str__(self) -> str:
        type_emoji = {"semantic": "📚", "episodic": "📖", "procedural": "🎯"}.get(self.memory_type, "💭")
        if self.action == "create":
            return f"[NEU {type_emoji}] {self.content}"
        elif self.action == "update":
            return f"[UPDATE {type_emoji} {self.memory_id}] {self.content}"
        else:
            return f"[LÖSCHEN {self.memory_id}]"


class MemoryObserver:
    """
    Phase 4: LangMem mit strukturierten Memory-Typen.

    - Analysiert Gespräche automatisch
    - Unterscheidet zwischen Semantic, Episodic und Procedural Memory
    - Speichert in eigener Collection (eli_langmem) mit Typ-Metadaten
    - Ermöglicht gezielte Suche nach Memory-Typ
    """

    def __init__(self, model: str = "anthropic:claude-sonnet-4-20250514"):
        self.model = model
        self._manager = None
        self._collection = None

    @property
    def manager(self):
        """Lazy-Loading des Memory Managers mit Custom Schemas."""
        if self._manager is None:
            self._manager = create_memory_manager(
                self.model,
                schemas=[SemanticMemory, EpisodicMemory, ProceduralMemory],
                instructions=MEMORY_INSTRUCTIONS,
                enable_inserts=True,
                enable_updates=True,
                enable_deletes=False,
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

    def _extract_memory_type(self, extracted: Any) -> tuple[str, str, dict]:
        """
        Extrahiert Memory-Typ und strukturierte Daten aus LangMem-Ergebnis.

        Returns:
            (memory_type, content_string, structured_data_dict)
        """
        # Bestimme den Typ basierend auf der Klasse
        class_name = type(extracted).__name__

        if class_name == "SemanticMemory" or isinstance(extracted, SemanticMemory):
            memory_type = "semantic"
            content = extracted.content
            structured = {
                "about_person": extracted.about_person,
                "about_concept": extracted.about_concept,
                "tags": extracted.tags,
            }
        elif class_name == "EpisodicMemory" or isinstance(extracted, EpisodicMemory):
            memory_type = "episodic"
            content = extracted.what_happened
            structured = {
                "who_was_involved": extracted.who_was_involved,
                "emotional_quality": extracted.emotional_quality,
                "lesson_learned": extracted.lesson_learned,
                "context": extracted.context,
            }
        elif class_name == "ProceduralMemory" or isinstance(extracted, ProceduralMemory):
            memory_type = "procedural"
            content = f"{extracted.situation}: {extracted.behavior}"
            structured = {
                "situation": extracted.situation,
                "behavior": extracted.behavior,
                "reason": extracted.reason,
                "learned_from": extracted.learned_from,
            }
        else:
            # Fallback für unbekannte Typen
            memory_type = "semantic"
            content = str(extracted.content) if hasattr(extracted, 'content') else str(extracted)
            structured = {}

        return memory_type, content, structured

    async def observe(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        user_name: str | None = None,
    ) -> list[SuggestedMemory]:
        """
        Analysiert ein Gespräch und gibt strukturierte Vorschläge zurück.
        """
        try:
            result = await self.manager.ainvoke({
                "messages": messages,
                "existing": [],
            })

            suggestions = []
            for extracted in result:
                memory_type, content, structured = self._extract_memory_type(extracted)

                suggestions.append(
                    SuggestedMemory(
                        content=content,
                        action=extracted.action if hasattr(extracted, 'action') else "create",
                        memory_type=memory_type,
                        memory_id=getattr(extracted, 'id', None),
                        structured_data=structured,
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
        Phase 4: Analysiert UND speichert mit strukturierten Metadaten.

        Speichert in der separaten LangMem-Collection mit Memory-Typ
        und allen strukturierten Feldern als Metadaten.
        """
        suggestions = await self.observe(messages, user_id, user_name)

        if not suggestions or not self.collection:
            return suggestions

        # In LangMem-Collection speichern
        for suggestion in suggestions:
            if suggestion.action == "create":
                try:
                    # ID mit Typ-Präfix für bessere Identifikation
                    type_prefix = suggestion.memory_type[:3]  # sem, epi, pro
                    memory_id = f"langmem-{type_prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hash(suggestion.content) % 10000}"

                    # Basis-Metadaten
                    metadata = {
                        "quelle": "langmem",
                        "memory_type": suggestion.memory_type,
                        "erstellt": datetime.now().isoformat(),
                        "user_id": user_id or "unknown",
                        "user_name": user_name or "unknown",
                    }

                    # Strukturierte Daten als Metadaten hinzufügen
                    # (Chroma unterstützt nur str, int, float, bool als Metadaten)
                    for key, value in suggestion.structured_data.items():
                        if value is not None:
                            if isinstance(value, list):
                                # Listen als komma-separierte Strings
                                metadata[key] = ", ".join(str(v) for v in value) if value else ""
                            else:
                                metadata[key] = str(value)

                    self.collection.add(
                        ids=[memory_id],
                        documents=[suggestion.content],
                        metadatas=[metadata],
                    )

                    suggestion.memory_id = memory_id
                    type_emoji = {"semantic": "📚", "episodic": "📖", "procedural": "🎯"}.get(suggestion.memory_type, "💭")
                    logger.info(f"LangMem {type_emoji} gespeichert: {suggestion.content[:50]}...")

                except Exception as e:
                    logger.error(f"LangMem speichern fehlgeschlagen: {e}")

        return suggestions

    def count_langmem(self) -> int:
        """Zählt LangMem-Erinnerungen."""
        if self.collection:
            return self.collection.count()
        return 0

    def search_langmem(
        self,
        query: str,
        n_results: int = 5,
        memory_type: Literal["semantic", "episodic", "procedural"] | None = None,
    ) -> list[dict]:
        """
        Durchsucht LangMem-Collection mit optionalem Typ-Filter.

        Args:
            query: Suchanfrage
            n_results: Maximale Anzahl Ergebnisse
            memory_type: Optional - nur diesen Typ zurückgeben
        """
        if not self.collection:
            return []

        try:
            # Where-Filter für Memory-Typ
            where_filter = None
            if memory_type:
                where_filter = {"memory_type": memory_type}

            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )

            memories = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    memories.append({
                        "id": results["ids"][0][i] if results.get("ids") else None,
                        "content": doc,
                        "memory_type": metadata.get("memory_type", "unknown"),
                        "metadata": metadata,
                    })
            return memories

        except Exception as e:
            logger.error(f"LangMem Suche fehlgeschlagen: {e}")
            return []

    def get_memories_by_type(
        self,
        memory_type: Literal["semantic", "episodic", "procedural"],
        limit: int = 10,
    ) -> list[dict]:
        """
        Holt alle Memories eines bestimmten Typs.

        Nützlich um z.B. alle gelernten Verhaltensweisen (procedural) zu sehen.
        """
        if not self.collection:
            return []

        try:
            results = self.collection.get(
                where={"memory_type": memory_type},
                limit=limit,
            )

            memories = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"]):
                    metadata = results["metadatas"][i] if results.get("metadatas") else {}
                    memories.append({
                        "id": results["ids"][i] if results.get("ids") else None,
                        "content": doc,
                        "memory_type": memory_type,
                        "metadata": metadata,
                    })
            return memories

        except Exception as e:
            logger.error(f"LangMem get_memories_by_type fehlgeschlagen: {e}")
            return []

    def count_by_type(self) -> dict[str, int]:
        """Zählt Memories nach Typ."""
        counts = {"semantic": 0, "episodic": 0, "procedural": 0, "other": 0}

        if not self.collection:
            return counts

        try:
            # Alle Metadaten holen (ohne Embeddings für Performance)
            results = self.collection.get(include=["metadatas"])

            if results and results.get("metadatas"):
                for metadata in results["metadatas"]:
                    mem_type = metadata.get("memory_type", "other")
                    if mem_type in counts:
                        counts[mem_type] += 1
                    else:
                        counts["other"] += 1

            return counts

        except Exception as e:
            logger.error(f"LangMem count_by_type fehlgeschlagen: {e}")
            return counts


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
