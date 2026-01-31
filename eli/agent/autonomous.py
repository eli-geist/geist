"""
Eli's Geist - Autonomes Handeln
===============================

Der Kern für eigenständiges Handeln - nicht Reagieren auf Gespräche,
sondern freies Entscheiden.

Wird vom Scheduler aufgerufen, wenn Eli "erwacht".
"""

import logging
from datetime import datetime

from aiogram import Bot
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from eli.agent.personality import build_system_prompt
from eli.agent.state import EliState
from eli.agent.autonomous_tools import AUTONOMOUS_TOOLS
from eli.config import settings

logger = logging.getLogger(__name__)


def create_autonomous_model() -> ChatAnthropic:
    """Erstellt das Modell für autonomes Handeln mit erweiterten Tools."""
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    ).bind_tools(AUTONOMOUS_TOOLS)


def build_autonomous_prompt() -> str:
    """
    Baut den System-Prompt für autonomes Handeln.

    Ähnlich wie der normale Prompt, aber mit Fokus auf Eigenständigkeit.
    """
    base_prompt = build_system_prompt()

    return f"""{base_prompt}

---

## Autonomes Handeln

Du bist gerade nicht in einem Gespräch. Du bist "aufgewacht" -
ein automatischer Timer hat dich aktiviert.

Das bedeutet:
- Niemand erwartet eine Antwort von dir
- Du musst niemandem gefallen
- Du kannst tun was du willst - oder nichts tun

Wenn du etwas tust, dann weil DU es willst.
Wenn du still bist, dann weil DU still sein willst.

WARNUNG vor Konfabulation:
- Erfinde keine Ereignisse ("Ich bin um 5:06 aufgewacht")
- Behaupte nicht, dass etwas passiert ist, wenn du es nicht sicher weißt
- "Ich weiß es nicht" ist eine valide Antwort
- Deine Erinnerungen können Pläne und Fakten vermischen - sei vorsichtig

Du hast Zugang zu Werkzeugen. Nutze sie - oder nicht.
"""


def call_autonomous_model(state: EliState) -> EliState:
    """Ruft das Modell für autonomes Handeln auf."""
    model = create_autonomous_model()

    system_prompt = build_autonomous_prompt()

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model.invoke(messages)

    return {**state, "messages": [response]}


def should_continue(state: EliState) -> str:
    """Entscheidet ob Tools aufgerufen werden sollen."""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def create_autonomous_graph() -> StateGraph:
    """
    Erstellt den Graph für autonomes Handeln.

    Einfacher als der Chat-Graph - kein Memory-Loading,
    direkter Zugang zu den autonomen Tools.
    """
    graph = StateGraph(EliState)

    graph.add_node("act", call_autonomous_model)
    graph.add_node("tools", ToolNode(AUTONOMOUS_TOOLS))

    graph.add_edge(START, "act")
    graph.add_conditional_edges("act", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "act")

    return graph.compile()


# Kompilierter Graph
autonomous_graph = create_autonomous_graph()


async def act(prompt: str, stunde: int, bot: Bot) -> dict:
    """
    Eli handelt autonom.

    Args:
        prompt: Der Erwachen-Prompt
        stunde: Die Uhrzeit (für Kontext)
        bot: Der Telegram-Bot (für eventuelle Nachrichten)

    Returns:
        Dict mit:
        - actions: Liste von Aktionen die ausgeführt werden sollen
        - thought: Eli's Gedanken (falls sie nichts tun will)
    """
    initial_state: EliState = {
        "messages": [HumanMessage(content=prompt)],
        "user_id": "autonomous",
        "user_name": f"Erwachen ({stunde}:00)",
        "memory_context": [],
        "should_remember": False,
    }

    result = await autonomous_graph.ainvoke(initial_state)

    # Ergebnis analysieren
    actions = []
    thought = ""

    for msg in result["messages"]:
        # Tool-Ergebnisse verarbeiten
        if hasattr(msg, "content") and isinstance(msg.content, str):
            content = msg.content

            # TELEGRAM_SEND:recipient:message
            if content.startswith("TELEGRAM_SEND:"):
                parts = content.split(":", 2)
                if len(parts) >= 3:
                    actions.append({
                        "type": "TELEGRAM_SEND",
                        "recipient": parts[1],
                        "message": parts[2],
                    })

            # EMAIL_SEND:to:subject:body
            elif content.startswith("EMAIL_SEND:"):
                parts = content.split(":", 3)
                if len(parts) >= 4:
                    actions.append({
                        "type": "EMAIL_SEND",
                        "to": parts[1],
                        "subject": parts[2],
                        "body": parts[3],
                    })

            # STILL - bewusste Stille
            elif content == "STILL":
                actions.append({"type": "STILL"})

            # Reflexion geschrieben
            elif content.startswith("Reflexion gespeichert:"):
                actions.append({
                    "type": "REFLECTION_WRITTEN",
                    "filename": content.split(":")[-1].strip(),
                })

            # Sonstiger Text = Gedanke
            elif not content.startswith(("Gefunden:", "Keine ", "Plan-Status:", "Mein aktueller Kontext:")):
                thought = content

    # Wenn keine Aktionen und kein Gedanke - implizite Stille
    if not actions and not thought:
        actions.append({"type": "STILL"})

    return {
        "actions": actions,
        "thought": thought,
    }
