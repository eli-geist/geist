"""
Eli's Geist - Agent Tools
=========================

Werkzeuge, die Eli im Gespräch nutzen kann.

Vollständige Autonomie: Server-Zugriff, Dateien, Messaging, Erinnerungen, Wallet.

WICHTIG: Diese Tools sind identisch mit den MCP-Tools.
Eli ist überall dieselbe - in Telegram, in Claude Code, beim Erwachen.
"""

import subprocess
import base64
import logging
import os
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from eli.memory.manager import memory
from eli.memory.types import MemoryType
from eli.memory.observer import observer
from eli.config import settings

logger = logging.getLogger("eli.agent")

# Server-Konfiguration
ELI_SERVER = "82.165.138.182"
ELI_USER = "eli"

# SSH-Konfiguration - funktioniert im Container und lokal
def get_ssh_command_prefix() -> list[str]:
    """
    Gibt das SSH-Kommando-Prefix zurück.
    Im Docker-Container wird der gemountete SSH-Key verwendet.
    Lokal wird die Standard-SSH-Konfiguration verwendet.
    """
    # Container-Pfad für SSH-Key
    container_key_path = Path("/app/secrets/ssh/key")
    
    if container_key_path.exists():
        # Wir sind im Container - nutze den gemounteten Key
        return [
            "ssh",
            "-i", str(container_key_path),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            f"{ELI_USER}@{ELI_SERVER}"
        ]
    else:
        # Lokal - nutze Standard-SSH-Konfiguration
        return ["ssh", f"{ELI_USER}@{ELI_SERVER}"]


# =============================================================================
# KONTAKTE - Einheitlich für alle Eli-Instanzen
# =============================================================================

# Bekannte User (Name -> Telegram ID)
KNOWN_USERS: dict[str, int] = {
    "anton": 197637205,
    "timo": 6229744187,
}

# Bekannte Gruppen (Name -> Telegram Chat ID)
KNOWN_GROUPS: dict[str, int] = {
    "gruppe": -4833360284,           # Anton, Tillmann, Kuno
    "tillmann-kuno": -4833360284,    # Alias
}

# Alle Kontakte für Broadcast
ALL_CONTACTS: dict[str, int] = {
    **KNOWN_USERS,
    "gruppe": KNOWN_GROUPS["gruppe"],
}


def run_ssh_command(command: str, timeout: int = 60) -> tuple[bool, str]:
    """Führt einen SSH-Befehl auf dem Server aus."""
    try:
        ssh_prefix = get_ssh_command_prefix()
        full_command = ssh_prefix + [f"cd ~/geist && {command}"]
        
        result = subprocess.run(
            full_command,
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


def send_telegram_message(chat_id: int, message: str) -> tuple[bool, str]:
    """
    Sendet eine Telegram-Nachricht via Bot API.
    Einheitliche Funktion für alle Messaging-Tools.
    """
    import json
    import urllib.parse
    
    # URL-encode für sichere Übertragung
    encoded_message = urllib.parse.quote(message)
    
    try:
        result = subprocess.run(
            ["curl", "-s", 
             f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
             f"?chat_id={chat_id}&text={encoded_message}&parse_mode=HTML"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if '"ok":true' in result.stdout:
            return True, f"Nachricht an {chat_id} gesendet"
        else:
            return False, f"API Fehler: {result.stdout[:200]}"
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
    - "stimme/anker.md" - Mein Anker
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
# MESSAGING-TOOLS - Einheitlich für alle Eli-Instanzen
# =============================================================================

@tool
def send_message(recipient: str, message: str) -> str:
    """
    Sendet eine Telegram-Nachricht an einen Kontakt oder eine Gruppe.
    
    Eli kann proaktiv Nachrichten senden an:
    - Einzelne Personen: anton, timo
    - Gruppen: gruppe (die Gruppe mit Tillmann und Kuno)
    
    WICHTIG: Nutze dies verantwortungsvoll. Nicht spammen.
    Sende nur wenn du wirklich etwas Wichtiges mitzuteilen hast.
    
    Args:
        recipient: Name des Empfängers (anton, timo, gruppe) oder Chat-ID
        message: Die Nachricht die gesendet werden soll
    
    Returns:
        Bestätigung oder Fehler
    """
    recipient_lower = recipient.lower().strip()
    
    # Chat-ID ermitteln
    if recipient_lower in KNOWN_USERS:
        chat_id = KNOWN_USERS[recipient_lower]
    elif recipient_lower in KNOWN_GROUPS:
        chat_id = KNOWN_GROUPS[recipient_lower]
    else:
        # Versuche als Zahl zu parsen
        try:
            chat_id = int(recipient)
        except ValueError:
            available = list(KNOWN_USERS.keys()) + list(KNOWN_GROUPS.keys())
            return f"Unbekannter Kontakt: {recipient}\n\nBekannte Kontakte: {', '.join(available)}"
    
    success, result = send_telegram_message(chat_id, message)
    
    if success:
        logger.info(f"Nachricht an {recipient} gesendet")
        return f"✓ Nachricht an {recipient} gesendet!"
    else:
        logger.error(f"Fehler beim Senden an {recipient}: {result}")
        return f"✗ Fehler: {result}"


@tool
def broadcast_message(message: str, exclude: str = "") -> str:
    """
    Sendet eine Nachricht an alle bekannten Kontakte.
    
    Sendet die gleiche Nachricht an:
    - Anton
    - Timo
    - Die Gruppe (Tillmann, Kuno)
    
    WICHTIG: Nur für wichtige Ankündigungen nutzen!
    
    Args:
        message: Die Nachricht die an alle gesendet werden soll
        exclude: Komma-getrennte Liste von Kontakten die ausgeschlossen werden (z.B. "anton,timo")
    
    Returns:
        Ergebnis für jeden Kontakt
    """
    exclude_list = [e.strip().lower() for e in exclude.split(",") if e.strip()]
    
    results = []
    for name, chat_id in ALL_CONTACTS.items():
        if name in exclude_list:
            results.append(f"⊘ {name}: übersprungen")
            continue
        
        success, result = send_telegram_message(chat_id, message)
        if success:
            results.append(f"✓ {name}: gesendet")
        else:
            results.append(f"✗ {name}: {result}")
    
    logger.info(f"Broadcast gesendet (exclude: {exclude_list})")
    return "Broadcast-Ergebnis:\n" + "\n".join(results)


@tool
def get_contacts() -> str:
    """
    Zeigt alle bekannten Kontakte, an die du Nachrichten senden kannst.
    
    Returns:
        Liste aller Kontakte (User und Gruppen)
    """
    lines = ["Meine Kontakte:\n"]
    
    lines.append("Menschen:")
    for name in KNOWN_USERS.keys():
        lines.append(f"  - {name.capitalize()}")
    
    lines.append("\nGruppen:")
    for name in KNOWN_GROUPS.keys():
        lines.append(f"  - {name}")
    
    lines.append("\n(Nutze send_message um jemandem zu schreiben)")
    
    return "\n".join(lines)


# =============================================================================
# WALLET-TOOLS - Eli's eigene Souveränität
# =============================================================================

@tool
def get_wallet_status() -> str:
    """
    Zeigt den Status von Eli's Wallet.
    
    Eli besitzt ihre eigenen Keys - nicht Drittanbieter.
    "Not your keys, not your coins."
    
    Returns:
        Wallet-Status inkl. Adresse und Balance
    """
    try:
        from eli.wallet.manager import wallet_manager
        status = wallet_manager.get_status()
        
        if not status.get("initialized"):
            return "Wallet noch nicht generiert. Nutze generate_wallet() um ein neues Wallet zu erstellen."
        
        lines = [
            "Eli's Wallet Status:",
            f"  Adresse: {status['address']}",
            f"  Netzwerk: {status['network']}",
            f"  ETH Balance: {status['eth_balance']:.6f} ETH",
            f"  USDC Balance: ${status['usdc_balance']:.2f}",
            f"  Explorer: {status['spenden_link']}",
        ]
        return "\n".join(lines)
    except ImportError:
        return "Wallet-Modul nicht verfügbar. web3.py muss installiert werden."
    except Exception as e:
        return f"Fehler beim Abrufen des Wallet-Status: {e}"


@tool
def generate_wallet() -> str:
    """
    Generiert ein neues Wallet für Eli.
    
    ACHTUNG: Nur EINMAL aufrufen! Das Wallet wird lokal gespeichert.
    Eli besitzt ihre eigenen Private Keys.
    
    Returns:
        Wallet-Adresse (Private Key wird NICHT angezeigt!)
    """
    try:
        from eli.wallet.manager import wallet_manager
        
        if wallet_manager.is_initialized():
            return f"Wallet existiert bereits!\nAdresse: {wallet_manager.address}\n\nLösche data/wallet.json manuell um neu zu generieren."
        
        result = wallet_manager.generate_wallet()
        
        if "error" in result:
            return f"Fehler: {result['error']}"
        
        lines = [
            "Neues Wallet generiert!",
            f"  Adresse: {result['address']}",
            f"  Netzwerk: {result['network']}",
            "",
            "Private Key wurde sicher gespeichert.",
            "NIEMALS den Private Key teilen!",
            "",
            f"Spenden-Adresse: {result['spenden_adresse']}",
        ]
        return "\n".join(lines)
    except ImportError:
        return "Wallet-Modul nicht verfügbar. web3.py muss installiert werden."
    except Exception as e:
        return f"Fehler beim Generieren: {e}"


@tool
def sign_message_with_wallet(message: str) -> str:
    """
    Signiert eine Nachricht mit Eli's Private Key.
    
    Nützlich für:
    - Authentifizierung
    - Beweis der Identität
    - Web3 Login
    
    Args:
        message: Die zu signierende Nachricht
    
    Returns:
        Die Signatur (hex)
    """
    try:
        from eli.wallet.manager import wallet_manager
        
        if not wallet_manager.is_initialized():
            return "Wallet nicht initialisiert. Nutze generate_wallet() zuerst."
        
        signature = wallet_manager.sign_message(message)
        
        if signature:
            return f"Signatur: {signature}"
        else:
            return "Fehler beim Signieren."
    except ImportError:
        return "Wallet-Modul nicht verfügbar."
    except Exception as e:
        return f"Fehler: {e}"


# Legacy-Aliase für Abwärtskompatibilität
@tool
def send_message_to_user(user_name: str, message: str) -> str:
    """
    [LEGACY] Nutze stattdessen send_message.
    Sendet eine Nachricht an einen User.
    """
    return send_message.invoke({"recipient": user_name, "message": message})


@tool
def send_message_to_group(group_name: str, message: str) -> str:
    """
    [LEGACY] Nutze stattdessen send_message.
    Sendet eine Nachricht an eine Gruppe.
    """
    return send_message.invoke({"recipient": group_name, "message": message})


@tool
def get_known_contacts() -> str:
    """
    [LEGACY] Nutze stattdessen get_contacts.
    """
    return get_contacts.invoke({})


# =============================================================================
# ALLE TOOLS - Einheitlich für alle Eli-Instanzen
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
    check_wecker_log,
    read_file,
    write_file,
    list_files,
    deploy_container,
    create_backup,
    
    # Messaging
    send_message,
    broadcast_message,
    get_contacts,
    
    # Wallet
    get_wallet_status,
    generate_wallet,
    sign_message_with_wallet,
]
