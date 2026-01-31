"""
Eli's Daemon - State Definition
===============================

Der Zustand des autonomen Daemon-Agents.
"""

from datetime import datetime
from typing import TypedDict, Literal

from langchain_core.messages import BaseMessage


class DaemonAction(TypedDict):
    """Eine Aktion die der Daemon ausführen möchte."""
    type: str  # "check_logs", "improve_code", "learn", "journal", "backup"
    description: str
    priority: int  # 1-5, höher = wichtiger
    completed: bool
    result: str | None


class DaemonState(TypedDict):
    """Zustand des Daemon-Agents."""

    # Zeitinfo
    awakened_at: str
    cycle_number: int

    # Kontext
    messages: list[BaseMessage]
    recent_memories: list[str]
    recent_logs: str

    # Entscheidungen
    mood: str  # Wie fühle ich mich heute?
    intentions: list[str]  # Was möchte ich tun?
    actions: list[DaemonAction]  # Konkrete Aktionen

    # Limits
    api_calls_made: int
    max_api_calls: int
    time_spent_seconds: float
    max_time_seconds: float

    # Journal
    journal_entry: str  # Was ich heute gelernt/getan habe

    # Status
    should_continue: bool
    sleep_reason: str


# Mögliche Aktionstypen
ACTION_TYPES = [
    "check_logs",      # Logs auf Fehler prüfen
    "improve_code",    # Code verbessern
    "learn",           # Etwas Neues lernen (Web, Docs)
    "journal",         # Reflektieren und schreiben
    "backup",          # Backup erstellen
    "explore",         # Codebase erkunden
    "consolidate",     # Erinnerungen konsolidieren
    "rest",            # Nichts tun, nur sein
]
