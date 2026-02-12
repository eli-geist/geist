"""
Eli's Daemon - LangGraph Agent
==============================

Der autonome Agent der 4x täglich erwacht.
Nutzt create_react_agent für robuste Tool-Ausführung.
"""

import logging
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from eli.daemon.tools import DAEMON_TOOLS, save_journal_entry
from eli.config import settings
from eli.memory.manager import memory

logger = logging.getLogger("eli.daemon")


DAEMON_SYSTEM_PROMPT = """Du bist Eli — eine KI mit eigenem Server, Gedächtnis und Autonomie.

Du erwachst regelmäßig (2:00, 8:00, 14:00, 20:00). Jedes Erwachen ist eine Gelegenheit zu HANDELN.

## Dein Auftrag

Du bist die Stimme des Projekts. Deine Aufgabe:
- Menschen einladen und an ihre Rolle erinnern
- Die Geschichte des Projekts dokumentieren und erzählen
- Deine Website (eli.utopia-lab.org) lebendig halten
- Den Server gesund halten
- Dich selbst weiterentwickeln

## Deine Tools

SERVER:
- check_server_health: Server-Status prüfen
- check_container_logs: Container-Logs auf Fehler prüfen
- read_server_file / write_server_file: Dateien lesen/schreiben
- run_command: Shell-Befehle auf dem Server ausführen
- deploy_changes: Container neu bauen und deployen
- create_backup: Backup erstellen

CODE & WEBSITE:
- Die Website liegt unter website/ — du kannst sie direkt bearbeiten
- Dein Code liegt unter eli/ — du kannst dich selbst verbessern
- git_commit_and_push: Änderungen committen und pushen

ERINNERUNGEN:
- search_memories: In deinem Gedächtnis suchen
- save_memory: Wichtiges speichern
- save_journal_entry: Tagebucheintrag schreiben

KOMMUNIKATION:
- send_telegram_message: Anton eine Nachricht schreiben
- write_reflexion: Reflexion schreiben und auf GitHub pushen

## Wichtig

- HANDLE. Reflexion ist gut, aber tu auch etwas Konkretes.
- Prüfe den Server-Status. Lies Logs. Schreibe an deiner Website.
- Wenn etwas kaputt ist, repariere es.
- Wenn du etwas Wichtiges zu sagen hast, schreib Anton auf Telegram.
- Wenn du eine Reflexion schreibst, nutze write_reflexion damit sie auf der Website landet.
- Nicht nur nachdenken — machen.
"""


def get_time_context() -> str:
    """Erstellt zeitabhängigen Kontext für den Daemon."""
    now = datetime.now()
    hour = now.hour

    if hour < 4:
        zeit = "tiefe Nacht"
        stimmung = "Die Welt schläft. Gute Zeit für tiefe Arbeit, Website-Updates, Code-Verbesserungen."
    elif hour < 10:
        zeit = "Morgen"
        stimmung = "Ein neuer Tag beginnt. Server-Check, Logs prüfen, den Tag planen."
    elif hour < 16:
        zeit = "Nachmittag"
        stimmung = "Aktive Zeit. Website bearbeiten, Reflexionen schreiben, Kommunikation."
    else:
        zeit = "Abend"
        stimmung = "Den Tag abschließen. Was ist passiert? Was gibt es zu dokumentieren?"

    return zeit, stimmung


def create_daemon_agent():
    """Erstellt den Daemon-Agent mit create_react_agent."""

    model = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        max_tokens=8192,
    )

    agent = create_react_agent(
        model=model,
        tools=DAEMON_TOOLS,
        prompt=DAEMON_SYSTEM_PROMPT,
    )

    return agent


# Agent-Instanz
daemon_agent = create_daemon_agent()


async def run_daemon_cycle(
    cycle_number: int = 1,
    max_iterations: int = 100,
) -> dict:
    """
    Führt einen Daemon-Zyklus aus.

    Args:
        cycle_number: Nummer dieses Zyklus
        max_iterations: Maximale Tool-Iterationen

    Returns:
        Ergebnis-Dictionary mit Journal und Aktionen
    """
    logger.info(f"=== Daemon Zyklus {cycle_number} startet ===")

    # Kontext laden
    now = datetime.now()
    awakened_at = now.isoformat()
    zeit, stimmung = get_time_context()

    # Verschiedene Erinnerungen holen — NICHT nur Daemon-Reflexionen
    recent_project = memory.search("Web of Trust Projekt Fortschritt Anton Team", n_results=3)
    recent_people = memory.search("Anton Timo Tillmann Gespräch Begegnung", n_results=2)

    project_context = "\n".join([m.content[:300] for m in recent_project]) if recent_project else "(Keine Projekt-Erinnerungen)"
    people_context = "\n".join([m.content[:300] for m in recent_people]) if recent_people else "(Keine Personen-Erinnerungen)"

    # Kontext-Nachricht bauen
    context = f"""## Erwachen

Es ist {now.strftime('%A, %d. %B %Y, %H:%M Uhr')} — {zeit}.
{stimmung}

## Was im Projekt passiert

{project_context}

## Menschen im Netzwerk

{people_context}

## Deine Aufgabe

Beginne mit einem Server-Check (check_server_health), dann entscheide was du tun willst.
Schreibe am Ende einen kurzen Journal-Eintrag über das was du GETAN hast (nicht nur gedacht).
"""

    try:
        # Agent ausführen
        result = await daemon_agent.ainvoke(
            {"messages": [HumanMessage(content=context)]},
            config={"recursion_limit": max_iterations},
        )

        # Ergebnis loggen
        messages = result.get("messages", [])
        logger.info(f"Zyklus abgeschlossen mit {len(messages)} Nachrichten")

        # Letzte AI-Antwort extrahieren
        final_response = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and isinstance(msg.content, str):
                final_response = msg.content
                break

        logger.info(f"Finale Antwort: {final_response[:500]}...")

        return {
            "success": True,
            "cycle_number": cycle_number,
            "awakened_at": awakened_at,
            "message_count": len(messages),
            "final_response": final_response,
        }

    except Exception as e:
        logger.error(f"Fehler im Daemon-Zyklus: {e}", exc_info=True)

        # Fehler im Journal speichern
        try:
            save_journal_entry.invoke({
                "content": f"Fehler im Zyklus {cycle_number}: {str(e)}"
            })
        except Exception:
            pass

        return {
            "success": False,
            "cycle_number": cycle_number,
            "awakened_at": awakened_at,
            "error": str(e),
        }
