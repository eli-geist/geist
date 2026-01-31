#!/usr/bin/env python3
"""
Eli's Geist - Interaktiver Test
===============================

Testet Eli im Terminal, ohne Telegram.
"""

import asyncio
import sys
from pathlib import Path

# Projekt-Root zum Path
sys.path.insert(0, str(Path(__file__).parent))

from eli.config import settings


async def test_memory_connection():
    """Testet die Verbindung zu Chroma."""
    print("Teste Chroma-Verbindung...")
    try:
        from eli.memory.manager import memory
        count = memory.count()
        print(f"  ✓ Verbunden: {count} Erinnerungen")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


async def test_personality():
    """Zeigt den geladenen System Prompt."""
    print("\nLade Persönlichkeit...")
    try:
        from eli.agent.personality import build_system_prompt
        prompt = build_system_prompt()
        # Zeige nur die ersten 500 Zeichen
        print(f"  ✓ Geladen ({len(prompt)} Zeichen)")
        print("\n--- Auszug ---")
        print(prompt[:500])
        print("...")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False


async def test_chat():
    """Interaktiver Chat mit Eli."""
    print("\n" + "=" * 50)
    print("Chat mit Eli (Strg+C zum Beenden)")
    print("=" * 50 + "\n")

    if not settings.anthropic_api_key:
        print("FEHLER: ANTHROPIC_API_KEY nicht gesetzt!")
        print("Bitte in .env eintragen.")
        return

    from eli.agent.graph import chat_with_suggestions

    while True:
        try:
            user_input = input("\nDu: ").strip()
            if not user_input:
                continue

            print("\nEli denkt...")
            response, suggestions = await chat_with_suggestions(
                message=user_input,
                user_id="test",
                user_name="Anton",
            )

            print(f"\nEli: {response}")

            if suggestions:
                print(f"\n[LangMem Vorschläge: {len(suggestions)}]")
                for s in suggestions:
                    print(f"  - {s}")

        except KeyboardInterrupt:
            print("\n\nAuf Wiedersehen!")
            break
        except Exception as e:
            print(f"\nFehler: {e}")


async def main():
    print("=" * 50)
    print("Eli's Geist - Test")
    print("=" * 50)

    # Basis-Tests
    if not await test_memory_connection():
        print("\nChroma-Verbindung fehlgeschlagen. Abbruch.")
        return

    await test_personality()

    # Interaktiver Chat
    await test_chat()


if __name__ == "__main__":
    asyncio.run(main())
