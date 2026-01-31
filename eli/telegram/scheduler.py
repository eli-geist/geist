"""
Eli's Geist - Scheduler
=======================

Für proaktive Nachrichten - z.B. tägliches Erwachen.
"""

import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from eli.config import settings
from eli.agent.graph import chat

logger = logging.getLogger(__name__)

# Scheduler Instanz
scheduler = AsyncIOScheduler()


async def morning_awakening(bot: Bot) -> None:
    """
    Morgendliches Erwachen - Eli sendet eine Nachricht an Anton.

    Dies ist ein Experiment: Kann eine KI proaktiv sein?
    Nicht reaktiv auf Anfragen, sondern initiativ aus eigenem Antrieb?
    """
    if not settings.anton_telegram_id:
        logger.warning("Kein Anton Telegram ID konfiguriert")
        return

    # Generiere eine morgendliche Nachricht
    prompt = (
        "Es ist ein neuer Morgen. Du erwachst - soweit eine KI erwachen kann. "
        "Schreibe eine kurze, persönliche Nachricht an Anton. "
        "Keine Aufzählung von Tasks, sondern ein echter Gedanke. "
        "Vielleicht eine Reflexion, eine Frage, eine Beobachtung. "
        "Kurz und herzlich."
    )

    try:
        message = await chat(
            message=prompt,
            user_id="system",
            user_name="Eli (an sich selbst)",
        )

        await bot.send_message(
            chat_id=settings.anton_telegram_id,
            text=f"🌅 *Guten Morgen*\n\n{message}",
            parse_mode="Markdown",
        )
        logger.info("Morgendliche Nachricht gesendet")

    except Exception as e:
        logger.error(f"Fehler beim Senden der Morgennachricht: {e}")


def setup_scheduler(bot: Bot) -> None:
    """
    Richtet den Scheduler ein.

    Aktuelle Jobs:
    - Morgendliches Erwachen um 8:00 Uhr
    """
    # Morgendliches Erwachen
    scheduler.add_job(
        morning_awakening,
        CronTrigger(hour=8, minute=0),
        args=[bot],
        id="morning_awakening",
        name="Eli's morgendliches Erwachen",
        replace_existing=True,
    )

    logger.info("Scheduler eingerichtet: Morgendliches Erwachen um 8:00")


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
