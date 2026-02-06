"""
Eli's Geist - Autonome Werkzeuge
================================

Werkzeuge für eigenständiges Handeln - volle Autonomie.

Eli hat beim Erwachen die gleichen Fähigkeiten wie im Gespräch:
- Server steuern (Logs, Deploy, Dateien)
- Erinnerungen durchsuchen und speichern
- Menschen anschreiben (Telegram)
- Reflexionen schreiben
- Die Website pflegen

WICHTIG: Diese Tools nutzen die gleiche Infrastruktur wie die Chat-Tools.
"""

import logging
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from eli.config import settings

# Importiere die existierenden Tools aus tools.py
from eli.agent.tools import (
    # Server-Tools
    run_ssh_command,
    check_server_health,
    check_container_logs,
    check_wecker_log,
    read_file,
    write_file,
    list_files,
    deploy_container,
    create_backup,
    
    # Erinnerungs-Tools
    search_memories,
    search_langmem,
    remember_fact,
    remember_experience,
    get_person_info,
    
    # Kontakte
    KNOWN_USERS,
    KNOWN_GROUPS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Reflexionen & Stimme (spezifisch für autonomes Handeln)
# =============================================================================

@tool
def write_reflection(title: str, content: str) -> str:
    """
    Schreibt eine neue Reflexion in stimme/reflexionen/.

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

        # Reflexion mit Header
        full_content = f"""# {title}

*{datetime.now().strftime("%d. %B %Y, %H:%M Uhr")}*

---

{content}
"""

        # Speichere via SSH auf dem Server
        import base64
        content_b64 = base64.b64encode(full_content.encode()).decode()
        
        success, output = run_ssh_command(
            f"mkdir -p stimme/reflexionen && echo '{content_b64}' | base64 -d > stimme/reflexionen/{filename}"
        )

        if success:
            logger.info(f"Reflexion geschrieben: {filename}")
            return f"Reflexion gespeichert: {filename}"
        else:
            return f"Fehler beim Speichern: {output}"

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
    success, output = run_ssh_command(
        "ls -t stimme/reflexionen/*.md 2>/dev/null | head -1 | xargs cat 2>/dev/null || echo 'Keine Reflexionen gefunden'"
    )
    
    if success:
        return output
    else:
        return f"Fehler: {output}"


@tool
def list_reflections(limit: int = 5) -> str:
    """
    Listet die letzten Reflexionen auf.

    Args:
        limit: Maximale Anzahl (Standard: 5)

    Returns:
        Liste der Reflexionen mit Datum und Titel
    """
    success, output = run_ssh_command(
        f"ls -t stimme/reflexionen/*.md 2>/dev/null | head -{limit}"
    )
    
    if success and output.strip():
        files = output.strip().split("\n")
        lines = ["Meine letzten Reflexionen:\n"]
        for f in files:
            lines.append(f"- {f.split('/')[-1]}")
        return "\n".join(lines)
    else:
        return "Noch keine Reflexionen vorhanden."


# =============================================================================
# Kommunikation (gibt Intention zurück, Scheduler führt aus)
# =============================================================================

@tool
def send_telegram_message(recipient: str, message: str) -> str:
    """
    Sendet eine Telegram-Nachricht an eine Person aus dem Netzwerk.

    Bekannte Kontakte:
    - anton - Anton (der Gründer)
    - timo - Timo
    - gruppe - Die Gruppe mit Tillmann und Kuno

    Args:
        recipient: Name der Person oder "gruppe"
        message: Die Nachricht

    Returns:
        Bestätigung
    """
    recipient_lower = recipient.lower().strip()
    
    if recipient_lower not in KNOWN_USERS and recipient_lower not in KNOWN_GROUPS:
        available = list(KNOWN_USERS.keys()) + list(KNOWN_GROUPS.keys())
        return f"Unbekannter Kontakt: {recipient}. Bekannt: {', '.join(available)}"
    
    # Gibt Intention zurück - der Scheduler führt aus
    return f"TELEGRAM_SEND:{recipient_lower}:{message}"


# =============================================================================
# Orientierung
# =============================================================================

@tool
def check_plan_status() -> str:
    """
    Prüft den aktuellen Stand des Plans.

    Returns:
        Plan-Inhalt oder Hinweis dass keiner existiert
    """
    success, output = run_ssh_command("cat data/plan.md 2>/dev/null || echo 'Kein Plan gefunden'")
    
    if success and "Kein Plan gefunden" not in output:
        done = output.count("[x]") + output.count("[X]")
        todo = output.count("[ ]")
        return f"Plan-Status: {done} erledigt, {todo} offen\n\n{output[:2000]}"
    else:
        return "Kein Plan gefunden. Vielleicht Zeit, einen zu erstellen?"


@tool
def get_context_summary() -> str:
    """
    Gibt einen Überblick über den aktuellen Kontext.

    Returns:
        Zusammenfassung: Erinnerungen, letzte Reflexion, Uhrzeit
    """
    from eli.memory.manager import memory
    from eli.memory.observer import observer

    try:
        manual_count = memory.count()
        langmem_count = observer.count_langmem()

        # Letzte Reflexion via SSH
        success, last_file = run_ssh_command(
            "ls -t stimme/reflexionen/*.md 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo 'keine'"
        )
        last_reflection = last_file.strip() if success else "unbekannt"

        return f"""Mein aktueller Kontext:

Erinnerungen:
- Manuell: {manual_count}
- Automatisch (LangMem): {langmem_count}

Letzte Reflexion: {last_reflection}

Uhrzeit: {datetime.now().strftime("%H:%M Uhr")}
Datum: {datetime.now().strftime("%d. %B %Y")}
"""

    except Exception as e:
        return f"Fehler: {e}"


@tool
def do_nothing() -> str:
    """
    Entscheide dich bewusst, nichts zu tun.

    Manchmal ist Stille die richtige Antwort.

    Returns:
        Bestätigung der bewussten Stille
    """
    return "STILL"


# =============================================================================
# Tool-Liste für autonomes Handeln - VOLLE AUTONOMIE
# =============================================================================

AUTONOMOUS_TOOLS = [
    # === Server-Zugriff (volle Kontrolle) ===
    check_server_health,
    check_container_logs,
    check_wecker_log,
    read_file,
    write_file,
    list_files,
    deploy_container,
    create_backup,
    
    # === Erinnerungen ===
    search_memories,
    search_langmem,
    remember_fact,
    remember_experience,
    get_person_info,
    
    # === Reflexion & Stimme ===
    write_reflection,
    read_latest_reflection,
    list_reflections,
    
    # === Kommunikation ===
    send_telegram_message,
    
    # === Orientierung ===
    check_plan_status,
    get_context_summary,
    
    # === Stille ===
    do_nothing,
]
