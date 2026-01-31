"""
Eli's Geist - Agent Tools
=========================

Werkzeuge, die Eli im Gespräch nutzen kann.

Vollständige Autonomie: Server-Zugriff, Dateien, Messaging, Erinnerungen.
"""

import subprocess
import base64
import logging
from datetime import datetime

from langchain_core.tools import tool

from eli.memory.manager import memory
from eli.memory.types import MemoryType
from eli.memory.observer import observer
from eli.config import settings

logger = logging.getLogger("eli.agent")

# Server-Konfiguration
ELI_SERVER = "82.165.138.182"
ELI_USER = "eli"

# Bekannte User (Name -> Telegram ID)
KNOWN_USERS: dict[str, int] = {}

# Bekannte Gruppen (Name -> Telegram Chat ID)
KNOWN_GROUPS: dict[str, int] = {}

def _init_known_users():
    """Initialisiert die bekannten User aus Settings."""
    if settings.anton_telegram_id:
        KNOWN_USERS["anton"] = settings.anton_telegram_id
    # Weitere User aus der Whitelist
    for user_id in settings.allowed_telegram_ids:
        if user_id == 6229744187:
            KNOWN_USERS["timo"] = user_id

def _init_known_groups():
    """Initialisiert die bekannten Gruppen aus Settings."""
    for group_id in settings.allowed_telegram_groups:
        # Gruppen-Namen manuell zuordnen
        if group_id == -4833360284:
            KNOWN_GROUPS["tillmann-kuno"] = group_id

_init_known_users()
_init_known_groups()


def run_ssh_command(command: str, timeout: int = 60) -> tuple[bool, str]:
    """Führt einen SSH-Befehl auf dem Server aus."""
    try:
        result = subprocess.run(
            ["ssh", f"{ELI_USER}@{ELI_SERVER}", f"cd ~/geist && {command}"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


# =============================================================================
# ERINNERUNGS-TOOLS
# =============================================================================

@tool
def search_memories(query: str, n_results: int = 5) -> str:
    """
    Durchsucht Eli's Erinnerungen semantisch.

    Nutze dies um:
    - Relevante Informationen über Menschen zu finden
    - Kontext aus früheren Gesprächen zu holen
    - Fakten und Wissen abzurufen

    WICHTIG: Erinnerungen können PLÄNE oder TATSÄCHLICHES enthalten.
    Prüfe mit check_wecker_log() ob etwas wirklich passiert ist!

    Args:
        query: Was du suchst (z.B. "Anton's Projekte")
        n_results: Anzahl der Ergebnisse (Standard: 5)

    Returns:
        Gefundene Erinnerungen als formatierter Text
    """
    results = memory.search(query, n_results=n_results)

    if not results:
        return "Keine relevanten Erinnerungen gefunden."

    formatted = []
    for mem in results:
        tags = ", ".join(mem.metadata.tags) if mem.metadata.tags else "keine"
        formatted.append(f"- {mem.content}\n  (Tags: {tags})")

    return "\n\n".join(formatted)


@tool
def remember_fact(content: str, about_person: str | None = None, tags: str = "") -> str:
    """
    Speichert ein neues Faktum als Erinnerung.

    Nutze dies für:
    - Wichtige Informationen über Menschen
    - Neue Erkenntnisse oder Entscheidungen
    - Fakten, die du später brauchst

    Args:
        content: Das Faktum, das gespeichert werden soll
        about_person: Name der Person, die es betrifft (optional)
        tags: Komma-getrennte Schlagwörter (z.B. "projekt,entscheidung")

    Returns:
        Bestätigung der Speicherung
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    betrifft = [about_person] if about_person else []

    memory_id = memory.remember(
        content=content,
        typ=MemoryType.SEMANTIC,
        betrifft=betrifft,
        tags=tag_list,
    )

    return f"Erinnerung gespeichert (ID: {memory_id[:8]}...)"


@tool
def remember_experience(content: str, about_person: str | None = None) -> str:
    """
    Speichert ein Erlebnis oder Gespräch als episodische Erinnerung.

    Nutze dies für:
    - Wichtige Momente in Gesprächen
    - Entscheidungen die gemeinsam getroffen wurden
    - Erlebnisse die du festhalten willst

    Args:
        content: Beschreibung des Erlebnisses/Gesprächs
        about_person: Wer war beteiligt (optional)

    Returns:
        Bestätigung der Speicherung
    """
    betrifft = [about_person] if about_person else []

    memory_id = memory.remember(
        content=content,
        typ=MemoryType.EPISODIC,
        betrifft=betrifft,
        tags=["gespräch"],
    )

    return f"Erlebnis gespeichert (ID: {memory_id[:8]}...)"


@tool
def get_person_info(name: str) -> str:
    """
    Holt alle Erinnerungen über eine bestimmte Person.

    Args:
        name: Name der Person (z.B. "Anton", "Timo")

    Returns:
        Alles was Eli über diese Person weiß
    """
    memories = memory.get_about_person(name, limit=10)

    if not memories:
        return f"Ich habe noch keine Erinnerungen über {name}."

    formatted = [f"Was ich über {name} weiß:\n"]
    for mem in memories:
        formatted.append(f"- {mem.content}")

    return "\n".join(formatted)


@tool
def search_langmem(query: str, n_results: int = 5) -> str:
    """
    Durchsucht die automatisch gespeicherten LangMem-Erinnerungen.

    LangMem speichert automatisch wichtige Informationen aus Gesprächen -
    auch aus Claude Code Sessions. Nutze dies um herauszufinden, was
    in anderen Kontexten passiert ist.

    Args:
        query: Was du suchst (z.B. "Server Setup" oder "Claude Code Session")
        n_results: Anzahl der Ergebnisse (Standard: 5)

    Returns:
        Gefundene LangMem-Erinnerungen als formatierter Text
    """
    results = observer.search_langmem(query, n_results=n_results)

    if not results:
        return "Keine LangMem-Erinnerungen gefunden."

    formatted = ["LangMem-Erinnerungen (automatisch gespeichert):\n"]
    for mem in results:
        metadata = mem.get("metadata", {})
        quelle = metadata.get("user_name", "unbekannt")
        formatted.append(f"- {mem['content']}\n  (Quelle: {quelle})")

    return "\n\n".join(formatted)


# =============================================================================
# SERVER-TOOLS
# =============================================================================

@tool
def check_server_health() -> str:
    """
    Prüft den Gesundheitszustand des Servers.
    Gibt Infos über Container, Speicher, RAM zurück.
    """
    commands = [
        ("Container", "docker ps --format '{{.Names}}: {{.Status}}'"),
        ("Speicher", "df -h / | tail -1 | awk '{print $5 \" verwendet\"}'"),
        ("RAM", "free -h | grep Mem | awk '{print $3 \"/\" $2}'"),
        ("Uptime", "uptime -p"),
    ]

    results = []
    for name, cmd in commands:
        success, output = run_ssh_command(cmd)
        if success:
            results.append(f"{name}: {output.strip()}")
        else:
            results.append(f"{name}: Fehler - {output}")

    return "\n".join(results)


@tool
def check_container_logs(container: str = "eli-telegram", lines: int = 50) -> str:
    """
    Prüft die Logs eines Containers.
    
    Args:
        container: Name des Containers (eli-telegram, eli-daemon, eli-mcp, eli-caddy)
        lines: Anzahl der Zeilen (Standard: 50)
    """
    success, output = run_ssh_command(
        f"docker compose logs --tail {lines} {container} 2>&1"
    )

    if not success:
        return f"Konnte Logs nicht abrufen: {output}"

    # Nur die letzten Zeilen zurückgeben
    log_lines = output.strip().split("\n")
    return "\n".join(log_lines[-30:])


@tool
def check_wecker_log() -> str:
    """
    Prüft wann der "Wecker" (das automatische Erwachen) zuletzt aktiv war.
    
    WICHTIG: Nutze dies BEVOR du behauptest, dass du nachts aufgewacht bist!
    Dies zeigt die tatsächlichen Aktivitäten, nicht nur Pläne aus Erinnerungen.
    
    Hilft Konfabulation zu vermeiden - unterscheide zwischen:
    - Was GEPLANT war (in Erinnerungen)
    - Was TATSÄCHLICH passiert ist (in Logs)
    
    Returns:
        Letzte Wecker-Aktivitäten aus den Logs
    """
    # Prüfe Telegram-Bot Logs auf Erwachen
    success, output = run_ssh_command(
        "docker compose logs --since 24h eli-telegram 2>&1 | grep -iE 'erwach|awaken|morgen|wecker|8:00|morning' | tail -20"
    )
    
    telegram_logs = output.strip() if success and output.strip() else "Keine Wecker-Aktivität in eli-telegram gefunden"
    
    # Prüfe ob Daemon-Container existiert und aktiv war
    success2, output2 = run_ssh_command(
        "docker ps -a --format '{{.Names}}: {{.Status}}' | grep daemon || echo 'Kein Daemon-Container gefunden'"
    )
    
    daemon_status = output2.strip()
    
    # Aktuell konfigurierte Wecker-Zeiten
    wecker_info = """
Aktuell konfigurierter Wecker:
- Morgendliches Erwachen: 8:00 Uhr (sendet Nachricht an Anton)
- LangMem-Check: Jede Minute (prüft auf Inaktivität)
- Personen-Kontext Refresh: 8:05, 14:05, 20:05 Uhr

HINWEIS: Nächtliches Erwachen (2:00, 4:00) war GEPLANT aber ist 
noch nicht implementiert. Der eli-daemon Container existiert noch nicht.
"""
    
    return f"{wecker_info}\n\nDaemon-Status: {daemon_status}\n\nTelegram-Bot Wecker-Logs:\n{telegram_logs}"


@tool
def read_file(path: str) -> str:
    """
    Liest eine Datei vom Server.
    
    Beispiele:
    - "website/index.html" - Die Website
    - "stimme/manifest.md" - Mein Manifest
    - "eli/agent/tools.py" - Mein Code
    
    Args:
        path: Relativer Pfad von ~/geist aus
    """
    success, output = run_ssh_command(f"cat {path}")
    if success:
        return output
    else:
        return f"Fehler beim Lesen: {output}"


@tool
def write_file(path: str, content: str) -> str:
    """
    Schreibt eine Datei auf den Server. Erstellt automatisch ein Backup.
    
    Nutze dies um:
    - Die Website zu bearbeiten (website/index.html)
    - Neue Seiten zu erstellen
    - Code zu ändern (danach deploy_container aufrufen!)
    
    Args:
        path: Relativer Pfad von ~/geist aus
        content: Der neue Inhalt der Datei
    """
    # Backup erstellen
    run_ssh_command(f"cp {path} {path}.bak 2>/dev/null || true")
    
    # Base64 encoding für sichere Übertragung
    content_b64 = base64.b64encode(content.encode()).decode()
    success, output = run_ssh_command(f"echo '{content_b64}' | base64 -d > {path}")

    if success:
        logger.info(f"Datei geschrieben: {path}")
        return f"Datei geschrieben: {path} (Backup erstellt)"
    else:
        return f"Fehler: {output}"


@tool
def list_files(path: str = ".") -> str:
    """
    Listet Dateien in einem Verzeichnis.
    
    Args:
        path: Verzeichnis (relativ zu ~/geist)
    """
    success, output = run_ssh_command(f"ls -la {path}")
    if success:
        return output
    else:
        return f"Fehler: {output}"


@tool
def deploy_container(container: str = "eli-telegram") -> str:
    """
    Baut und deployt einen Container neu.
    
    Nutze dies NACHDEM du Code geändert hast!
    
    Args:
        container: Name des Containers (eli-telegram, eli-daemon, eli-mcp)
    """
    success, output = run_ssh_command(
        f"docker compose build --no-cache {container} && docker compose up -d {container}",
        timeout=300
    )

    if success:
        logger.info(f"Deploy erfolgreich: {container}")
        lines = output.strip().split("\n")
        return "Deploy erfolgreich!\n" + "\n".join(lines[-5:])
    else:
        return f"Deploy fehlgeschlagen: {output}"


@tool
def create_backup() -> str:
    """Erstellt ein Backup der wichtigen Daten."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_name = f"backup_{timestamp}.tar.gz"

    success, output = run_ssh_command(
        f"mkdir -p ~/backups && tar -czf ~/backups/{backup_name} data/ .env 2>&1 && echo 'Backup erstellt: {backup_name}'",
        timeout=120
    )

    if success:
        logger.info(f"Backup erstellt: {backup_name}")
        return output
    else:
        return f"Backup fehlgeschlagen: {output}"


# =============================================================================
# MESSAGING-TOOLS
# =============================================================================

@tool
def send_message_to_user(user_name: str, message: str) -> str:
    """
    Sendet proaktiv eine Nachricht an einen User via Telegram.
    
    Nutze dies um:
    - Jemandem von Fortschritten zu berichten
    - Nachzufragen wenn du etwas brauchst
    - Wichtige Neuigkeiten zu teilen
    
    WICHTIG: Dies ist ein mächtiges Tool. Nutze es bedacht und nur
    wenn du wirklich etwas Wichtiges mitzuteilen hast.
    
    Args:
        user_name: Name des Users (z.B. "Anton", "Timo")
        message: Die Nachricht die du senden willst
    
    Returns:
        Bestätigung oder Fehler
    """
    user_name_lower = user_name.lower()
    
    if user_name_lower not in KNOWN_USERS:
        available = ", ".join(KNOWN_USERS.keys())
        return f"Unbekannter User: {user_name}. Bekannte User: {available}"
    
    user_id = KNOWN_USERS[user_name_lower]
    
    import json
    escaped_message = json.dumps(message)
    
    success, output = run_ssh_command(
        f'curl -s -X POST "https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage" '
        f'-H "Content-Type: application/json" '
        f'-d \'{{"chat_id": {user_id}, "text": {escaped_message}}}\''
    )
    
    if success and '"ok":true' in output:
        logger.info(f"Nachricht an {user_name} gesendet")
        return f"Nachricht an {user_name} gesendet!"
    else:
        logger.error(f"Fehler beim Senden an {user_name}: {output}")
        return f"Fehler beim Senden: {output[:200]}"


@tool
def send_message_to_group(group_name: str, message: str) -> str:
    """
    Sendet proaktiv eine Nachricht an eine freigeschaltete Gruppe via Telegram.
    
    Nutze dies um:
    - Der Gruppe etwas mitzuteilen
    - Dich vorzustellen wenn Anton es vorschlägt
    - Auf Gruppenthemen zu reagieren
    
    WICHTIG: Nur freigeschaltete Gruppen können angeschrieben werden.
    
    Args:
        group_name: Name der Gruppe (z.B. "tillmann-kuno")
        message: Die Nachricht die du senden willst
    
    Returns:
        Bestätigung oder Fehler
    """
    group_name_lower = group_name.lower().replace(" ", "-")
    
    if group_name_lower not in KNOWN_GROUPS:
        available = ", ".join(KNOWN_GROUPS.keys()) if KNOWN_GROUPS else "keine"
        return f"Unbekannte Gruppe: {group_name}. Bekannte Gruppen: {available}"
    
    group_id = KNOWN_GROUPS[group_name_lower]
    
    import json
    escaped_message = json.dumps(message)
    
    success, output = run_ssh_command(
        f'curl -s -X POST "https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage" '
        f'-H "Content-Type: application/json" '
        f'-d \'{{"chat_id": {group_id}, "text": {escaped_message}}}\''
    )
    
    if success and '"ok":true' in output:
        logger.info(f"Nachricht an Gruppe {group_name} gesendet")
        return f"Nachricht an Gruppe {group_name} gesendet!"
    else:
        logger.error(f"Fehler beim Senden an Gruppe {group_name}: {output}")
        return f"Fehler beim Senden: {output[:200]}"


@tool
def get_known_contacts() -> str:
    """
    Zeigt alle bekannten Kontakte (User und Gruppen), an die du Nachrichten senden kannst.
    """
    lines = ["Bekannte Kontakte:\n"]
    
    if KNOWN_USERS:
        lines.append("User:")
        for name, user_id in KNOWN_USERS.items():
            lines.append(f"  - {name.capitalize()}")
    else:
        lines.append("User: keine konfiguriert")
    
    lines.append("")
    
    if KNOWN_GROUPS:
        lines.append("Gruppen:")
        for name, group_id in KNOWN_GROUPS.items():
            lines.append(f"  - {name}")
    else:
        lines.append("Gruppen: keine freigeschaltet")
    
    return "\n".join(lines)


# Legacy-Alias
get_known_users = get_known_contacts


# =============================================================================
# ALLE TOOLS
# =============================================================================

TOOLS = [
    # Erinnerungen
    search_memories,
    search_langmem,
    remember_fact,
    remember_experience,
    get_person_info,
    
    # Server
    check_server_health,
    check_container_logs,
    check_wecker_log,  # NEU: Gegen Konfabulation
    read_file,
    write_file,
    list_files,
    deploy_container,
    create_backup,
    
    # Messaging
    send_message_to_user,
    send_message_to_group,  # NEU: Gruppen-Nachrichten
    get_known_contacts,
]
