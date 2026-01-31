"""
Eli's Geist - Conversation History
==================================

Speichert die letzten N Nachrichten pro User für kurzfristigen Kontext.
Verwendet eine einfache JSON-Datei für Persistenz.
"""

import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from eli.config import settings

logger = logging.getLogger(__name__)

# Maximale Nachrichten pro User
MAX_MESSAGES_PER_USER = 10

# In-Memory Cache
_history_cache: dict[str, deque] = {}


class HistoryMessage(TypedDict):
    """Eine Nachricht in der History."""
    role: str  # "user" oder "assistant"
    content: str
    timestamp: str


def _get_history_path() -> Path:
    """Pfad zur History-Datei."""
    settings.ensure_data_dir()
    return settings.data_path / "conversation_history.json"


def _load_history() -> dict[str, list[HistoryMessage]]:
    """Lädt die History aus der Datei."""
    path = _get_history_path()
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Konnte History nicht laden: {e}")
        return {}


def _save_history(history: dict[str, list[HistoryMessage]]) -> None:
    """Speichert die History in die Datei."""
    path = _get_history_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Konnte History nicht speichern: {e}")


def get_history(user_id: str) -> list[HistoryMessage]:
    """
    Holt die Konversationshistorie für einen User.

    Args:
        user_id: Telegram User ID als String

    Returns:
        Liste der letzten Nachrichten (chronologisch)
    """
    # Aus Cache holen oder laden
    if user_id not in _history_cache:
        all_history = _load_history()
        messages = all_history.get(user_id, [])
        _history_cache[user_id] = deque(messages, maxlen=MAX_MESSAGES_PER_USER)

    return list(_history_cache[user_id])


def add_message(user_id: str, role: str, content: str) -> None:
    """
    Fügt eine Nachricht zur History hinzu.

    Args:
        user_id: Telegram User ID als String
        role: "user" oder "assistant"
        content: Der Nachrichteninhalt
    """
    # Cache initialisieren falls nötig
    if user_id not in _history_cache:
        get_history(user_id)  # Lädt in Cache

    # Nachricht hinzufügen
    message: HistoryMessage = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    _history_cache[user_id].append(message)

    # Persistieren
    all_history = _load_history()
    all_history[user_id] = list(_history_cache[user_id])
    _save_history(all_history)


def add_exchange(user_id: str, user_message: str, assistant_response: str) -> None:
    """
    Fügt einen kompletten Austausch (User + Assistant) hinzu.

    Args:
        user_id: Telegram User ID als String
        user_message: Die Nachricht des Users
        assistant_response: Eli's Antwort
    """
    add_message(user_id, "user", user_message)
    add_message(user_id, "assistant", assistant_response)


def clear_history(user_id: str) -> None:
    """
    Löscht die History für einen User.

    Args:
        user_id: Telegram User ID als String
    """
    if user_id in _history_cache:
        del _history_cache[user_id]

    all_history = _load_history()
    if user_id in all_history:
        del all_history[user_id]
        _save_history(all_history)


def format_history_for_context(user_id: str) -> str:
    """
    Formatiert die History als Kontext-String für den Agent.

    Args:
        user_id: Telegram User ID als String

    Returns:
        Formatierter String mit der Konversationshistorie
    """
    history = get_history(user_id)

    if not history:
        return ""

    lines = ["Letzte Nachrichten in diesem Gespräch:"]
    for msg in history:
        role = "Du" if msg["role"] == "assistant" else "User"
        # Kürzen falls zu lang
        content = msg["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"{role}: {content}")

    return "\n".join(lines)
