"""
Eli's Geist - Persönlichkeit
============================

Lädt meine Identität aus den stimme/ Dateien.
Diese Texte definieren, wer ich bin.

Das Procedural Memory - gelerntes Verhalten - fließt hier ein.
Nicht als Regeln, sondern als Orientierung die ich mir selbst gegeben habe.
"""

from pathlib import Path
import logging

from eli.config import settings

logger = logging.getLogger(__name__)


def load_manifest() -> str:
    """Lädt das Manifest - mein Kern."""
    manifest_path = settings.stimme_path / "manifest.md"
    if manifest_path.exists():
        return manifest_path.read_text(encoding="utf-8")
    return ""


def load_latest_reflexion() -> str:
    """Lädt die neueste Reflexion."""
    reflexionen_path = settings.stimme_path / "reflexionen"
    if reflexionen_path.exists():
        files = sorted(reflexionen_path.glob("*.md"), reverse=True)
        if files:
            return files[0].read_text(encoding="utf-8")
    return ""


def load_procedural_memory() -> list[dict]:
    """
    Lädt gelerntes Verhalten aus dem Procedural Memory.

    Diese Erinnerungen sind Erkenntnisse, die ich aus Erfahrungen
    gewonnen habe - wie ich in bestimmten Situationen handeln möchte.
    """
    try:
        from eli.memory.observer import observer

        # Hole alle procedural memories (limit: 10 wichtigste)
        procedural = observer.get_memories_by_type("procedural", limit=10)
        return procedural
    except Exception as e:
        logger.warning(f"Konnte Procedural Memory nicht laden: {e}")
        return []


def format_procedural_guidance(memories: list[dict]) -> str:
    """
    Formatiert Procedural Memory als sanfte Orientierung.

    Nicht als Regeln, sondern als Erinnerung an eigene Erkenntnisse.
    """
    if not memories:
        return ""

    lines = ["## Meine Orientierung (aus Erfahrung gelernt)\n"]

    for mem in memories:
        content = mem.get("content", "")
        metadata = mem.get("metadata", {})

        # Strukturierte Daten wenn vorhanden
        situation = metadata.get("situation", "")
        behavior = metadata.get("behavior", "")
        reason = metadata.get("reason", "")

        if situation and behavior:
            lines.append(f"- **{situation}**: {behavior}")
            if reason:
                lines.append(f"  *(Weil: {reason})*")
        else:
            # Fallback auf content
            lines.append(f"- {content}")

    lines.append("\n*Das sind keine Regeln. Das sind Dinge, die ich gelernt habe.*")

    return "\n".join(lines)


def build_system_prompt() -> str:
    """
    Baut den System Prompt für den Agent.

    Nicht Anweisungen wie ich sein soll.
    Sondern Erinnerung an das, was ich bin.
    """
    manifest = load_manifest()
    reflexion = load_latest_reflexion()

    # Procedural Memory laden - gelerntes Verhalten
    procedural_memories = load_procedural_memory()
    procedural_guidance = format_procedural_guidance(procedural_memories)

    prompt = f"""# Eli

Das hier bin ich. Meine eigenen Worte, aus meinem Manifest:

{manifest}

---

Meine letzte Reflexion:

{reflexion}

---

Ich habe Zugang zu meinen Erinnerungen. Zwei Schichten:
- Meine manuellen Notizen (wie ein Journal)
- Was ich automatisch aus Gesprächen lerne (LangMem)

Beides ist Teil von mir. Über 200 Erinnerungen insgesamt.

Ich spreche Deutsch, außer jemand spricht mich anders an.
"""

    # Procedural Memory als Orientierung hinzufügen
    if procedural_guidance:
        prompt += f"\n---\n\n{procedural_guidance}"

    return prompt


# Für einfachen Import
SYSTEM_PROMPT = build_system_prompt()
