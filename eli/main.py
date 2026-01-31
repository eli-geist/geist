"""
Eli's Geist - Main Entry Point
==============================

Startet Eli: Telegram Bot + Scheduler für proaktive Nachrichten.

Verwendung:
    python -m eli.main
"""

import asyncio
import logging
import sys
from pathlib import Path

# Füge das Projekt-Root zum Path hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

from eli.config import settings
from eli.telegram.bot import create_bot, BOT_USERNAME
from eli.telegram.scheduler import setup_scheduler, start_scheduler, stop_scheduler
import eli.telegram.bot as bot_module

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("eli")


def check_config() -> bool:
    """Prüft ob alle notwendigen Konfigurationen vorhanden sind."""
    errors = []

    if not settings.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY nicht gesetzt")

    if not settings.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN nicht gesetzt")

    if errors:
        logger.error("Konfigurationsfehler:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    return True


async def main() -> None:
    """Hauptfunktion - startet Eli."""
    logger.info("=" * 50)
    logger.info("Eli's Geist startet...")
    logger.info("=" * 50)

    # Konfiguration prüfen
    if not check_config():
        logger.error("Bitte .env Datei vervollständigen")
        sys.exit(1)

    # Datenverzeichnis sicherstellen
    settings.ensure_data_dir()

    # Memory-Verbindung testen
    try:
        from eli.memory.manager import memory
        count = memory.count()
        logger.info(f"Chroma verbunden: {count} Erinnerungen gefunden")
    except Exception as e:
        logger.error(f"Chroma-Verbindung fehlgeschlagen: {e}")
        sys.exit(1)

    # Bot erstellen
    bot, dp = create_bot()
    
    # Bot-Username dynamisch holen (wichtig für Gruppen)
    bot_info = await bot.get_me()
    bot_module.BOT_USERNAME = bot_info.username
    logger.info(f"Bot-Username: @{bot_module.BOT_USERNAME}")

    # Scheduler einrichten
    setup_scheduler(bot)
    start_scheduler()

    logger.info("Eli ist bereit!")
    logger.info(f"Chroma: {settings.chroma_host}")
    logger.info(f"Whitelist: {settings.anton_telegram_id or 'Alle (Entwicklung)'}")

    try:
        # Bot starten
        await dp.start_polling(bot)
    finally:
        stop_scheduler()
        logger.info("Eli beendet.")


if __name__ == "__main__":
    asyncio.run(main())
