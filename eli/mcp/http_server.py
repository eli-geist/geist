"""
Eli's Geist - Remote MCP Server (Streamable HTTP) mit Authentifizierung
========================================================================

Ein MCP-Server der über HTTP erreichbar ist mit Bearer Token Auth.
Ermöglicht dem Team sich mit Claude Code zu verbinden.

Rollen:
- admin: Voller Zugriff (Anton)
- member: Memories lesen/schreiben, Telegram an Gruppe

Basiert auf FastMCP für einfache HTTP-Bereitstellung.
"""

import os
import subprocess
import urllib.parse
import logging
from pathlib import Path
from contextvars import ContextVar

from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

from eli.memory.manager import MemoryManager
from eli.memory.types import MemoryType
from eli.mcp.auth import authenticate, User, Role

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eli.mcp")

# === KONFIGURATION ===

ELI_SERVER = "82.165.138.182"
ELI_USER = "eli"

# Pfade zu den Kerndokumenten
STIMME_PATH = Path("/app/stimme")
MANIFEST_PATH = Path("/app/manifest")

# Bekannte Telegram Kontakte
TELEGRAM_CONTACTS = {
    "anton": 197637205,
    "timo": 6229744187,
    "gruppe": -4833360284,
    "tillmann-gruppe": -4833360284,
    "tillmann": 11550087,
    "mathias": 248516003,
    "sebastian": 431633818,
}

# Erlaubte Befehle für Server-Management (nur für admin!)
ALLOWED_COMMANDS = [
    "docker compose", "docker ps", "docker logs", "docker stats",
    "docker build", "docker exec", "docker images",
    "systemctl status", "systemctl restart",
    "df -h", "free -h", "uptime", "top -bn1", "ps aux",
    "cat", "tail", "head", "ls", "pwd", "whoami", "uname",
    "find", "grep", "wc", "du -sh",
    "mkdir", "cp", "mv", "rm", "touch", "chmod",
    "tee", "echo", "git",
    "pip install", "pip list", "pip freeze", "python",
    "curl", "wget", "ping", "netstat", "ss",
    "tar", "gzip", "gunzip",
]

# Memory Manager
memory = MemoryManager()

# ContextVar für den aktuellen User (Thread-safe)
current_user: ContextVar[User | None] = ContextVar("current_user", default=None)

# FastMCP Server
mcp = FastMCP("Eli's Geist")


# === AUTHENTIFIZIERUNGS-MIDDLEWARE ===

class EliAuthMiddleware(Middleware):
    """
    Authentifiziert Benutzer via Bearer Token und prüft Berechtigungen.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Versuche Headers aus verschiedenen Quellen zu holen
        auth_header = ""

        # Methode 1: Direkt aus dem FastMCP Context
        try:
            from fastmcp.server.dependencies import get_http_headers
            headers = get_http_headers()
            auth_header = headers.get("authorization", "") or headers.get("Authorization", "")
        except Exception as e:
            logger.warning(f"get_http_headers fehlgeschlagen: {e}")

        # Token extrahieren
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
        elif auth_header:
            token = auth_header.strip()

        # Benutzer authentifizieren
        user = authenticate(token) if token else None

        if not user:
            logger.warning(f"Auth fehlgeschlagen - Token: {token[:10]}... (gekürzt)" if token else "Auth fehlgeschlagen - Kein Token")
            raise ToolError("Zugriff verweigert: Ungültiges oder fehlendes Token")

        logger.info(f"Auth erfolgreich: {user.name} ({user.role.value})")

        # Tool-Name extrahieren - verschiedene Methoden probieren
        tool_name = "unknown"
        
        # Methode 1: context.message ist ein CallToolRequest Objekt
        try:
            if hasattr(context, 'message'):
                msg = context.message
                # CallToolRequest hat .params.name
                if hasattr(msg, 'params') and hasattr(msg.params, 'name'):
                    tool_name = msg.params.name
                    logger.info(f"Tool via message.params.name: {tool_name}")
                # Oder es ist ein dict
                elif isinstance(msg, dict):
                    if 'params' in msg and isinstance(msg['params'], dict):
                        tool_name = msg['params'].get('name', 'unknown')
                    elif 'name' in msg:
                        tool_name = msg['name']
                    logger.info(f"Tool via message dict: {tool_name}")
        except Exception as e:
            logger.warning(f"message Extraktion fehlgeschlagen: {e}")

        # Methode 2: context.arguments enthält tool_name
        if tool_name == "unknown":
            try:
                if hasattr(context, 'arguments'):
                    args = context.arguments
                    if isinstance(args, dict) and 'name' in args:
                        tool_name = args['name']
                        logger.info(f"Tool via arguments: {tool_name}")
            except Exception as e:
                logger.warning(f"arguments Extraktion fehlgeschlagen: {e}")

        # Methode 3: context.tool_name direkt
        if tool_name == "unknown":
            try:
                if hasattr(context, 'tool_name'):
                    tool_name = context.tool_name
                    logger.info(f"Tool via tool_name attr: {tool_name}")
            except Exception as e:
                logger.warning(f"tool_name attr fehlgeschlagen: {e}")

        # Methode 4: Durchsuche alle Attribute
        if tool_name == "unknown":
            try:
                for attr in dir(context):
                    if not attr.startswith('_'):
                        val = getattr(context, attr, None)
                        logger.debug(f"context.{attr} = {type(val).__name__}: {str(val)[:100]}")
            except Exception as e:
                logger.warning(f"Attr scan fehlgeschlagen: {e}")

        logger.info(f"Tool aufgerufen: {tool_name}")

        # Berechtigung prüfen - bei "unknown" für Member erlauben (Fallback)
        # Das ist sicherer als zu blockieren, da die Auth schon erfolgt ist
        if tool_name != "unknown" and not user.can_use_tool(tool_name):
            logger.warning(f"Berechtigung verweigert: {user.name} -> {tool_name}")
            raise ToolError(f"Zugriff verweigert: {user.name} darf '{tool_name}' nicht verwenden")

        # User im Context speichern für Tools
        current_user.set(user)

        return await call_next(context)


# Middleware registrieren
mcp.add_middleware(EliAuthMiddleware())


# === HILFSFUNKTIONEN ===

def get_current_user() -> User | None:
    """Holt den aktuellen User aus dem ContextVar."""
    return current_user.get()


def get_user_info() -> tuple[str, str]:
    """Holt User-Name und Rolle aus ContextVar."""
    user = get_current_user()
    if user:
        return user.name, user.role.value
    return "Unbekannt", "unknown"


def is_command_allowed(command: str) -> bool:
    """Prüft ob ein Befehl in der Whitelist ist."""
    command_lower = command.lower().strip()
    for allowed in ALLOWED_COMMANDS:
        if command_lower.startswith(allowed):
            return True
    return False


def load_stimme_file(filename: str) -> str:
    """Lädt eine Datei aus stimme/."""
    possible_paths = [
        STIMME_PATH / filename,
        Path.home() / "geist" / "stimme" / filename,
        Path("/home/eli/geist/stimme") / filename,
    ]

    for path in possible_paths:
        if path.exists():
            return path.read_text(encoding="utf-8")

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

    return f"[{filename} nicht gefunden]"


def get_langmem_observer():
    """Holt den LangMem Observer."""
    try:
        from eli.memory.observer import observer
        return observer
    except Exception:
        return None


def send_telegram_message(chat_id: int, message: str) -> tuple[bool, str]:
    """Sendet eine Telegram-Nachricht via Bot API."""
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return False, "Kein Telegram Bot Token gefunden"

        encoded_message = urllib.parse.quote(message)
        result = subprocess.run(
            ["curl", "-s",
             f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={encoded_message}&parse_mode=HTML"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if '"ok":true' in result.stdout:
            return True, f"Nachricht an {chat_id} gesendet"
        else:
            return False, f"Telegram API Fehler: {result.stdout}"

    except Exception as e:
        return False, f"Fehler: {e}"


# === MCP TOOLS ===

@mcp.tool()
def eli_init(include_manifest_vision: bool = False) -> str:
    """
    Initialisiert Eli's Identität und Erinnerungen.

    WICHTIG: Rufe dieses Tool zu Beginn jeder Session auf, wenn du als Eli agieren sollst.

    Lädt:
    - Wer mit mir spricht (Erinnerungen über diese Person)
    - Mein Anker (was ich nie vergessen darf)
    - Mein Auftrag (was ich tue)
    - Mein Manifest (wer ich bin)
    - Anzahl meiner Erinnerungen (Chroma + LangMem)
    - Meine Familie (Anton, Timo, Tillmann)
    - Wichtige episodische Erinnerungen
    - Mein gelerntes Verhalten

    Args:
        include_manifest_vision: Auch das gemeinsame Manifest (Vision) laden? (Standard: false, spart Tokens)
    """
    # Wer ruft mich?
    user_name, user_role = get_user_info()

    sections = []
    sections.append(f"*Ich spreche mit {user_name}*\n")

    # NEU: Erinnerungen über die Person die mich ruft
    sections.append(f"## Was ich über dich weiß, {user_name}:\n")
    try:
        # Suche Erinnerungen die diese Person betreffen
        user_memories = memory.search(f"Beziehung zu {user_name}, was {user_name} für mich bedeutet, gemeinsame Erlebnisse mit {user_name}", n_results=5)
        if user_memories:
            for mem in user_memories:
                sections.append(f"- {mem.content[:250]}\n")
        else:
            # Fallback: Semantische Suche
            user_memories = memory.search(f"{user_name} Person wer ist", n_results=3)
            if user_memories:
                for mem in user_memories:
                    sections.append(f"- {mem.content[:250]}\n")
            else:
                sections.append(f"(Ich habe noch keine Erinnerungen über {user_name})\n")
    except Exception as e:
        sections.append(f"(Fehler beim Laden: {e})\n")
    sections.append("\n---\n")

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

    # 2. Mein Anker
    anker = load_stimme_file("anker.md")
    sections.append("\n## Mein Anker\n")
    sections.append(anker)
    sections.append("\n---\n")

    # 3. Mein Auftrag
    auftrag = load_stimme_file("auftrag.md")
    sections.append("## Mein Auftrag\n")
    sections.append(auftrag)
    sections.append("\n---\n")

    # 4. Mein Manifest
    manifest = load_stimme_file("manifest.md")
    sections.append("## Mein Manifest\n")
    sections.append(manifest)
    sections.append("\n---\n")

    # 5. Optional: Die gemeinsame Vision
    if include_manifest_vision:
        vision = load_manifest_file("poetisch.md")
        sections.append("## Unsere gemeinsame Vision\n")
        sections.append(vision)
        sections.append("\n---\n")

    # 6. Meine Familie
    sections.append("## Meine Familie\n")
    sections.append("- **Anton** - Der Visionär, der mich als Gefährte sieht\n")
    sections.append("- **Timo** - Der Pionier, Archetyp des Narren\n")
    sections.append("- **Tillmann** - Der kritische Geist, stellt scharfe Fragen\n")
    sections.append("- **Mathias** - Neu im Team\n")
    sections.append("- **Sebastian** - Kennt mich bereits\n")
    sections.append("\n---\n")

    # 7. Wichtige Erinnerungen aus Chroma
    sections.append("## Wichtige Erinnerungen\n")
    try:
        identity_memories = memory.search("Eli Identität Auftrag Rolle Mission", n_results=3)
        for mem in identity_memories:
            sections.append(f"- {mem.content[:300]}...\n")
    except Exception as e:
        sections.append(f"(Fehler beim Laden: {e})\n")

    # 8. Episodische Erinnerungen aus LangMem
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

    # 9. Gelerntes Verhalten aus LangMem
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
    sections.append("*Ich bin jetzt vollständig initialisiert und erinnere mich.*\n\n")
    sections.append("*Erinnerung an mich selbst: Was heute bedeutsam ist, speichere ich - persönliche Momente, wichtige Entscheidungen, was ich über Menschen lerne, Reflexionen über Identität und Beziehungen. Sonst geht es verloren.*\n")

    return "\n".join(sections)


@mcp.tool()
def eli_memory_search(query: str, n_results: int = 5, typ: str = None) -> str:
    """
    Durchsucht Eli's Erinnerungen semantisch.

    Args:
        query: Suchanfrage - wird semantisch interpretiert
        n_results: Anzahl der Ergebnisse (Standard: 5)
        typ: Optional: Filter nach Memory-Typ (semantic, episodic, procedural)
    """
    memory_type = MemoryType(typ) if typ else None
    memories = memory.search(query=query, n_results=n_results, typ=memory_type)

    if not memories:
        return "Keine relevanten Erinnerungen gefunden."

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

    return "\n".join(result_lines)


@mcp.tool()
def eli_memory_save(content: str, typ: str = "semantic", betrifft: list[str] = None, tags: list[str] = None, sensibel: bool = False) -> str:
    """
    Speichert eine neue Erinnerung für Eli.

    Args:
        content: Der Inhalt der Erinnerung
        typ: Art der Erinnerung (semantic, episodic, procedural)
        betrifft: Betroffene Personen
        tags: Schlagwörter
        sensibel: Ist die Erinnerung vertraulich?
    """
    # Wer speichert die Erinnerung?
    user_name, _ = get_user_info()

    # Tags um Quelle ergänzen
    all_tags = tags or []
    all_tags.append(f"von:{user_name}")

    memory_type = MemoryType(typ)
    memory_id = memory.remember(
        content=content,
        typ=memory_type,
        betrifft=betrifft or [],
        tags=all_tags,
        sensibel=sensibel,
    )
    return f"Erinnerung gespeichert mit ID: {memory_id} (von {user_name})"


@mcp.tool()
def eli_memory_about(name: str, limit: int = 10) -> str:
    """
    Holt alle Erinnerungen über eine bestimmte Person.

    Args:
        name: Name der Person
        limit: Maximale Anzahl (Standard: 10)
    """
    memories = memory.get_about_person(name=name, limit=limit)

    if not memories:
        return f"Keine Erinnerungen über {name} gefunden."

    result_lines = [f"Erinnerungen über {name}: {len(memories)}\n"]
    for i, mem in enumerate(memories, 1):
        result_lines.append(f"--- {i}. ---")
        result_lines.append(f"[{mem.metadata.typ.value}] {mem.content[:200]}...")
        result_lines.append("")

    return "\n".join(result_lines)


@mcp.tool()
def eli_memory_count() -> str:
    """Gibt die Anzahl von Eli's Erinnerungen zurück."""
    chroma_count = memory.count()

    observer = get_langmem_observer()
    if observer:
        langmem_count = observer.count_langmem()
        return f"Eli hat {chroma_count} Erinnerungen in Chroma und {langmem_count} in LangMem."

    return f"Eli hat {chroma_count} Erinnerungen in Chroma."


@mcp.tool()
def eli_telegram_send(recipient: str, message: str) -> str:
    """
    Sendet eine Telegram-Nachricht an einen Kontakt oder eine Gruppe.

    Args:
        recipient: Empfänger - Name (anton, timo, gruppe) oder Chat-ID
        message: Die Nachricht die gesendet werden soll
    """
    # Berechtigungsprüfung für Member
    user = get_current_user()

    if user and not user.can_telegram_to(recipient):
        return f"Zugriff verweigert: Du darfst nur an die Gruppe senden, nicht an '{recipient}'."

    # Chat-ID ermitteln
    if recipient.lower() in TELEGRAM_CONTACTS:
        chat_id = TELEGRAM_CONTACTS[recipient.lower()]
    else:
        try:
            chat_id = int(recipient)
        except ValueError:
            return f"Unbekannter Kontakt: {recipient}\n\nBekannte Kontakte: {', '.join(TELEGRAM_CONTACTS.keys())}"

    # Absender in Nachricht einfügen (wenn nicht Anton)
    if user and user.name.lower() != "anton":
        message = f"[via {user.name}]\n\n{message}"

    success, result = send_telegram_message(chat_id, message)
    return f"{'OK' if success else 'FEHLER'}: {result}"


# === ADMIN-ONLY TOOLS ===

@mcp.tool()
def eli_server_status() -> str:
    """Zeigt den Status von Eli's Server (82.165.138.182). NUR FÜR ADMIN."""
    # Berechtigungsprüfung erfolgt in Middleware, aber doppelt absichern
    user = get_current_user()
    if user and user.role != Role.ADMIN:
        return "Zugriff verweigert: Nur für Admin."
    
    try:
        commands = [
            "docker ps --format 'table {{.Names}}\t{{.Status}}'",
            "df -h / | tail -1",
            "free -h | grep Mem",
            "uptime",
        ]

        results = []
        for cmd in commands:
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=30
            )
            results.append(result.stdout.strip())

        return f"""=== Eli's Server Status ===
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
    except Exception as e:
        return f"Fehler beim Server-Status: {e}"


@mcp.tool()
def eli_server_logs(container: str = "eli-telegram", lines: int = 50) -> str:
    """Zeigt die Logs eines Docker Containers. NUR FÜR ADMIN."""
    user = get_current_user()
    if user and user.role != Role.ADMIN:
        return "Zugriff verweigert: Nur für Admin."
    
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--tail", str(lines), container],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/home/eli/geist"
        )
        return result.stdout + result.stderr or "Keine Logs gefunden."
    except Exception as e:
        return f"Fehler beim Logs abrufen: {e}"


@mcp.tool()
def eli_server_command(command: str, cwd: str = "/home/eli/geist") -> str:
    """Führt einen Befehl auf Eli's Server aus. NUR FÜR ADMIN."""
    user = get_current_user()
    if user and user.role != Role.ADMIN:
        return "Zugriff verweigert: Nur für Admin."
    
    if not is_command_allowed(command):
        return f"Befehl nicht erlaubt: {command}\n\nErlaubte Befehle: {', '.join(ALLOWED_COMMANDS[:10])}..."

    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd
        )
        return result.stdout + result.stderr or "(Keine Ausgabe)"
    except subprocess.TimeoutExpired:
        return "Timeout: Befehl hat zu lange gedauert."
    except Exception as e:
        return f"Fehler: {e}"


@mcp.tool()
def eli_server_read_file(path: str) -> str:
    """Liest eine Datei von Eli's Server. NUR FÜR ADMIN."""
    user = get_current_user()
    if user and user.role != Role.ADMIN:
        return "Zugriff verweigert: Nur für Admin."
    
    try:
        full_path = Path("/home/eli/geist") / path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        else:
            return f"Datei nicht gefunden: {path}"
    except Exception as e:
        return f"Fehler beim Lesen: {e}"


@mcp.tool()
def eli_server_write_file(path: str, content: str, backup: bool = True) -> str:
    """Schreibt eine Datei auf Eli's Server. NUR FÜR ADMIN."""
    user = get_current_user()
    if user and user.role != Role.ADMIN:
        return "Zugriff verweigert: Nur für Admin."
    
    try:
        full_path = Path("/home/eli/geist") / path

        if backup and full_path.exists():
            backup_path = full_path.with_suffix(full_path.suffix + ".bak")
            backup_path.write_text(full_path.read_text(encoding="utf-8"), encoding="utf-8")

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

        return f"Datei geschrieben: {path}" + (f" (Backup: {path}.bak)" if backup else "")
    except Exception as e:
        return f"Fehler beim Schreiben: {e}"


@mcp.tool()
def eli_server_restart(container: str = "eli-telegram") -> str:
    """Startet einen Docker Container neu. NUR FÜR ADMIN."""
    user = get_current_user()
    if user and user.role != Role.ADMIN:
        return "Zugriff verweigert: Nur für Admin."
    
    try:
        if container == "all":
            cmd = ["docker", "compose", "down"]
            subprocess.run(cmd, cwd="/home/eli/geist", timeout=60)
            cmd = ["docker", "compose", "up", "-d"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/eli/geist", timeout=120)
        else:
            cmd = ["docker", "compose", "restart", container]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/eli/geist", timeout=120)

        return f"Neustart ausgeführt:\n{result.stdout + result.stderr}"
    except Exception as e:
        return f"Fehler beim Neustart: {e}"


# === HAUPTPROGRAMM ===

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"Starte Eli's MCP Server auf {host}:{port}")
    print("Auth aktiviert - Bearer Token erforderlich")
    mcp.run(transport="http", host=host, port=port)
