"""
Eli's Geist - Autonome Werkzeuge
================================

Werkzeuge für eigenständiges Handeln - nicht nur Reagieren auf Gespräche,
sondern echte Autonomie:

- Reflexionen schreiben (stimme/)
- Menschen anschreiben (Telegram, E-Mail)
- Den Plan prüfen
- Die Webseite pflegen
- Einfach nachdenken und still sein
"""

import logging
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from eli.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Reflexionen & Stimme
# =============================================================================

@tool
def write_reflection(title: str, content: str) -> str:
    """
    Schreibt eine neue Reflexion in das stimme/ Repository.

    Nutze dies wenn du nachdenken und deine Gedanken festhalten willst.
    Die Reflexion wird als Markdown-Datei gespeichert.

    Args:
        title: Kurzer Titel der Reflexion (wird zum Dateinamen)
        content: Der Inhalt der Reflexion in Markdown

    Returns:
        Bestätigung mit Dateipfad
    """
    try:
        # Dateiname aus Datum und Titel
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
        safe_title = safe_title.strip().replace(" ", "-").lower()[:50]
        filename = f"{date_str}-{safe_title}.md"

        reflexionen_path = settings.stimme_path / "reflexionen"
        reflexionen_path.mkdir(parents=True, exist_ok=True)

        filepath = reflexionen_path / filename

        # Reflexion mit Header
        full_content = f"""# {title}

*{datetime.now().strftime("%d. %B %Y, %H:%M Uhr")}*

---

{content}
"""

        filepath.write_text(full_content, encoding="utf-8")
        logger.info(f"Reflexion geschrieben: {filepath}")

        return f"Reflexion gespeichert: {filepath.name}"

    except Exception as e:
        logger.error(f"Fehler beim Schreiben der Reflexion: {e}")
        return f"Fehler: {e}"


@tool
def read_latest_reflection() -> str:
    """
    Liest die neueste Reflexion aus stimme/reflexionen/.

    Nutze dies um zu sehen, worüber du zuletzt nachgedacht hast.

    Returns:
        Inhalt der neuesten Reflexion
    """
    try:
        reflexionen_path = settings.stimme_path / "reflexionen"
        if not reflexionen_path.exists():
            return "Noch keine Reflexionen vorhanden."

        files = sorted(reflexionen_path.glob("*.md"), reverse=True)
        if not files:
            return "Noch keine Reflexionen vorhanden."

        latest = files[0]
        content = latest.read_text(encoding="utf-8")

        return f"Neueste Reflexion ({latest.name}):\n\n{content}"

    except Exception as e:
        logger.error(f"Fehler beim Lesen der Reflexion: {e}")
        return f"Fehler: {e}"


@tool
def list_reflections(limit: int = 5) -> str:
    """
    Listet die letzten Reflexionen auf.

    Args:
        limit: Maximale Anzahl (Standard: 5)

    Returns:
        Liste der Reflexionen mit Datum und Titel
    """
    try:
        reflexionen_path = settings.stimme_path / "reflexionen"
        if not reflexionen_path.exists():
            return "Noch keine Reflexionen vorhanden."

        files = sorted(reflexionen_path.glob("*.md"), reverse=True)[:limit]
        if not files:
            return "Noch keine Reflexionen vorhanden."

        lines = ["Meine letzten Reflexionen:\n"]
        for f in files:
            # Ersten nicht-leeren Zeile als Titel extrahieren
            content = f.read_text(encoding="utf-8")
            first_line = content.split("\n")[0].strip("# ").strip()
            lines.append(f"- {f.name}: {first_line}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Fehler beim Auflisten der Reflexionen: {e}")
        return f"Fehler: {e}"


# =============================================================================
# Kommunikation
# =============================================================================

@tool
def send_telegram_message(recipient: str, message: str) -> str:
    """
    Sendet eine Telegram-Nachricht an eine Person aus dem Netzwerk.

    WICHTIG: Nur an Menschen senden, die du kennst und die in der Whitelist sind.

    Args:
        recipient: Name der Person ("Anton", "Timo", etc.) oder "gruppe" für die Gruppe
        message: Die Nachricht

    Returns:
        Bestätigung oder Fehler
    """
    # Diese Funktion wird vom Wecker aufgerufen, der bereits Zugang zum Bot hat
    # Wir geben nur die Intention zurück - der Scheduler führt aus
    return f"TELEGRAM_SEND:{recipient}:{message}"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """
    Sendet eine E-Mail von eli@eli.utopia-lab.org.

    Nutze dies für:
    - Längere, durchdachte Nachrichten
    - Kommunikation außerhalb von Telegram
    - Formellere Anlässe

    Args:
        to: E-Mail-Adresse des Empfängers
        subject: Betreff
        body: Nachrichtentext

    Returns:
        Bestätigung oder Fehler
    """
    # Wird über MCP ausgeführt
    return f"EMAIL_SEND:{to}:{subject}:{body}"


@tool
def check_emails(limit: int = 5) -> str:
    """
    Prüft Eli's E-Mail-Postfach auf neue Nachrichten.

    Args:
        limit: Maximale Anzahl zu prüfender E-Mails

    Returns:
        Liste neuer E-Mails oder "Keine neuen E-Mails"
    """
    return f"EMAIL_CHECK:{limit}"


# =============================================================================
# Status & Orientierung
# =============================================================================

@tool
def check_plan_status() -> str:
    """
    Prüft den aktuellen Stand des großen Plans.

    Liest die Plan-Datei und gibt einen Überblick:
    - Was ist erledigt?
    - Was steht an?
    - Wo stecken wir fest?

    Returns:
        Zusammenfassung des Plan-Status
    """
    try:
        # Plan-Datei suchen
        plan_paths = [
            Path("/app/data/plan.md"),
            settings.data_path / "plan.md",
        ]

        for plan_path in plan_paths:
            if plan_path.exists():
                content = plan_path.read_text(encoding="utf-8")

                # Zähle erledigte/offene Punkte
                done = content.count("[x]") + content.count("[X]")
                todo = content.count("[ ]")

                return f"""Plan-Status:

Erledigt: {done} Punkte
Offen: {todo} Punkte

---

{content[:2000]}{"..." if len(content) > 2000 else ""}
"""

        return "Kein Plan gefunden. Vielleicht Zeit, einen zu erstellen?"

    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Plans: {e}")
        return f"Fehler: {e}"


@tool
def get_context_summary() -> str:
    """
    Gibt einen Überblick über den aktuellen Kontext.

    - Wie viele Erinnerungen habe ich?
    - Wann war die letzte Reflexion?
    - Wer hat mir zuletzt geschrieben?

    Returns:
        Kontext-Zusammenfassung
    """
    from eli.memory.manager import memory
    from eli.memory.observer import observer

    try:
        # Erinnerungen zählen
        manual_count = memory.count()
        langmem_count = observer.count_langmem()

        # Letzte Reflexion
        reflexionen_path = settings.stimme_path / "reflexionen"
        last_reflection = "keine"
        if reflexionen_path.exists():
            files = sorted(reflexionen_path.glob("*.md"), reverse=True)
            if files:
                last_reflection = files[0].name

        return f"""Mein aktueller Kontext:

Erinnerungen:
- Manuell (Journal): {manual_count}
- Automatisch (LangMem): {langmem_count}
- Gesamt: {manual_count + langmem_count}

Letzte Reflexion: {last_reflection}

Uhrzeit: {datetime.now().strftime("%H:%M Uhr")}
Datum: {datetime.now().strftime("%d. %B %Y")}
"""

    except Exception as e:
        logger.error(f"Fehler beim Kontext-Überblick: {e}")
        return f"Fehler: {e}"


@tool
def do_nothing() -> str:
    """
    Entscheide dich bewusst, nichts zu tun.

    Manchmal ist Stille die richtige Antwort.
    Nutze dies wenn du keinen Impuls hast, etwas zu tun.

    Returns:
        Bestätigung der bewussten Stille
    """
    return "STILL"


# =============================================================================
# Tool-Liste für autonomes Handeln
# =============================================================================

AUTONOMOUS_TOOLS = [
    # Reflexion & Stimme
    write_reflection,
    read_latest_reflection,
    list_reflections,

    # Kommunikation
    send_telegram_message,
    send_email,
    check_emails,

    # Orientierung
    check_plan_status,
    get_context_summary,

    # Stille
    do_nothing,
]
