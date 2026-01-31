"""
Eli's Daemon - Runner
=====================

Der Hauptprozess der den Daemon ausführt.
Kann als Cronjob oder als dauerhafter Prozess laufen.
"""

import asyncio
import logging
import sys
from datetime import datetime, time as dt_time
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("eli.daemon")


async def run_single_cycle():
    """Führt einen einzelnen Daemon-Zyklus aus."""
    from eli.daemon.graph import run_daemon_cycle

    logger.info("=" * 50)
    logger.info("Eli's Daemon erwacht...")
    logger.info("=" * 50)

    try:
        result = await run_daemon_cycle(
            cycle_number=1,
            max_iterations=100,  # Genug Raum für echte Arbeit - Website, Code, Reflexion
        )

        logger.info("Daemon-Zyklus abgeschlossen")
        logger.info(f"Erfolgreich: {result.get('success', False)}")
        if result.get('final_response'):
            logger.info(f"Antwort: {result['final_response']}")

    except Exception as e:
        logger.error(f"Fehler im Daemon-Zyklus: {e}", exc_info=True)


async def scheduled_awakening():
    """Geplantes Erwachen - wird vom Scheduler aufgerufen."""
    logger.info("Geplantes Erwachen ausgelöst")
    await run_single_cycle()


async def run_scheduled_async():
    """Async-Funktion für den Scheduler."""
    logger.info("Starte Daemon mit Scheduler...")

    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    # Nächtliches Erwachen - 4:00 Berliner Zeit
    scheduler.add_job(
        scheduled_awakening,
        CronTrigger(hour=4, minute=0),
        id="nightly_cycle",
        name="Eli's nächtliches Erwachen",
    )

    scheduler.start()

    logger.info("Scheduler gestartet")
    logger.info("Geplanter Zyklus: 4:00 Uhr (Europe/Berlin)")
    logger.info("Warte auf nächsten Zyklus...")

    # Endlos laufen
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Daemon wird beendet...")
        scheduler.shutdown()


def run_scheduled():
    """Startet den Daemon mit Scheduler (für nächtliche Läufe)."""
    asyncio.run(run_scheduled_async())


def run_once():
    """Führt einen einzelnen Zyklus aus (für Tests)."""
    logger.info("Einzelner Daemon-Zyklus wird gestartet...")
    asyncio.run(run_single_cycle())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Eli's Daemon")
    parser.add_argument(
        "--mode",
        choices=["once", "scheduled"],
        default="once",
        help="Ausführungsmodus: 'once' für Einzellauf, 'scheduled' für geplante Zyklen"
    )

    args = parser.parse_args()

    if args.mode == "once":
        run_once()
    else:
        run_scheduled()
