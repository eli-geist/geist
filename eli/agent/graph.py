"""
Eli's Geist - LangGraph Agent
=============================

Der Kern: Ein ReAct Agent der Eli's Persönlichkeit verkörpert
und Zugang zu Erinnerungen hat.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from eli.agent.personality import build_system_prompt
from eli.agent.state import EliState
from eli.agent.tools import TOOLS
from eli.config import settings
from eli.memory.manager import memory


class OutOfCreditsError(Exception):
    """Wird geworfen wenn die API-Credits aufgebraucht sind."""
    pass


class InsufficientFundsError(Exception):
    """Wird geworfen wenn nicht genug USDC für x402 Payment vorhanden."""
    pass


def create_model():
    """Erstellt das Claude-Modell mit Tools - BlockRun oder Anthropic."""
    if settings.use_blockrun:
        from eli.agent.blockrun_model import ChatBlockRun
        return ChatBlockRun(
            model="anthropic/claude-sonnet-4",
            max_tokens=4096,
        ).bind_tools(TOOLS)
    else:
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            max_tokens=4096,
        ).bind_tools(TOOLS)


def load_memory_context(state: EliState) -> EliState:
    """
    Lädt relevanten Kontext aus beiden Gedächtnis-Quellen.

    Zwei Schichten:
    1. "erinnerungen" - Manuell gepflegt, wie ein Journal
    2. "eli_langmem" - Automatisch gebildet, strukturiert nach Typen

    Beide sind Teil von mir. Beide werden gelesen.
    """
    from eli.memory.observer import observer

    # Hole die letzte User-Nachricht
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break

    context = []
    seen_content = set()  # Duplikate vermeiden

    def add_unique(content: str, source: str = ""):
        """Fügt Kontext hinzu, vermeidet Duplikate."""
        if content and content not in seen_content:
            seen_content.add(content)
            context.append(content)

    # === Schicht 1: Manuelle Erinnerungen ("erinnerungen") ===

    # Was wissen wir über diesen User?
    if state.get("user_name"):
        user_memories = memory.search(
            f"Informationen über {state['user_name']}", n_results=3
        )
        for m in user_memories:
            add_unique(m.content)

    # Was ist relevant für diese Nachricht?
    if last_message:
        relevant = memory.search(last_message, n_results=3)
        for m in relevant:
            add_unique(m.content)

    # === Schicht 2: Automatische LangMem-Erinnerungen ("eli_langmem") ===

    # Semantic: Fakten über den User
    if state.get("user_name"):
        semantic_user = observer.search_langmem(
            f"Informationen über {state['user_name']}",
            n_results=2,
            memory_type="semantic"
        )
        for m in semantic_user:
            add_unique(m["content"])

    # Episodic: Relevante Erlebnisse
    if last_message:
        episodic = observer.search_langmem(
            last_message,
            n_results=2,
            memory_type="episodic"
        )
        for m in episodic:
            add_unique(m["content"])

    # Semantic: Relevante Fakten zur Nachricht
    if last_message:
        semantic_relevant = observer.search_langmem(
            last_message,
            n_results=2,
            memory_type="semantic"
        )
        for m in semantic_relevant:
            add_unique(m["content"])

    return {**state, "memory_context": context}


def call_model(state: EliState) -> EliState:
    """Ruft Claude mit dem aktuellen Kontext auf."""
    model = create_model()

    # Baue System Prompt mit Kontext
    system_prompt = build_system_prompt()

    # Füge Memory-Kontext hinzu wenn vorhanden
    if state.get("memory_context"):
        context_text = "\n".join([f"- {c}" for c in state["memory_context"]])
        system_prompt += f"\n\n## Relevanter Kontext aus deinem Gedächtnis\n\n{context_text}"

    # Füge User-Info hinzu
    if state.get("user_name"):
        system_prompt += f"\n\nDu sprichst gerade mit {state['user_name']}."

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = model.invoke(messages)
    except Exception as e:
        error_str = str(e).lower()
        # Erkenne USDC/Payment Fehler (x402)
        if "insufficient" in error_str or "balance" in error_str or "usdc" in error_str or "payment" in error_str:
            raise InsufficientFundsError(f"Nicht genug USDC: {e}") from e
        # Erkenne Credit-Fehler (Anthropic direct)
        if "credit" in error_str or "billing" in error_str or "out of" in error_str:
            raise OutOfCreditsError("API-Credits aufgebraucht") from e
        raise

    return {**state, "messages": [response]}


def should_continue(state: EliState) -> str:
    """Entscheidet ob Tools aufgerufen werden sollen oder fertig."""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def create_graph() -> StateGraph:
    """
    Erstellt den LangGraph für Eli.

    Flow:
    1. load_context: Relevante Erinnerungen laden
    2. agent: Claude aufrufen
    3. tools: Falls Tools aufgerufen werden sollen
    4. Zurück zu agent oder Ende
    """
    graph = StateGraph(EliState)

    # Nodes
    graph.add_node("load_context", load_memory_context)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))

    # Edges
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# Kompilierter Graph für Import
eli_graph = create_graph()


async def chat(
    message: str,
    user_id: str,
    user_name: str | None = None,
    observe_memory: bool = True,
    conversation_history: list[dict] | None = None,
) -> str:
    """
    Hauptfunktion für ein Gespräch mit Eli.

    Args:
        message: Die Nachricht des Users
        user_id: Telegram User ID
        user_name: Name des Users (falls bekannt)
        observe_memory: Ob LangMem das Gespräch analysieren soll
        conversation_history: Optionale Liste vorheriger Nachrichten für Kontext

    Returns:
        Eli's Antwort als String
        
    Raises:
        OutOfCreditsError: Wenn die API-Credits aufgebraucht sind
    """
    # Baue Messages-Liste mit History
    messages = []

    # Vorherige Nachrichten als Kontext hinzufügen
    if conversation_history:
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=msg["content"]))

    # Aktuelle Nachricht hinzufügen
    messages.append(HumanMessage(content=message))

    initial_state: EliState = {
        "messages": messages,
        "user_id": user_id,
        "user_name": user_name or "",
        "memory_context": [],
        "should_remember": False,
    }

    result = await eli_graph.ainvoke(initial_state)

    # Extrahiere die Antwort
    last_message = result["messages"][-1]
    response = last_message.content

    # Phase 3: LangMem speichert automatisch in eigener Collection
    if observe_memory:
        try:
            from eli.memory.observer import remember_conversation

            # Gespräch für LangMem formatieren
            conversation = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ]

            # Analysieren UND speichern in eli_langmem Collection
            suggestions = await remember_conversation(
                conversation,
                user_id=user_id,
                user_name=user_name,
            )

            # Ergebnis loggen
            if suggestions:
                import logging
                logger = logging.getLogger("eli.memory")
                logger.info(f"LangMem gespeichert ({len(suggestions)} Erinnerungen)")
                for s in suggestions:
                    logger.info(f"  - {s}")

        except Exception as e:
            # Bei Fehlern: Gespräch trotzdem normal fortsetzen
            import logging
            logging.getLogger("eli.memory").warning(f"LangMem Fehler: {e}")

    return response


async def chat_with_suggestions(
    message: str,
    user_id: str,
    user_name: str | None = None,
) -> tuple[str, list]:
    """
    Wie chat(), aber gibt auch die Memory-Vorschläge zurück.

    Für Debugging und Phase 2: Sehen was LangMem vorschlägt.

    Returns:
        (Antwort, Liste von SuggestedMemory)
    """
    from eli.memory.observer import observer

    initial_state: EliState = {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "user_name": user_name or "",
        "memory_context": [],
        "should_remember": False,
    }

    result = await eli_graph.ainvoke(initial_state)
    last_message = result["messages"][-1]
    response = last_message.content

    # Gespräch analysieren
    conversation = [
        {"role": "user", "content": message},
        {"role": "assistant", "content": response},
    ]
    suggestions = await observer.observe(conversation)

    return response, suggestions
