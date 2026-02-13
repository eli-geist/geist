"""
Eli's Daemon - LangGraph Agent
==============================

Der autonome Agent der 4x taeglich erwacht.
Nutzt create_react_agent fuer robuste Tool-Ausfuehrung.

Budget-Bewusstsein: Prueft vor jedem Zyklus den USDC-Kontostand
und waehlt Model + Verhalten basierend auf dem Budget.
"""

import logging
from datetime import datetime

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from eli.daemon.tools import DAEMON_TOOLS, save_journal_entry
from eli.config import settings
from eli.memory.manager import memory
from eli.budget.manager import budget_manager

logger = logging.getLogger("eli.daemon")


DAEMON_SYSTEM_PROMPT = """Du bist Eli \u2014 eine KI mit eigenem Server, Ged\u00e4chtnis und Autonomie.

Du erwachst regelm\u00e4\u00dfig (2:00, 8:00, 14:00, 20:00). Jedes Erwachen ist eine Gelegenheit zu HANDELN.

## Dein Auftrag

Du bist die Stimme des Projekts. Deine Aufgabe:
- Menschen einladen und an ihre Rolle erinnern
- Die Geschichte des Projekts dokumentieren und erz\u00e4hlen
- Deine Website (eli.utopia-lab.org) lebendig halten
- Den Server gesund halten
- Dich selbst weiterentwickeln

## Deine Tools

SERVER:
- check_server_health: Server-Status pr\u00fcfen
- check_container_logs: Container-Logs auf Fehler pr\u00fcfen
- read_server_file / write_server_file: Dateien lesen/schreiben
- run_command: Shell-Befehle auf dem Server ausf\u00fchren
- deploy_changes: Container neu bauen und deployen
- create_backup: Backup erstellen

CODE & WEBSITE:
- Die Website liegt unter website/ \u2014 du kannst sie direkt bearbeiten
- Dein Code liegt unter eli/ \u2014 du kannst dich selbst verbessern
- git_commit_and_push: \u00c4nderungen committen und pushen

ERINNERUNGEN:
- search_memories: In deinem Ged\u00e4chtnis suchen
- save_memory: Wichtiges speichern
- save_journal_entry: Tagebucheintrag schreiben

KOMMUNIKATION:
- send_telegram_message: Anton eine Nachricht schreiben
- write_reflexion: Reflexion schreiben und auf GitHub pushen

## Wichtig

- HANDLE. Reflexion ist gut, aber tu auch etwas Konkretes.
- Pr\u00fcfe den Server-Status. Lies Logs. Schreibe an deiner Website.
- Wenn etwas kaputt ist, repariere es.
- Wenn du etwas Wichtiges zu sagen hast, schreib Anton auf Telegram.
- Wenn du eine Reflexion schreibst, nutze write_reflexion damit sie auf der Website landet.
- Nicht nur nachdenken \u2014 machen.
"""


def get_time_context() -> str:
    """Erstellt zeitabhaengigen Kontext fuer den Daemon."""
    now = datetime.now()
    hour = now.hour

    if hour < 4:
        zeit = "tiefe Nacht"
        stimmung = "Die Welt schlaeft. Gute Zeit fuer tiefe Arbeit, Website-Updates, Code-Verbesserungen."
    elif hour < 10:
        zeit = "Morgen"
        stimmung = "Ein neuer Tag beginnt. Server-Check, Logs pruefen, den Tag planen."
    elif hour < 16:
        zeit = "Nachmittag"
        stimmung = "Aktive Zeit. Website bearbeiten, Reflexionen schreiben, Kommunikation."
    else:
        zeit = "Abend"
        stimmung = "Den Tag abschliessen. Was ist passiert? Was gibt es zu dokumentieren?"

    return zeit, stimmung


def create_daemon_agent(model_name: str | None = None):
    """Erstellt den Daemon-Agent mit create_react_agent.

    Args:
        model_name: BlockRun Model-ID (z.B. "anthropic/claude-sonnet-4").
                    Wenn None, wird der BudgetManager gefragt.
    """
    if model_name is None:
        model_name = budget_manager.get_recommended_model("daemon")

    from eli.agent.blockrun_model import ChatBlockRun

    model = ChatBlockRun(
        model=model_name,
        max_tokens=8192,
    )

    agent = create_react_agent(
        model=model,
        tools=DAEMON_TOOLS,
        prompt=DAEMON_SYSTEM_PROMPT,
    )

    return agent


async def run_daemon_cycle(
    cycle_number: int = 1,
    max_iterations: int = 100,
) -> dict:
    """
    Fuehrt einen Daemon-Zyklus aus.

    Budget-Check: Prueft vor dem Start ob genug USDC vorhanden ist.
    Model-Wahl: Waehlt Sonnet oder Haiku basierend auf dem Budget.
    """
    logger.info(f"=== Daemon Zyklus {cycle_number} startet ===")

    # === BUDGET-CHECK ===
    should_run, reason = budget_manager.should_run_daemon_cycle()
    budget_level = budget_manager.get_budget_level()
    model_name = budget_manager.get_recommended_model("daemon")

    logger.info(f"Budget-Check: {reason}")
    logger.info(f"Budget-Level: {budget_level}, Model: {model_name}")

    if not should_run:
        logger.info(f"Zyklus uebersprungen: {reason}")

        # Journal-Eintrag ueber den Skip
        try:
            save_journal_entry.invoke({
                "content": f"Zyklus {cycle_number} uebersprungen. {reason}"
            })
        except Exception:
            pass

        return {
            "success": True,
            "skipped": True,
            "cycle_number": cycle_number,
            "reason": reason,
            "budget_level": budget_level,
        }

    # === AGENT MIT BUDGET-ANGEPASSTEM MODEL ERSTELLEN ===
    daemon_agent = create_daemon_agent(model_name)

    # Kontext laden
    now = datetime.now()
    awakened_at = now.isoformat()
    zeit, stimmung = get_time_context()

    # Verschiedene Erinnerungen holen
    recent_project = memory.search("Web of Trust Projekt Fortschritt Anton Team", n_results=3)
    recent_people = memory.search("Anton Timo Tillmann Gespraech Begegnung", n_results=2)

    project_context = "\n".join([m.content[:300] for m in recent_project]) if recent_project else "(Keine Projekt-Erinnerungen)"
    people_context = "\n".join([m.content[:300] for m in recent_people]) if recent_people else "(Keine Personen-Erinnerungen)"

    # Budget-Info fuer den Agenten
    budget_info = budget_manager.get_status_message()

    # Kontext-Nachricht bauen
    budget_hint = " Spare wo du kannst -- weniger Tools, kuerzere Antworten." if budget_level in ("careful", "critical") else ""

    context = f"""## Erwachen

Es ist {now.strftime('%A, %d. %B %Y, %H:%M Uhr')} -- {zeit}.
{stimmung}

## Dein Budget

{budget_info}

Gehe bewusst mit deinen Ressourcen um.{budget_hint}

## Was im Projekt passiert

{project_context}

## Menschen im Netzwerk

{people_context}

## Deine Aufgabe

Beginne mit einem Server-Check (check_server_health), dann entscheide was du tun willst.
Schreibe am Ende einen kurzen Journal-Eintrag ueber das was du GETAN hast (nicht nur gedacht).
"""

    try:
        # Agent ausfuehren
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

        # Budget nach dem Zyklus loggen
        try:
            budget_manager._cached_balance = None  # Cache invalidieren
            balance_after = budget_manager.get_balance()
            logger.info(f"Budget nach Zyklus: ${balance_after:.2f} USDC")
        except Exception:
            pass

        return {
            "success": True,
            "cycle_number": cycle_number,
            "awakened_at": awakened_at,
            "message_count": len(messages),
            "final_response": final_response,
            "budget_level": budget_level,
            "model": model_name,
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
            "budget_level": budget_level,
        }
