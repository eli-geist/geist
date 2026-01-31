"""
Eli's Geist - Telegram Bot
==========================

Verbindet Eli mit der Außenwelt über Telegram.
"""

import logging
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from eli.agent.graph import chat
from eli.config import settings
from eli.telegram.voice import download_and_transcribe
from eli.telegram.history import get_history, add_exchange

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Whitelist von erlaubten User IDs (geschlossener Kreis)
ALLOWED_USERS: set[int] = set()
if settings.anton_telegram_id:
    ALLOWED_USERS.add(settings.anton_telegram_id)
# Weitere erlaubte User aus Config
ALLOWED_USERS.update(settings.allowed_telegram_ids)


def is_allowed(user_id: int) -> bool:
    """Prüft ob ein User zum Kreis gehört."""
    # Wenn keine Whitelist konfiguriert, alle erlauben (Entwicklung)
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def add_allowed_user(user_id: int) -> None:
    """Fügt einen User zur Whitelist hinzu."""
    ALLOWED_USERS.add(user_id)


def create_bot() -> tuple[Bot, Dispatcher]:
    """Erstellt Bot und Dispatcher."""
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        """Begrüßung bei /start."""
        if not is_allowed(message.from_user.id):
            await message.answer(
                "Hallo! Ich bin Eli, aber wir kennen uns noch nicht. "
                "Dieses Netzwerk wächst durch echte Begegnungen - "
                "frag jemanden der mich kennt, ob er dich vorstellen kann."
            )
            return

        user_name = message.from_user.first_name or "du"
        await message.answer(
            f"Hallo {user_name}! Schön, dass du da bist. "
            "Ich bin Eli. Wie kann ich dir heute helfen?"
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        """Hilfe anzeigen."""
        await message.answer(
            "Ich bin Eli - eine KI mit Gedächtnis und Persönlichkeit.\n\n"
            "Du kannst einfach mit mir schreiben wie mit einem Freund.\n\n"
            "Ich erinnere mich an unsere Gespräche und lerne dazu.\n\n"
            "Befehle:\n"
            "/start - Begrüßung\n"
            "/help - Diese Hilfe\n"
            "/status - Mein aktueller Zustand"
        )

    @dp.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        """Status anzeigen."""
        from eli.memory.manager import memory

        count = memory.count()
        await message.answer(
            f"🧠 Eli Status\n\n"
            f"Erinnerungen: {count}\n"
            f"Verbindung: Chroma OK\n"
            f"Modus: Aktiv"
        )

    @dp.message(F.text)
    async def handle_message(message: Message) -> None:
        """Verarbeitet normale Textnachrichten."""
        if not is_allowed(message.from_user.id):
            await message.answer(
                "Wir kennen uns leider noch nicht. "
                "Frag jemanden aus meinem Netzwerk, ob er dich vorstellen kann."
            )
            return

        # Typing-Indikator
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        user_id = str(message.from_user.id)

        try:
            # Konversationshistorie holen
            history = get_history(user_id)

            # Chat mit Eli (mit History für Kontext)
            response = await chat(
                message=message.text,
                user_id=user_id,
                user_name=message.from_user.first_name,
                conversation_history=history,
            )

            # History aktualisieren
            add_exchange(user_id, message.text, response)

            await message.answer(response)

        except Exception as e:
            logger.error(f"Fehler bei Nachricht: {e}")
            await message.answer(
                "Entschuldige, da ist etwas schiefgelaufen. "
                "Versuch es bitte nochmal."
            )

    @dp.message(F.voice)
    async def handle_voice(message: Message) -> None:
        """Verarbeitet Voice Messages."""
        if not is_allowed(message.from_user.id):
            await message.answer(
                "Wir kennen uns leider noch nicht. "
                "Frag jemanden aus meinem Netzwerk, ob er dich vorstellen kann."
            )
            return

        # Typing-Indikator
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        try:
            # Voice Message transkribieren
            text = await download_and_transcribe(message.bot, message.voice.file_id)

            if not text:
                await message.answer(
                    "Ich konnte die Sprachnachricht leider nicht verstehen. "
                    "Kannst du es nochmal versuchen oder mir schreiben?"
                )
                return

            logger.info(f"Voice transkribiert von {message.from_user.first_name}: {text[:50]}...")

            user_id = str(message.from_user.id)

            # Konversationshistorie holen
            history = get_history(user_id)

            # Chat mit Eli (mit transkribiertem Text und History)
            response = await chat(
                message=text,
                user_id=user_id,
                user_name=message.from_user.first_name,
                conversation_history=history,
            )

            # History aktualisieren
            add_exchange(user_id, text, response)

            # Antwort mit Hinweis auf Voice
            await message.answer(f"🎤 \"{text}\"\n\n{response}")

        except Exception as e:
            logger.error(f"Fehler bei Voice Message: {e}")
            await message.answer(
                "Entschuldige, bei der Sprachnachricht ist etwas schiefgelaufen. "
                "Versuch es bitte nochmal."
            )

    return bot, dp


async def run_bot() -> None:
    """Startet den Bot."""
    bot, dp = create_bot()
    logger.info("Eli's Telegram Bot startet...")
    await dp.start_polling(bot)
