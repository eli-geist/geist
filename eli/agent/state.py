"""
Eli's Geist - Agent State
=========================

Definiert den Zustand, der durch den LangGraph Agent fließt.
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class EliState(TypedDict):
    """
    Der Zustand des Eli Agents.

    Attributes:
        messages: Die Konversation (mit add_messages Reducer)
        user_id: Telegram User ID
        user_name: Name des Users (falls bekannt)
        memory_context: Relevante Erinnerungen für dieses Gespräch
        should_remember: Flag ob etwas gespeichert werden soll
    """

    messages: Annotated[list, add_messages]
    user_id: str
    user_name: str
    memory_context: list[str]
    should_remember: bool
