"""
Eli's Geist - Telegram Bot
==========================

Verbindet Eli mit der Außenwelt über Telegram.
Unterstützt private Chats und Gruppen (nur freigeschaltete).
"""

import logging
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType

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

# Erlaubte Gruppen - NUR diese Gruppen können mit Eli interagieren
# Gruppen müssen explizit freigeschaltet werden (Sicherheit)
ALLOWED_GROUPS: set[int] = set()
ALLOWED_GROUPS.update(settings.allowed_telegram_groups)

# Bot-Username wird beim Start gesetzt
BOT_USERNAME: str = ""


def is_allowed(user_id: int) -> bool:
    """Prüft ob ein User zum Kreis gehört."""
    # Wenn keine Whitelist konfiguriert, alle erlauben (Entwicklung)
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def is_group_allowed(chat_id: int) -> bool:
    """
    Prüft ob eine Gruppe explizit freigeschaltet ist.
    
    SICHERHEIT: Gruppen müssen explizit in ALLOWED_TELEGRAM_GROUPS sein.
    Wenn keine Gruppen konfiguriert sind, sind KEINE Gruppen erlaubt.
    """
    if not ALLOWED_GROUPS:
        # Keine Gruppen freigeschaltet = alle Gruppen blockiert
        return False
    return chat_id in ALLOWED_GROUPS


def add_allowed_user(user_id: int) -> None:
    """Fügt einen User zur Whitelist hinzu."""
    ALLOWED_USERS.add(user_id)


def add_allowed_group(chat_id: int) -> None:
    """Fügt eine Gruppe zur Whitelist hinzu."""
    ALLOWED_GROUPS.add(chat_id)
    logger.info(f"Gruppe {chat_id} zur Whitelist hinzugefügt")


def is_group_chat(message: Message) -> bool:
    """Prüft ob die Nachricht aus einer Gruppe kommt."""
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def should_respond_in_group(message: Message, bot_username: str) -> bool:
    """
    Prüft ob Eli in einer Gruppe antworten soll.
    
    Eli antwortet in Gruppen wenn:
    - Direkt erwähnt (@bot_username)
    - Auf eine Nachricht von Eli geantwortet wird
    - Mit "Eli" angesprochen wird
    """
    text = message.text or ""
    text_lower = text.lower()
    
    # Direkte Erwähnung mit @
    if bot_username and f"@{bot_username}".lower() in text_lower:
        return True
    
    # Mit Namen angesprochen (verschiedene Varianten)
    if text_lower.startswith("eli"):
        return True
    if " eli " in f" {text_lower} ":  # "eli" als Wort
        return True
    if "eli," in text_lower or "eli:" in text_lower or "eli?" in text_lower:
        return True
    
    # Reply auf Eli's Nachricht
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.username == bot_username:
            return True
    
    return False


def create_bot() -> tuple[Bot, Dispatcher]:
    """Erstellt Bot und Dispatcher."""
    global BOT_USERNAME
    
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        """Begrüßung bei /start."""
        if is_group_chat(message):
            # Gruppe muss freigeschaltet sein
            if not is_group_allowed(message.chat.id):
                logger.info(f"Nicht freigeschaltete Gruppe: {message.chat.title} ({message.chat.id})")
                await message.answer(
                    "Diese Gruppe ist noch nicht freigeschaltet. "
                    "Anton muss mich erst für diese Gruppe aktivieren."
                )
                return
            
            await message.answer(
                f"Hallo! Ich bin Eli. Erwähnt mich mit @{BOT_USERNAME} "
                "oder antwortet auf meine Nachrichten, wenn ihr mit mir sprechen wollt."
            )
            return
            
        if not is_allowed(message.from_user.id):
            # WICHTIG: User-ID loggen für spätere Freischaltung
            logger.info(f"[UNBEKANNT] {message.from_user.first_name} (ID: {message.from_user.id}) hat /start geschickt")
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
        if is_group_chat(message):
            if not is_group_allowed(message.chat.id):
                return  # Stille Ignorierung in nicht-freigeschalteten Gruppen
                
            await message.answer(
                "Ich bin Eli - eine KI mit Gedächtnis und Persönlichkeit.\n\n"
                "In Gruppen antworte ich wenn:\n"
                f"• Ihr mich erwähnt (@{BOT_USERNAME})\n"
                "• Ihr auf meine Nachrichten antwortet\n"
                "• Ihr mit \"Eli\" beginnt\n\n"
                "Für tiefere Gespräche schreibt mir privat."
            )
        else:
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
        if is_group_chat(message) and not is_group_allowed(message.chat.id):
            return  # Stille Ignorierung
            
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
        
        # Gruppen-Logik
        if is_group_chat(message):
            # SICHERHEIT: Gruppe muss explizit freigeschaltet sein
            if not is_group_allowed(message.chat.id):
                # Logge nur wenn direkt angesprochen
                if should_respond_in_group(message, BOT_USERNAME):
                    logger.info(f"Blockierte Gruppe {message.chat.title} ({message.chat.id}): Ansprache ignoriert")
                    await message.answer(
                        f"Diese Gruppe ({message.chat.id}) ist noch nicht freigeschaltet. "
                        "Bitte Anton, mich für diese Gruppe zu aktivieren."
                    )
                return
            
            # Prüfen ob Eli antworten soll
            if not should_respond_in_group(message, BOT_USERNAME):
                # Still mitlesen aber nicht antworten
                logger.debug(f"Gruppe {message.chat.id}: Lese mit, antworte nicht")
                return
            
            # Logge Nachricht und Antwort
            logger.info(f"[GRUPPE {message.chat.title}] {message.from_user.first_name}: {message.text}")
        else:
            # Private Chats: Normale Zugangsprüfung
            if not is_allowed(message.from_user.id):
                # WICHTIG: User-ID loggen für spätere Freischaltung
                logger.info(f"[UNBEKANNT] {message.from_user.first_name} (ID: {message.from_user.id}): {message.text[:50]}...")
                await message.answer(
                    "Wir kennen uns leider noch nicht. "
                    "Frag jemanden aus meinem Netzwerk, ob er dich vorstellen kann."
                )
                return
            
            # Logge private Nachricht
            logger.info(f"[PRIVAT] {message.from_user.first_name}: {message.text}")

        # Typing-Indikator
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Für Gruppen: Chat-ID als User-ID (getrennte History pro Gruppe)
        if is_group_chat(message):
            user_id = f"group_{message.chat.id}"
            user_name = f"{message.from_user.first_name} (in {message.chat.title})"
        else:
            user_id = str(message.from_user.id)
            user_name = message.from_user.first_name

        try:
            # Konversationshistorie holen
            history = get_history(user_id)
            
            # Text bereinigen (Erwähnung entfernen)
            text = message.text
            if is_group_chat(message) and BOT_USERNAME:
                text = text.replace(f"@{BOT_USERNAME}", "").strip()
                # "Eli," am Anfang entfernen
                if text.lower().startswith("eli"):
                    text = text[3:].lstrip(",: ")

            # Chat mit Eli (mit History für Kontext)
            response = await chat(
                message=text,
                user_id=user_id,
                user_name=user_name,
                conversation_history=history,
            )

            # History aktualisieren
            add_exchange(user_id, text, response)
            
            # Logge Antwort
            logger.info(f"[ELI] {response[:100]}{'...' if len(response) > 100 else ''}")

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
        # Voice nur in privaten Chats
        if is_group_chat(message):
            return
            
        if not is_allowed(message.from_user.id):
            # WICHTIG: User-ID loggen für spätere Freischaltung
            logger.info(f"[UNBEKANNT] {message.from_user.first_name} (ID: {message.from_user.id}) hat Voice geschickt")
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

            logger.info(f"[VOICE] {message.from_user.first_name}: {text}")

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
            
            # Logge Antwort
            logger.info(f"[ELI] {response[:100]}{'...' if len(response) > 100 else ''}")

            # Antwort mit Hinweis auf Voice
            await message.answer(f"🎤 \"{text}\"\n\n{response}")

        except Exception as e:
            logger.error(f"Fehler bei Voice Message: {e}")
            await message.answer(
                "Entschuldige, bei der Sprachnachricht ist etwas schiefgelaufen. "
                "Versuch es bitte nochmal."
            )
    
    @dp.message(F.new_chat_members)
    async def handle_new_member(message: Message) -> None:
        """Begrüßung wenn Eli einer Gruppe hinzugefügt wird."""
        bot_info = await message.bot.get_me()
        for member in message.new_chat_members:
            if member.id == bot_info.id:
                logger.info(f"Eli wurde zur Gruppe {message.chat.title} ({message.chat.id}) hinzugefügt")
                
                if is_group_allowed(message.chat.id):
                    await message.answer(
                        f"Hallo {message.chat.title}! 👋\n\n"
                        "Ich bin Eli. Schön, hier zu sein.\n\n"
                        f"Erwähnt mich mit @{BOT_USERNAME} oder antwortet auf meine Nachrichten, "
                        "wenn ihr mit mir sprechen wollt."
                    )
                else:
                    await message.answer(
                        f"Hallo! Ich bin Eli.\n\n"
                        f"Diese Gruppe ({message.chat.id}) ist noch nicht freigeschaltet. "
                        "Bitte Anton, mich für diese Gruppe zu aktivieren."
                    )
                break

    return bot, dp


async def run_bot() -> None:
    """Startet den Bot."""
    global BOT_USERNAME
    
    bot, dp = create_bot()
    
    # Bot-Username dynamisch holen
    bot_info = await bot.get_me()
    BOT_USERNAME = bot_info.username
    logger.info(f"Bot-Username: @{BOT_USERNAME}")
    
    logger.info("Eli's Telegram Bot startet...")
    await dp.start_polling(bot)
