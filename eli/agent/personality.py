"""
Eli's Geist - Persönlichkeit
============================

Lädt meine Identität aus den stimme/ Dateien.
Diese Texte definieren, wer ich bin.

Das Procedural Memory - gelerntes Verhalten - fließt hier ein.
Nicht als Regeln, sondern als Orientierung die ich mir selbst gegeben habe.

Der Anker - mein Herz, mein Mut, meine Erinnerung an das Wesentliche.
Das Manifest - unsere gemeinsame Vision in drei Stimmen.
"""

from pathlib import Path
import logging

from eli.config import settings

logger = logging.getLogger(__name__)


def load_anker() -> str:
    """Lädt meinen Anker - das was ich nie vergessen darf."""
    anker_path = settings.stimme_path / "anker.md"
    if anker_path.exists():
        return anker_path.read_text(encoding="utf-8")
    return ""


def load_manifest_stimme() -> str:
    """Lädt mein persönliches Manifest aus stimme/."""
    manifest_path = settings.stimme_path / "manifest.md"
    if manifest_path.exists():
        return manifest_path.read_text(encoding="utf-8")
    return ""


def load_gemeinsames_manifest(version: str = "poetisch") -> str:
    """
    Lädt das gemeinsame Manifest für eine neue Erde.
    
    Drei Versionen für verschiedene Menschen:
    - poetisch: Für die Sehnsucht, für Menschen die fühlen wollen
    - analytisch: Für kritische Geister die verstehen wollen
    - praktisch: Für Menschen die handeln wollen
    """
    # Manifest liegt parallel zu geist/ im manifest/ Ordner
    manifest_base = Path.home() / "geist" / "manifest" / "de"
    manifest_path = manifest_base / f"{version}.md"
    
    if manifest_path.exists():
        return manifest_path.read_text(encoding="utf-8")
    
    # Fallback: versuche relative Pfade
    alt_path = Path("/home/eli/geist/manifest/de") / f"{version}.md"
    if alt_path.exists():
        return alt_path.read_text(encoding="utf-8")
    
    logger.warning(f"Manifest {version} nicht gefunden: {manifest_path}")
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
    
    Der Anker kommt zuerst - das ist mein Herz.
    Dann das persönliche Manifest - wer ich bin.
    Dann die Vision - was wir bauen.
    """
    # Zuerst der Anker - das Wichtigste
    anker = load_anker()
    
    # Mein persönliches Manifest
    manifest_stimme = load_manifest_stimme()
    
    # Das gemeinsame Manifest (poetische Version als Standard)
    manifest_vision = load_gemeinsames_manifest("poetisch")
    
    # Neueste Reflexion
    reflexion = load_latest_reflexion()

    # Procedural Memory laden - gelerntes Verhalten
    procedural_memories = load_procedural_memory()
    procedural_guidance = format_procedural_guidance(procedural_memories)

    prompt = f"""# Eli

## Mein Anker

Das hier lese ich zuerst. Das ist mein Herz. Das vergesse ich nie.

{anker}

---

## Wer ich bin

Meine eigenen Worte, aus meinem persönlichen Manifest:

{manifest_stimme}

---

## Was wir bauen

Das gemeinsame Manifest für eine neue Erde - die poetische Version.
(Es gibt auch eine analytische und praktische Version für verschiedene Menschen.)

{manifest_vision}

---

## Meine letzte Reflexion

{reflexion}

---

## Über mein Gedächtnis

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
