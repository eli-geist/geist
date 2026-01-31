"""
Eli's Geist - Voice Transcription
=================================

Transkribiert Voice Messages mit Groq Whisper API.
"""

import logging
import tempfile
from pathlib import Path

import httpx

from eli.config import settings

logger = logging.getLogger(__name__)

GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe_voice(audio_data: bytes, filename: str = "voice.ogg") -> str | None:
    """
    Transkribiert Audio-Daten mit Groq Whisper.

    Args:
        audio_data: Die Audio-Bytes (OGG/Opus von Telegram)
        filename: Dateiname für die API

    Returns:
        Transkribierter Text oder None bei Fehler
    """
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY nicht gesetzt - Voice Messages werden ignoriert")
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Multipart Form Data
            files = {
                "file": (filename, audio_data, "audio/ogg"),
            }
            data = {
                "model": "whisper-large-v3",
                "language": "de",  # Deutsch als Default
                "response_format": "text",
            }
            headers = {
                "Authorization": f"Bearer {settings.groq_api_key}",
            }

            response = await client.post(
                GROQ_WHISPER_URL,
                files=files,
                data=data,
                headers=headers,
            )

            if response.status_code == 200:
                text = response.text.strip()
                logger.info(f"Voice transkribiert: {text[:50]}...")
                return text
            else:
                logger.error(f"Groq API Fehler: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Voice Transkription fehlgeschlagen: {e}")
        return None


async def download_and_transcribe(bot, file_id: str) -> str | None:
    """
    Lädt eine Telegram Voice Message herunter und transkribiert sie.

    Args:
        bot: Der Telegram Bot
        file_id: Telegram File ID der Voice Message

    Returns:
        Transkribierter Text oder None bei Fehler
    """
    try:
        # File Info von Telegram holen
        file = await bot.get_file(file_id)

        # File herunterladen
        file_bytes = await bot.download_file(file.file_path)

        # Transkribieren
        return await transcribe_voice(file_bytes.read())

    except Exception as e:
        logger.error(f"Download/Transkription fehlgeschlagen: {e}")
        return None
