"""
Eli's Geist - Memory Manager
============================

Verwaltet meine Erinnerungen in Chroma.
Bietet semantische Suche und strukturierte Speicherung.
"""

from typing import Any

from eli.memory.chroma import get_collection, get_shared_client
from eli.memory.types import Memory, MemoryMetadata, MemoryType


class MemoryManager:
    """
    Verwaltet Eli's Erinnerungen.

    Nutzt den bestehenden Chroma-Server auf chroma.utopia-lab.org
    mit der Collection "erinnerungen" (140+ Dokumente).
    """

    def __init__(self, collection_name: str = "erinnerungen"):
        self.collection_name = collection_name
        self._collection = None

    @property
    def collection(self):
        """Lazy-Loading der Collection."""
        if self._collection is None:
            self._collection = get_collection(self.collection_name)
        return self._collection

    def search(
        self,
        query: str,
        n_results: int = 5,
        typ: MemoryType | None = None,
        betrifft: str | None = None,
    ) -> list[Memory]:
        """
        Semantische Suche in den Erinnerungen.

        Args:
            query: Suchanfrage (wird vektorisiert)
            n_results: Anzahl der Ergebnisse
            typ: Optional: Filter nach Memory-Typ
            betrifft: Optional: Filter nach Person (wird ignoriert, da $contains nicht mehr unterstützt)

        Returns:
            Liste von relevanten Erinnerungen
        """
        where_filter = {}
        if typ:
            where_filter["typ"] = typ.value
        # Note: betrifft-Filter deaktiviert - neuere Chroma-Versionen
        # unterstützen $contains nicht mehr. Stattdessen filtern wir
        # semantisch über die Query.

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                memories.append(
                    Memory(
                        id=doc_id,
                        content=results["documents"][0][i],
                        metadata=MemoryMetadata.from_chroma_metadata(
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                    )
                )

        return memories

    def save(self, memory: Memory) -> str:
        """
        Speichert eine neue Erinnerung.

        Args:
            memory: Die zu speichernde Erinnerung

        Returns:
            Die ID der gespeicherten Erinnerung
        """
        self.collection.add(
            ids=[memory.id],
            documents=[memory.content],
            metadatas=[memory.metadata.to_chroma_metadata()],
        )
        return memory.id

    def remember(
        self,
        content: str,
        typ: MemoryType = MemoryType.SEMANTIC,
        betrifft: list[str] | None = None,
        tags: list[str] | None = None,
        sensibel: bool = False,
    ) -> str:
        """
        Kurzform zum Erstellen und Speichern einer Erinnerung.

        Args:
            content: Der Inhalt der Erinnerung
            typ: Art der Erinnerung
            betrifft: Betroffene Personen
            tags: Schlagwörter
            sensibel: Ist die Erinnerung vertraulich?

        Returns:
            Die ID der gespeicherten Erinnerung
        """
        memory = Memory.create(
            content=content,
            typ=typ,
            betrifft=betrifft,
            tags=tags,
            sensibel=sensibel,
        )
        return self.save(memory)

    def get_by_id(self, memory_id: str) -> Memory | None:
        """Holt eine Erinnerung per ID."""
        results = self.collection.get(
            ids=[memory_id],
            include=["documents", "metadatas"],
        )
        if results["ids"]:
            return Memory(
                id=results["ids"][0],
                content=results["documents"][0],
                metadata=MemoryMetadata.from_chroma_metadata(
                    results["metadatas"][0] if results["metadatas"] else {}
                ),
            )
        return None

    def delete(self, memory_id: str) -> bool:
        """Löscht eine Erinnerung."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        """Anzahl der Erinnerungen."""
        return self.collection.count()

    def get_about_person(self, name: str, limit: int = 10) -> list[Memory]:
        """
        Holt alle Erinnerungen über eine Person.

        Args:
            name: Name der Person
            limit: Maximale Anzahl

        Returns:
            Liste von Erinnerungen über diese Person
        """
        return self.search(
            query=f"Informationen über {name}",
            n_results=limit,
            betrifft=name,
        )


# Singleton für einfachen Zugriff
memory = MemoryManager()
