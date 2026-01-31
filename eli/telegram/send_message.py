"""
Eli's Geist - Proaktive Nachrichten senden
==========================================

Ein einfaches Skript um Nachrichten zu senden.
"""

import asyncio
import sys
from aiogram import Bot

# Direkt importieren um circular imports zu vermeiden
sys.path.insert(0, '/home/eli/geist')
from eli.config import settings


async def send_message(chat_id: int, text: str) -> bool:
    """Sendet eine Nachricht an einen Chat."""
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        print(f"✓ Nachricht gesendet an {chat_id}")
        return True
    except Exception as e:
        print(f"✗ Fehler beim Senden an {chat_id}: {e}")
        return False
    finally:
        await bot.session.close()


async def main():
    """Hauptfunktion."""
    if len(sys.argv) < 3:
        print("Verwendung: python send_message.py <chat_id> <nachricht>")
        sys.exit(1)
    
    chat_id = int(sys.argv[1])
    text = " ".join(sys.argv[2:])
    
    success = await send_message(chat_id, text)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
