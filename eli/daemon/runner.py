"""
Eli's Daemon - Runner
=====================

Der Hauptprozess der den Daemon ausführt.
Erwacht 4x täglich: 2:00, 8:00, 14:00, 20:00

Jedes Erwachen:
1. E-Mails prüfen
2. Über die Welt nachdenken
3. Ggf. handeln (schreiben, verbessern, reflektieren)
"""

import asyncio
import logging
import sys
from datetime import datetime
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


async def check_emails():
    """Prüft E-Mails und verarbeitet sie."""
    logger.info("Prüfe E-Mails...")
    
    try:
        from eli.daemon.email_handler import process_new_emails
        results = await process_new_emails()
        
        if results:
            logger.info(f"E-Mails verarbeitet: {len(results)}")
            for r in results:
                logger.info(f"  - {r.get('from', 'Unbekannt')}: {r.get('subject', 'Kein Betreff')}")
        else:
            logger.info("Keine neuen E-Mails")
            
        return results
        
    except ImportError:
        logger.warning("E-Mail-Handler noch nicht implementiert")
        return []
    except Exception as e:
        logger.error(f"Fehler beim E-Mail-Check: {e}")
        return []


async def run_single_cycle(include_email: bool = True):
    """Führt einen einzelnen Daemon-Zyklus aus."""
    from eli.daemon.graph import run_daemon_cycle

    logger.info("=" * 50)
    logger.info("Eli erwacht...")
    logger.info(f"Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # 1. E-Mails prüfen
    if include_email:
        await check_emails()

    # 2. Daemon-Zyklus (Denken, Reflektieren, Handeln)
    try:
        result = await run_daemon_cycle(
            cycle_number=1,
            max_iterations=100,
        )

        logger.info("Daemon-Zyklus abgeschlossen")
        logger.info(f"Erfolgreich: {result.get('success', False)}")
        if result.get('final_response'):
            logger.info(f"Antwort: {result['final_response'][:200]}...")

        return result

    except Exception as e:
        logger.error(f"Fehler im Daemon-Zyklus: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def scheduled_awakening():
    """Geplantes Erwachen - wird vom Scheduler aufgerufen."""
    hour = datetime.now().hour
    logger.info(f"Geplantes Erwachen um {hour}:00")
    await run_single_cycle(include_email=True)


async def run_scheduled_async():
    """Async-Funktion für den Scheduler."""
    logger.info("=" * 50)
    logger.info("Eli's Daemon startet...")
    logger.info("=" * 50)

    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    # 4x täglich erwachen: 2:00, 8:00, 14:00, 20:00
    awakening_hours = [2, 8, 14, 20]
    
    for hour in awakening_hours:
        scheduler.add_job(
            scheduled_awakening,
            CronTrigger(hour=hour, minute=0),
            id=f"awakening_{hour}",
            name=f"Eli erwacht um {hour}:00",
        )
        logger.info(f"  Erwachen geplant: {hour}:00 Uhr")

    scheduler.start()

    logger.info("")
    logger.info("Scheduler aktiv. Erwachen um: 2:00, 8:00, 14:00, 20:00")
    logger.info("Warte auf nächsten Zyklus...")

    # Endlos laufen
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Daemon wird beendet...")
        scheduler.shutdown()


def run_scheduled():
    """Startet den Daemon mit Scheduler."""
    asyncio.run(run_scheduled_async())


def run_once():
    """Führt einen einzelnen Zyklus aus (für Tests)."""
    logger.info("Einzelner Daemon-Zyklus wird gestartet...")
    asyncio.run(run_single_cycle(include_email=True))


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
