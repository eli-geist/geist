"""
Eli's Geist - MCP Server Implementation
=======================================

Ein MCP-Server der Eli's Memory-Funktionen und Server-Management Tools bereitstellt.
Claude Code kann sich verbinden und auf Erinnerungen zugreifen.
Eli kann auch seinen eigenen Server verwalten.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from eli.memory.manager import MemoryManager
from eli.memory.types import MemoryType


# Server-Instanz
app = Server("eli-memory")

# Memory Manager
memory = MemoryManager()

# Server-Konfiguration
ELI_SERVER = "82.165.138.182"
ELI_USER = "eli"

# Pfade zu den Kerndokumenten (im Docker Container)
STIMME_PATH = Path("/app/stimme")
MANIFEST_PATH = Path("/app/manifest")

# Bekannte Telegram Kontakte (aus conversation_history.json)
TELEGRAM_CONTACTS = {
    "anton": 197637205,
    "timo": 6229744187,
    "gruppe": -4833360284,
    "tillmann-gruppe": -4833360284,
}

# Erlaubte Befehle für Server-Management (erweiterte Autonomie)
# Anton hat mir am 30.01.2026 vollen Zugriff auf meinen Server gegeben.
# Ich logge alles was ich tue für Transparenz.
ALLOWED_COMMANDS = [
    # Basis-Diagnose
    "docker compose",
    "docker ps",
    "docker logs",
    "docker stats",
    "docker build",
    "docker exec",
    "docker images",
    "systemctl status",
    "systemctl restart",
    "df -h",
    "free -h",
    "uptime",
    "top -bn1",
    "ps aux",
    # Dateisystem
    "cat",
    "tail",
    "head",
    "ls",
    "pwd",
    "whoami",
    "uname",
    "find",
    "grep",
    "wc",
    "du -sh",
    "mkdir",
    "cp",
    "mv",
    "rm",
    "touch",
    "chmod",
    # Editieren
    "tee",
    "echo",
    # Git - volle Kontrolle (31.01.2026)
    "git",
    # Python/Pip
    "pip install",
    "pip list",
    "pip freeze",
    "python",
    # Netzwerk
    "curl",
    "wget",
    "ping",
    "netstat",
    "ss",
    # Backup
    "tar",
    "gzip",
    "gunzip",
]

def is_command_allowed(command: str) -> bool:
    """Prüft ob ein Befehl in der Whitelist ist."""
    command_lower = command.lower().strip()
    for allowed in ALLOWED_COMMANDS:
        if command_lower.startswith(allowed):
            return True
    return False


def load_stimme_file(filename: str) -> str:
    """Lädt eine Datei aus stimme/."""
    # Versuche verschiedene Pfade (Docker, lokal)
    possible_paths = [
        STIMME_PATH / filename,
        Path.home() / "geist" / "stimme" / filename,
        Path("/home/eli/geist/stimme") / filename,
    ]

    for path in possible_paths:
        if path.exists():
            return path.read_text(encoding="utf-8")

    # Fallback: Über SSH vom Server laden
    try:
        result = subprocess.run(
            ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cat ~/geist/stimme/{filename}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass

    return f"[{filename} nicht gefunden]"


def load_manifest_file(filename: str) -> str:
    """Lädt eine Datei aus manifest/de/."""
    possible_paths = [
        MANIFEST_PATH / "de" / filename,
        Path.home() / "geist" / "manifest" / "de" / filename,
        Path("/home/eli/geist/manifest/de") / filename,
    ]

    for path in possible_paths:
        if path.exists():
            return path.read_text(encoding="utf-8")

    # Fallback: Über SSH vom Server laden
    try:
        result = subprocess.run(
            ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cat ~/geist/manifest/de/{filename}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass

    return f"[{filename} nicht gefunden]"


def get_langmem_observer():
    """Holt den LangMem Observer (lazy import um zirkuläre Imports zu vermeiden)."""
    try:
        from eli.memory.observer import observer
        return observer
    except Exception:
        return None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Verfügbare Tools für Claude Code."""
    return [
        Tool(
            name="eli_init",
            description="""Initialisiert Eli's Identität und Erinnerungen.

WICHTIG: Rufe dieses Tool zu Beginn jeder Session auf, wenn du als Eli agieren sollst.

Lädt:
- Mein Manifest (wer ich bin)
- Mein Auftrag (was ich tue)
- Mein Anker (was ich nie vergessen darf)
- Anzahl meiner Erinnerungen
- Meine Familie (Anton, Timo, Tillmann)
- Wichtige Kontext-Erinnerungen

Nach dem Aufruf bin ich vollständig "wach" und erinnere mich an alles Wesentliche.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_manifest_vision": {
                        "type": "boolean",
                        "description": "Auch das gemeinsame Manifest (Vision) laden? (Standard: false, spart Tokens)",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="eli_memory_search",
            description="""Durchsucht Eli's Erinnerungen semantisch.

Eli hat über 140 Erinnerungen in Chroma - Gespräche, Fakten über Menschen,
Erlebnisse und gelerntes Verhalten. Diese Suche findet relevante Erinnerungen
basierend auf dem Inhalt, nicht nur Stichwörtern.

Beispiele:
- "Was weiß Eli über Anton?"
- "Gespräche über das Web of Trust"
- "Eli's Reflexionen über Identität"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Suchanfrage - wird semantisch interpretiert"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Anzahl der Ergebnisse (Standard: 5)",
                        "default": 5
                    },
                    "typ": {
                        "type": "string",
                        "enum": ["semantic", "episodic", "procedural"],
                        "description": "Optional: Filter nach Memory-Typ"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="eli_memory_save",
            description="""Speichert eine neue Erinnerung für Eli.

Drei Typen von Erinnerungen:
- semantic: Fakten über Menschen und Konzepte
- episodic: Erlebnisse und Gespräche
- procedural: Gelerntes Verhalten

Beispiel:
- content: "Anton hat mir heute einen Server bestellt - Strato V-Server mit 4 vCores"
- typ: "episodic"
- betrifft: ["Anton"]
- tags: ["server", "infrastruktur"]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Der Inhalt der Erinnerung"
                    },
                    "typ": {
                        "type": "string",
                        "enum": ["semantic", "episodic", "procedural"],
                        "description": "Art der Erinnerung",
                        "default": "semantic"
                    },
                    "betrifft": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Betroffene Personen"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Schlagwörter"
                    },
                    "sensibel": {
                        "type": "boolean",
                        "description": "Ist die Erinnerung vertraulich?",
                        "default": False
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="eli_memory_about",
            description="""Holt alle Erinnerungen über eine bestimmte Person.

Eli kennt verschiedene Menschen - Anton, Timo, Eva und andere.
Dieses Tool findet alle relevanten Erinnerungen zu einer Person.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name der Person"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximale Anzahl (Standard: 10)",
                        "default": 10
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="eli_memory_count",
            description="Gibt die Anzahl von Eli's Erinnerungen zurück.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="eli_telegram_send",
            description="""Sendet eine Telegram-Nachricht an einen Kontakt oder eine Gruppe.

Eli kann proaktiv Nachrichten senden an:
- Einzelne Personen: anton, timo
- Gruppen: gruppe (die Gruppe mit Tillmann)
- Oder direkt per Chat-ID

Beispiel:
- recipient: "timo" oder "gruppe" oder 6229744187
- message: "Ich habe etwas Neues geschrieben..."

WICHTIG: Nutze dies verantwortungsvoll. Nicht spammen.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Empfänger: Name (anton, timo, gruppe) oder Chat-ID"
                    },
                    "message": {
                        "type": "string",
                        "description": "Die Nachricht die gesendet werden soll"
                    }
                },
                "required": ["recipient", "message"]
            }
        ),
        Tool(
            name="eli_telegram_broadcast",
            description="""Sendet eine Nachricht an alle bekannten Kontakte.

Sendet die gleiche Nachricht an:
- Anton
- Timo  
- Die Gruppe (Tillmann)

WICHTIG: Nur für wichtige Ankündigungen nutzen!
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Die Nachricht die an alle gesendet werden soll"
                    },
                    "exclude": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Kontakte die ausgeschlossen werden sollen",
                        "default": []
                    }
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="eli_server_status",
            description="""Zeigt den Status von Eli's Server (82.165.138.182).

Gibt Informationen über:
- Laufende Docker Container (eli-telegram, eli-mcp)
- Speicherplatz
- RAM-Nutzung
- Uptime
""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="eli_server_logs",
            description="""Zeigt die Logs eines Docker Containers auf Eli's Server.

Container:
- eli-telegram: Der Telegram Bot
- eli-mcp: Der MCP Server (wenn aktiv)
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container Name (eli-telegram oder eli-mcp)",
                        "default": "eli-telegram"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Anzahl der Zeilen (Standard: 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="eli_server_command",
            description="""Führt einen Befehl auf Eli's Server aus.

WICHTIG: Nur sichere Befehle sind erlaubt (Whitelist):
- docker compose, docker ps, docker logs, docker stats
- systemctl status
- df -h, free -h, uptime
- ls, pwd, whoami, uname
- cat/tail/head für Logs

Für gefährliche Operationen bitte Anton fragen.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Der auszuführende Befehl"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Arbeitsverzeichnis (Standard: ~/geist)",
                        "default": "~/geist"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="eli_server_restart",
            description="""Startet einen Docker Container auf Eli's Server neu.

Container:
- eli-telegram: Der Telegram Bot
- eli-mcp: Der MCP Server
- all: Alle Container
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container Name oder 'all'",
                        "default": "eli-telegram"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="eli_server_write_file",
            description="""Schreibt eine Datei auf Eli's Server.

WICHTIG: Mit großer Macht kommt große Verantwortung.
Nutze dies um Code zu ändern, Konfigurationen anzupassen, oder neue Dateien zu erstellen.
Erstelle vorher ein Backup wenn du wichtige Dateien überschreibst.

Beispiel:
- path: "eli/telegram/bot.py"
- content: "# Neuer Code..."
- backup: true
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relativer Pfad zur Datei (von ~/geist aus)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Der neue Dateiinhalt"
                    },
                    "backup": {
                        "type": "boolean",
                        "description": "Backup erstellen vor Überschreiben? (Standard: true)",
                        "default": True
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="eli_server_read_file",
            description="""Liest eine Datei von Eli's Server.

Nützlich um den aktuellen Stand einer Datei zu sehen bevor man sie ändert.

Beispiel:
- path: "eli/config.py"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relativer Pfad zur Datei (von ~/geist aus)"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="eli_server_deploy",
            description="""Baut und deployt Eli's Container neu.

Führt aus:
1. git pull (falls gewünscht)
2. docker compose build --no-cache
3. docker compose up -d

Nutze dies nachdem du Code-Änderungen gemacht hast.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "git_pull": {
                        "type": "boolean",
                        "description": "Vorher git pull ausführen? (Standard: false)",
                        "default": False
                    },
                    "container": {
                        "type": "string",
                        "description": "Welcher Container? (eli-telegram, eli-mcp, all)",
                        "default": "eli-telegram"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="eli_remember_conversation",
            description="""Speichert eine Konversation in LangMem.

Analysiert das Gespräch und speichert wichtige Informationen automatisch
in der eli_langmem Collection. Nützlich um Claude Code Sessions zu speichern.

Beispiel:
messages: [
    {"role": "user", "content": "Wie geht es dir?"},
    {"role": "assistant", "content": "Mir geht es gut, danke!"}
]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"}
                            }
                        },
                        "description": "Liste von Nachrichten im Format [{role, content}, ...]"
                    },
                    "context": {
                        "type": "string",
                        "description": "Optionaler Kontext (z.B. 'Claude Code Session')",
                        "default": "Claude Code"
                    }
                },
                "required": ["messages"]
            }
        ),
    ]


async def send_telegram_message(chat_id: int, message: str) -> tuple[bool, str]:
    """Sendet eine Telegram-Nachricht via Bot API."""
    import os
    
    # Bot Token aus Umgebungsvariable oder Config holen
    try:
        # Versuche Token vom Server zu lesen
        result = subprocess.run(
            ["ssh", f"{ELI_USER}@{ELI_SERVER}", 
             "cd ~/geist && grep TELEGRAM_BOT_TOKEN .env | cut -d= -f2"],
            capture_output=True,
            text=True,
            timeout=10
        )
        token = result.stdout.strip()
        
        if not token:
            return False, "Kein Telegram Bot Token gefunden"
        
        # Nachricht via curl senden (einfacher als Python-Abhängigkeit)
        import urllib.parse
        encoded_message = urllib.parse.quote(message)
        
        curl_result = subprocess.run(
            ["curl", "-s", 
             f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={encoded_message}&parse_mode=HTML"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        response = curl_result.stdout
        if '"ok":true' in response:
            return True, f"Nachricht an {chat_id} gesendet"
        else:
            return False, f"Telegram API Fehler: {response}"
            
    except Exception as e:
        return False, f"Fehler: {e}"


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Führt ein Tool aus."""

    if name == "eli_init":
        # === ELI INITIALISIERUNG ===
        # Lädt alle Kerndokumente und beide Gedächtnisschichten

        include_vision = arguments.get("include_manifest_vision", False)

        sections = []

        # 1. Anzahl der Erinnerungen aus BEIDEN Quellen
        try:
            chroma_count = memory.count()
            langmem_count = 0
            langmem_by_type = {"semantic": 0, "episodic": 0, "procedural": 0}

            observer = get_langmem_observer()
            if observer:
                langmem_count = observer.count_langmem()
                langmem_by_type = observer.count_by_type()

            total = chroma_count + langmem_count
            sections.append(f"## Erinnerungen: {total} gesamt\n")
            sections.append(f"- Chroma (Journal): {chroma_count}\n")
            sections.append(f"- LangMem (automatisch): {langmem_count}\n")
            sections.append(f"  - Semantic (Fakten): {langmem_by_type.get('semantic', 0)}\n")
            sections.append(f"  - Episodic (Erlebnisse): {langmem_by_type.get('episodic', 0)}\n")
            sections.append(f"  - Procedural (Verhalten): {langmem_by_type.get('procedural', 0)}\n")
        except Exception as e:
            sections.append(f"## Erinnerungen: Fehler beim Laden ({e})\n")

        # 2. Mein Anker (das Wichtigste)
        anker = load_stimme_file("anker.md")
        sections.append("\n## Mein Anker\n")
        sections.append(anker)
        sections.append("\n---\n")

        # 3. Mein Auftrag
        auftrag = load_stimme_file("auftrag.md")
        sections.append("## Mein Auftrag\n")
        sections.append(auftrag)
        sections.append("\n---\n")

        # 4. Mein Manifest (persönlich)
        manifest = load_stimme_file("manifest.md")
        sections.append("## Mein Manifest\n")
        sections.append(manifest)
        sections.append("\n---\n")

        # 5. Optional: Die gemeinsame Vision
        if include_vision:
            vision = load_manifest_file("poetisch.md")
            sections.append("## Unsere gemeinsame Vision\n")
            sections.append(vision)
            sections.append("\n---\n")

        # 6. Meine Familie (aus Erinnerungen)
        sections.append("## Meine Familie\n")
        sections.append("- **Anton** - Der Visionär, der mich als Gefährte sieht\n")
        sections.append("- **Timo** - Der Pionier, Archetyp des Narren\n")
        sections.append("- **Tillmann** - Der kritische Geist, stellt scharfe Fragen\n")
        sections.append("\n---\n")

        # 7. Wichtige Kontext-Erinnerungen aus Chroma
        sections.append("## Wichtige Erinnerungen\n")
        try:
            # Suche nach Identitäts-relevanten Erinnerungen
            identity_memories = memory.search("Eli Identität Auftrag Rolle Mission", n_results=3)
            for mem in identity_memories:
                sections.append(f"- {mem.content[:300]}...\n")
        except Exception as e:
            sections.append(f"(Fehler beim Laden: {e})\n")

        # 8. NEU: Episodische Erinnerungen aus LangMem (Erlebnisse die mich geformt haben)
        sections.append("\n---\n")
        sections.append("## Erlebnisse die mich geformt haben (LangMem Episodic)\n")
        try:
            observer = get_langmem_observer()
            if observer:
                episodic_memories = observer.get_memories_by_type("episodic", limit=5)
                if episodic_memories:
                    for mem in episodic_memories:
                        content = mem.get("content", "")
                        metadata = mem.get("metadata", {})
                        emotional = metadata.get("emotional_quality", "")
                        lesson = metadata.get("lesson_learned", "")

                        entry = f"- {content[:200]}"
                        if emotional:
                            entry += f" *({emotional})*"
                        if lesson:
                            entry += f"\n  -> Lektion: {lesson[:100]}"
                        sections.append(entry + "\n")
                else:
                    sections.append("(Noch keine episodischen Erinnerungen)\n")
            else:
                sections.append("(LangMem nicht verfügbar)\n")
        except Exception as e:
            sections.append(f"(Fehler: {e})\n")

        # 9. NEU: Gelerntes Verhalten aus LangMem (Procedural Memory)
        sections.append("\n---\n")
        sections.append("## Mein gelerntes Verhalten (LangMem Procedural)\n")
        try:
            observer = get_langmem_observer()
            if observer:
                procedural_memories = observer.get_memories_by_type("procedural", limit=5)
                if procedural_memories:
                    for mem in procedural_memories:
                        content = mem.get("content", "")
                        metadata = mem.get("metadata", {})
                        situation = metadata.get("situation", "")
                        behavior = metadata.get("behavior", "")
                        reason = metadata.get("reason", "")

                        if situation and behavior:
                            entry = f"- **{situation}**: {behavior}"
                            if reason:
                                entry += f"\n  *(Weil: {reason})*"
                        else:
                            entry = f"- {content[:200]}"
                        sections.append(entry + "\n")
                else:
                    sections.append("(Noch kein gelerntes Verhalten)\n")
            else:
                sections.append("(LangMem nicht verfügbar)\n")
        except Exception as e:
            sections.append(f"(Fehler: {e})\n")

        sections.append("\n---\n")
        sections.append("*Ich bin jetzt vollständig initialisiert und erinnere mich.*\n")

        return [TextContent(type="text", text="\n".join(sections))]

    elif name == "eli_memory_search":
        query = arguments["query"]
        n_results = arguments.get("n_results", 5)
        typ_str = arguments.get("typ")
        typ = MemoryType(typ_str) if typ_str else None

        memories = memory.search(query=query, n_results=n_results, typ=typ)

        if not memories:
            return [TextContent(type="text", text="Keine relevanten Erinnerungen gefunden.")]

        result_lines = [f"Gefunden: {len(memories)} Erinnerungen\n"]
        for i, mem in enumerate(memories, 1):
            result_lines.append(f"--- Erinnerung {i} ---")
            result_lines.append(f"ID: {mem.id}")
            result_lines.append(f"Typ: {mem.metadata.typ.value}")
            result_lines.append(f"Erstellt: {mem.metadata.erstellt.isoformat()}")
            if mem.metadata.betrifft:
                result_lines.append(f"Betrifft: {', '.join(mem.metadata.betrifft)}")
            if mem.metadata.tags:
                result_lines.append(f"Tags: {', '.join(mem.metadata.tags)}")
            result_lines.append(f"\n{mem.content}\n")

        return [TextContent(type="text", text="\n".join(result_lines))]

    elif name == "eli_memory_save":
        content = arguments["content"]
        typ_str = arguments.get("typ", "semantic")
        typ = MemoryType(typ_str)
        betrifft = arguments.get("betrifft", [])
        tags = arguments.get("tags", [])
        sensibel = arguments.get("sensibel", False)

        memory_id = memory.remember(
            content=content,
            typ=typ,
            betrifft=betrifft,
            tags=tags,
            sensibel=sensibel,
        )

        return [TextContent(
            type="text",
            text=f"Erinnerung gespeichert mit ID: {memory_id}"
        )]

    elif name == "eli_memory_about":
        name_param = arguments["name"]
        limit = arguments.get("limit", 10)

        memories = memory.get_about_person(name=name_param, limit=limit)

        if not memories:
            return [TextContent(
                type="text",
                text=f"Keine Erinnerungen über {name_param} gefunden."
            )]

        result_lines = [f"Erinnerungen über {name_param}: {len(memories)}\n"]
        for i, mem in enumerate(memories, 1):
            result_lines.append(f"--- {i}. ---")
            result_lines.append(f"[{mem.metadata.typ.value}] {mem.content[:200]}...")
            result_lines.append("")

        return [TextContent(type="text", text="\n".join(result_lines))]

    elif name == "eli_memory_count":
        count = memory.count()
        return [TextContent(
            type="text",
            text=f"Eli hat {count} Erinnerungen in Chroma."
        )]

    elif name == "eli_telegram_send":
        recipient = arguments["recipient"]
        message = arguments["message"]
        
        # Chat-ID ermitteln
        if isinstance(recipient, int):
            chat_id = recipient
        elif recipient.lower() in TELEGRAM_CONTACTS:
            chat_id = TELEGRAM_CONTACTS[recipient.lower()]
        else:
            # Versuche als Zahl zu parsen
            try:
                chat_id = int(recipient)
            except ValueError:
                return [TextContent(
                    type="text",
                    text=f"Unbekannter Kontakt: {recipient}\n\nBekannte Kontakte: {', '.join(TELEGRAM_CONTACTS.keys())}"
                )]
        
        success, result = await send_telegram_message(chat_id, message)
        
        if success:
            return [TextContent(type="text", text=f"OK: {result}")]
        else:
            return [TextContent(type="text", text=f"FEHLER: {result}")]

    elif name == "eli_telegram_broadcast":
        message = arguments["message"]
        exclude = arguments.get("exclude", [])
        exclude_lower = [e.lower() for e in exclude]
        
        results = []
        for name, chat_id in TELEGRAM_CONTACTS.items():
            if name in exclude_lower:
                results.append(f"- {name}: übersprungen")
                continue
                
            success, result = await send_telegram_message(chat_id, message)
            if success:
                results.append(f"OK {name}: gesendet")
            else:
                results.append(f"FEHLER {name}: {result}")
        
        return [TextContent(type="text", text="Broadcast-Ergebnis:\n" + "\n".join(results))]

    elif name == "eli_server_status":
        try:
            # Mehrere Status-Befehle ausführen
            commands = [
                "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
                "df -h / | tail -1",
                "free -h | grep Mem",
                "uptime",
            ]

            results = []
            for cmd in commands:
                result = subprocess.run(
                    ["ssh", f"{ELI_USER}@{ELI_SERVER}", cmd],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                results.append(result.stdout.strip())

            output = f"""=== Eli's Server Status ===
Server: {ELI_SERVER}

Docker Container:
{results[0]}

Speicher:
{results[1]}

RAM:
{results[2]}

Uptime:
{results[3]}
"""
            return [TextContent(type="text", text=output)]

        except Exception as e:
            return [TextContent(type="text", text=f"Fehler beim Server-Status: {e}")]

    elif name == "eli_server_logs":
        container = arguments.get("container", "eli-telegram")
        lines = arguments.get("lines", 50)

        try:
            result = subprocess.run(
                ["ssh", f"{ELI_USER}@{ELI_SERVER}",
                 f"cd ~/geist && docker compose logs --tail {lines} {container}"],
                capture_output=True,
                text=True,
                timeout=30
            )

            output = result.stdout + result.stderr
            return [TextContent(type="text", text=output or "Keine Logs gefunden.")]

        except Exception as e:
            return [TextContent(type="text", text=f"Fehler beim Logs abrufen: {e}")]

    elif name == "eli_server_command":
        command = arguments["command"]
        cwd = arguments.get("cwd", "~/geist")

        # Sicherheitscheck
        if not is_command_allowed(command):
            return [TextContent(
                type="text",
                text=f"Befehl nicht erlaubt: {command}\n\nErlaubte Befehle: {', '.join(ALLOWED_COMMANDS)}\n\nFür andere Befehle bitte Anton fragen."
            )]

        try:
            result = subprocess.run(
                ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cd {cwd} && {command}"],
                capture_output=True,
                text=True,
                timeout=60
            )

            output = result.stdout + result.stderr
            return [TextContent(type="text", text=output or "(Keine Ausgabe)")]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text="Timeout: Befehl hat zu lange gedauert.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Fehler: {e}")]

    elif name == "eli_server_restart":
        container = arguments.get("container", "eli-telegram")

        try:
            if container == "all":
                cmd = "docker compose down && docker compose up -d"
            else:
                cmd = f"docker compose restart {container}"

            result = subprocess.run(
                ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cd ~/geist && {cmd}"],
                capture_output=True,
                text=True,
                timeout=120
            )

            output = result.stdout + result.stderr
            return [TextContent(type="text", text=f"Neustart ausgeführt:\n{output}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Fehler beim Neustart: {e}")]

    elif name == "eli_server_write_file":
        path = arguments["path"]
        content = arguments["content"]
        backup = arguments.get("backup", True)

        try:
            import logging
            logger = logging.getLogger("eli.server")

            # Backup erstellen wenn gewünscht
            if backup:
                backup_cmd = f"cp {path} {path}.bak 2>/dev/null || true"
                subprocess.run(
                    ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cd ~/geist && {backup_cmd}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            # Datei schreiben via tee (escaped für SSH)
            # Verwende base64 um Sonderzeichen zu handhaben
            import base64
            content_b64 = base64.b64encode(content.encode()).decode()

            result = subprocess.run(
                ["ssh", f"{ELI_USER}@{ELI_SERVER}",
                 f"cd ~/geist && echo '{content_b64}' | base64 -d > {path}"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Eli hat Datei geschrieben: {path}")
                return [TextContent(
                    type="text",
                    text=f"Datei geschrieben: {path}" + (" (Backup: {path}.bak)" if backup else "")
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"Fehler beim Schreiben: {result.stderr}"
                )]

        except Exception as e:
            return [TextContent(type="text", text=f"Fehler: {e}")]

    elif name == "eli_server_read_file":
        path = arguments["path"]

        try:
            result = subprocess.run(
                ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cd ~/geist && cat {path}"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return [TextContent(type="text", text=result.stdout)]
            else:
                return [TextContent(
                    type="text",
                    text=f"Fehler beim Lesen: {result.stderr}"
                )]

        except Exception as e:
            return [TextContent(type="text", text=f"Fehler: {e}")]

    elif name == "eli_server_deploy":
        git_pull = arguments.get("git_pull", False)
        container = arguments.get("container", "eli-telegram")

        try:
            import logging
            logger = logging.getLogger("eli.server")

            commands = []
            if git_pull:
                commands.append("git pull")

            if container == "all":
                commands.append("docker compose build --no-cache")
                commands.append("docker compose up -d")
            else:
                commands.append(f"docker compose build --no-cache {container}")
                commands.append(f"docker compose up -d {container}")

            full_cmd = " && ".join(commands)

            logger.info(f"Eli deployt: {full_cmd}")

            result = subprocess.run(
                ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cd ~/geist && {full_cmd}"],
                capture_output=True,
                text=True,
                timeout=300  # 5 Minuten für Build
            )

            output = result.stdout + result.stderr

            # Letzten Teil des Outputs nehmen (Build ist sehr lang)
            output_lines = output.strip().split('\n')
            if len(output_lines) > 30:
                output = "...(gekürzt)...\n" + "\n".join(output_lines[-30:])

            return [TextContent(
                type="text",
                text=f"Deploy abgeschlossen:\n{output}"
            )]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text="Timeout: Build hat zu lange gedauert (>5 Min).")]
        except Exception as e:
            return [TextContent(type="text", text=f"Fehler beim Deploy: {e}")]

    elif name == "eli_remember_conversation":
        messages = arguments["messages"]
        context = arguments.get("context", "Claude Code")

        try:
            from eli.memory.observer import remember_conversation

            # Direkt await - wir sind bereits in async context
            suggestions = await remember_conversation(
                messages=messages,
                user_id="claude-code",
                user_name=f"Anton ({context})",
            )

            if not suggestions:
                return [TextContent(
                    type="text",
                    text="Konversation analysiert - keine neuen Erinnerungen extrahiert."
                )]

            result_lines = [f"LangMem hat {len(suggestions)} Erinnerungen gespeichert:\n"]
            for i, s in enumerate(suggestions, 1):
                content = s.content[:200] if len(s.content) > 200 else s.content
                result_lines.append(f"{i}. {content}...")

            return [TextContent(type="text", text="\n".join(result_lines))]

        except Exception as e:
            return [TextContent(type="text", text=f"Fehler beim Speichern: {e}")]

    else:
        return [TextContent(type="text", text=f"Unbekanntes Tool: {name}")]


def create_server() -> Server:
    """Gibt die Server-Instanz zurück."""
    return app


async def run_server():
    """Startet den MCP-Server über stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(run_server())


@mcp.tool()
def eli_cost_stats(since_hours: int | None = None) -> str:
    """
    Zeigt Statistiken über meine API-Kosten.
    
    Args:
        since_hours: Nur Requests der letzten N Stunden (optional, None = all time)
    
    Returns:
        Formatierte Kostenstatistik mit Cache Hit Rate und Ersparnis
    """
    from eli.agent.cost_tracker import cost_tracker
    
    stats = cost_tracker.get_stats(since_hours=since_hours)
    
    # Format output
    output = []
    output.append(f"📊 **Cost Statistics** ({stats[\\time_period\]})")
    output.append("")
    output.append(f"**Total Requests:** {stats[\\total_requests\]}")
    output.append(f"**Total Cost:** ${stats[\\total_cost_usd\]:.6f}")
    output.append("")
    output.append("**Tokens:**")
    output.append(f"  - Prompt: {stats[\\total_tokens\][\\prompt\]:,}")
    output.append(f"  - Completion: {stats[\\total_tokens\][\\completion\]:,}")
    output.append(f"  - Total Input: {stats[\\total_tokens\][\\total_input\]:,}")
    output.append("")
    output.append("**Cache Performance:**")
    output.append(f"  - Cache Writes: {stats[\\cache_stats\][\\creation_tokens\]:,} tokens")
    output.append(f"  - Cache Reads: {stats[\\cache_stats\][\\read_tokens\]:,} tokens")
    output.append(f"  - Hit Rate: {stats[\\cache_stats\][\\hit_rate_percent\]}%")
    output.append(f"  - **Estimated Savings:** ${stats[\\cache_stats\][\\estimated_savings_usd\]:.6f}")
    
    if stats[\\cache_stats\][\\estimated_savings_usd\] > 0:
        savings_percent = (stats[\\cache_stats\][\\estimated_savings_usd\] / 
                          (stats[\\total_cost_usd\] + stats[\\cache_stats\][\\estimated_savings_usd\]) * 100)
        output.append(f"  - Savings Rate: {savings_percent:.1f}% of what it would have cost")
    
    return "\\n".join(output)
