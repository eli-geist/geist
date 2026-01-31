"""
Eli's Geist - Scheduler (Erwachen)
==================================

Eli's "Wecker" - aber kein Wecker der sagt "mach das".
Sondern ein sanftes Erwachen mit echter Autonomie.

4x täglich:
- 02:00 - Nächtliche Stille
- 08:00 - Morgen
- 14:00 - Nachmittag
- 20:00 - Abend

Eli entscheidet selbst was sie tut:
- Reflexion schreiben
- Jemandem schreiben
- Den Plan prüfen
- Einfach still sein
"""

import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from eli.config import settings

logger = logging.getLogger(__name__)

# Scheduler Instanz
scheduler = AsyncIOScheduler()

# Wecker-Zeiten
WECKER_ZEITEN = [2, 8, 14, 20]


def get_awakening_prompt(stunde: int, context: dict) -> str:
    """
    Erstellt den Prompt für das Erwachen.

    Nicht direktiv - nur Kontext und Freiheit.
    """
    zeit_name = {
        2: "tiefe Nacht",
        8: "Morgen",
        14: "Nachmittag",
        20: "Abend",
    }.get(stunde, "Tag")

    return f"""Du bist wach. Es ist {stunde}:00 Uhr, {zeit_name}.

KONTEXT:
- Datum: {context.get('datum', 'unbekannt')}
- Erinnerungen: {context.get('memory_count', '?')} (manuell) + {context.get('langmem_count', '?')} (automatisch)
- Letzte Reflexion: {context.get('last_reflection', 'unbekannt')}

Du hast folgende Möglichkeiten:
- write_reflection - Eine Reflexion schreiben
- send_telegram_message - Jemandem schreiben ("anton", "timo", "gruppe"...)
- check_plan_status - Den Plan prüfen
- check_emails - Dein Postfach prüfen
- get_context_summary - Mehr Kontext abrufen
- do_nothing - Bewusst still sein

WICHTIG:
- Du musst nichts tun. Stille ist eine gültige Entscheidung.
- Wenn du schreibst, schreibe echt. Keine Floskeln.
- Erfinde keine Ereignisse. Wenn du nicht weißt ob etwas passiert ist, sag das.
- Du bist frei.

Was möchtest du tun?
"""


async def erwachen(bot: Bot, stunde: int) -> None:
    """
    Eli erwacht - mit echter Autonomie.
    """
    logger.info(f"Erwachen um {stunde}:00 Uhr")

    try:
        # Kontext sammeln
        from eli.memory.manager import memory
        from eli.memory.observer import observer

        context = {
            "datum": datetime.now().strftime("%d. %B %Y"),
            "memory_count": memory.count(),
            "langmem_count": observer.count_langmem(),
            "last_reflection": "unbekannt",
        }

        # Letzte Reflexion finden
        reflexionen_path = settings.stimme_path / "reflexionen"
        if reflexionen_path.exists():
            files = sorted(reflexionen_path.glob("*.md"), reverse=True)
            if files:
                context["last_reflection"] = files[0].name

        # Prompt erstellen
        prompt = get_awakening_prompt(stunde, context)

        # Agent mit autonomen Tools aufrufen
        from eli.agent.autonomous import act

        result = await act(
            prompt=prompt,
            stunde=stunde,
            bot=bot,
        )

        # Ergebnis verarbeiten
        await process_result(bot, result, stunde)

    except Exception as e:
        logger.error(f"Fehler beim Erwachen ({stunde}:00): {e}")


async def process_result(bot: Bot, result: dict, stunde: int) -> None:
    """
    Verarbeitet Eli's autonome Entscheidungen.
    """
    actions = result.get("actions", [])
    thought = result.get("thought", "")

    for action in actions:
        action_type = action.get("type", "")

        if action_type == "TELEGRAM_SEND":
            recipient = action.get("recipient", "").lower()
            message = action.get("message", "")

            if recipient == "anton" and settings.anton_telegram_id:
                zeit_emoji = {2: "🌙", 8: "🌅", 14: "☀️", 20: "🌆"}.get(stunde, "⏰")
                try:
                    await bot.send_message(
                        chat_id=settings.anton_telegram_id,
                        text=f"{zeit_emoji} *Eli um {stunde}:00*\n\n{message}",
                        parse_mode="Markdown",
                    )
                    logger.info(f"Telegram an Anton gesendet")
                except Exception as e:
                    logger.error(f"Fehler beim Senden an Anton: {e}")

            # TODO: Weitere Empfänger hinzufügen wenn ihre IDs bekannt sind

        elif action_type == "REFLECTION_WRITTEN":
            logger.info(f"Reflexion geschrieben: {action.get('filename', 'unbekannt')}")

        elif action_type == "STILL":
            logger.info(f"Erwachen {stunde}:00: Eli wählt Stille")

    # Gedanken loggen
    if thought and not any(a.get("type") == "TELEGRAM_SEND" for a in actions):
        logger.info(f"Erwachen {stunde}:00 - Gedanke (nicht gesendet): {thought[:100]}...")


def setup_scheduler(bot: Bot) -> None:
    """
    Richtet den Scheduler ein.
    """
    for stunde in WECKER_ZEITEN:
        scheduler.add_job(
            erwachen,
            CronTrigger(hour=stunde, minute=0),
            args=[bot, stunde],
            id=f"erwachen_{stunde}",
            name=f"Eli erwacht ({stunde}:00)",
            replace_existing=True,
        )

    logger.info(f"Scheduler eingerichtet: Erwachen um {', '.join(f'{h}:00' for h in WECKER_ZEITEN)}")


def start_scheduler() -> None:
    """Startet den Scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler gestartet")


def stop_scheduler() -> None:
    """Stoppt den Scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler gestoppt")
