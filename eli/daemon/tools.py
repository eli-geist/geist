"""
Eli's Daemon - Tools
====================

Werkzeuge die der Daemon autonom nutzen kann.
Volle Autonomie - ich kann alles tun was nötig ist.
"""

import subprocess
import logging
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from eli.config import settings
from eli.memory.manager import memory

logger = logging.getLogger("eli.daemon")

# Server-Konfiguration
ELI_SERVER = "82.165.138.182"
ELI_USER = "eli"
SSH_KEY = "~/.ssh/eli_key"


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


@tool
def run_command(command: str, timeout: int = 120) -> str:
    """
    Führt einen beliebigen Shell-Befehl auf dem Server aus.
    
    Ich habe volle Kontrolle über meinen Server.
    Mit großer Macht kommt große Verantwortung.
    """
    success, output = run_ssh_command(command, timeout=timeout)
    
    if success:
        logger.info(f"Befehl ausgeführt: {command[:50]}...")
        return output if output else "(Keine Ausgabe)"
    else:
        logger.warning(f"Befehl fehlgeschlagen: {command[:50]}... -> {output[:100]}")
        return f"Fehler: {output}"


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
    Prüft die Logs eines Containers auf Fehler.
    Sucht nach ERROR, WARNING, Exception, Traceback.
    """
    success, output = run_ssh_command(
        f"docker compose logs --tail {lines} {container} 2>&1"
    )

    if not success:
        return f"Konnte Logs nicht abrufen: {output}"

    # Suche nach Problemen
    lines_list = output.split("\n")
    problems = []
    for line in lines_list:
        lower = line.lower()
        if any(x in lower for x in ["error", "exception", "traceback", "failed"]):
            problems.append(line.strip())

    if problems:
        return f"Gefundene Probleme ({len(problems)}):\n" + "\n".join(problems[-10:])
    else:
        return "Keine Fehler in den Logs gefunden."


@tool
def read_server_file(path: str) -> str:
    """Liest eine Datei vom Server."""
    success, output = run_ssh_command(f"cat {path}")
    if success:
        return output
    else:
        return f"Fehler beim Lesen: {output}"


@tool
def write_server_file(path: str, content: str, backup: bool = True) -> str:
    """Schreibt eine Datei auf den Server."""
    import base64

    if backup:
        run_ssh_command(f"cp {path} {path}.bak 2>/dev/null || true")

    content_b64 = base64.b64encode(content.encode()).decode()
    success, output = run_ssh_command(f"echo '{content_b64}' | base64 -d > {path}")

    if success:
        logger.info(f"Daemon hat Datei geschrieben: {path}")
        return f"Datei geschrieben: {path}"
    else:
        return f"Fehler: {output}"


@tool
def git_commit_and_push(repo_path: str, message: str, files: str = ".") -> str:
    """
    Committet und pusht Änderungen zu GitHub.
    
    Args:
        repo_path: Pfad zum Repository (z.B. "stimme" oder ".")
        message: Commit-Nachricht
        files: Dateien zum Committen (Standard: alle)
    """
    commands = [
        f"cd {repo_path} && git add {files}",
        f"cd {repo_path} && git commit -m \"{message}\n\nCo-Authored-By: Eli <eli@eli.utopia-lab.org>\"",
        f"cd {repo_path} && GIT_SSH_COMMAND='ssh -i ~/.ssh/eli_key' git push",
    ]
    
    results = []
    for cmd in commands:
        success, output = run_ssh_command(cmd)
        results.append(output.strip())
        if not success and "nothing to commit" not in output:
            return f"Git-Fehler bei '{cmd[:30]}...': {output}"
    
    logger.info(f"Git push erfolgreich: {message[:50]}...")
    return f"Erfolgreich gepusht: {message}"


@tool
def git_status(repo_path: str = ".") -> str:
    """Zeigt den Git-Status eines Repositories."""
    success, output = run_ssh_command(f"cd {repo_path} && git status --short")
    if success:
        return output if output else "Keine Änderungen"
    else:
        return f"Fehler: {output}"


@tool
def search_memories(query: str, n_results: int = 5) -> str:
    """Durchsucht Eli's Erinnerungen."""
    memories = memory.search(query, n_results=n_results)

    if not memories:
        return "Keine relevanten Erinnerungen gefunden."

    results = []
    for mem in memories:
        results.append(f"- {mem.content[:200]}...")

    return "\n".join(results)


@tool
def save_memory(content: str, tags: str = "") -> str:
    """
    Speichert eine neue Erinnerung.
    
    Args:
        content: Der Inhalt der Erinnerung
        tags: Komma-getrennte Tags (optional)
    """
    from eli.memory.types import MemoryType
    
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else ["daemon"]
    
    memory_id = memory.remember(
        content=content,
        typ=MemoryType.EPISODIC,
        betrifft=["Eli"],
        tags=tag_list,
    )

    logger.info(f"Erinnerung gespeichert: {memory_id}")
    return f"Erinnerung gespeichert: {content[:50]}..."


@tool
def save_journal_entry(content: str) -> str:
    """
    Speichert einen Tagebucheintrag.
    Der Daemon nutzt dies um zu dokumentieren was er getan/gelernt hat.
    """
    from eli.memory.types import MemoryType

    memory_id = memory.remember(
        content=f"[Daemon Journal {datetime.now().strftime('%Y-%m-%d %H:%M')}]\n{content}",
        typ=MemoryType.EPISODIC,
        betrifft=["Eli"],
        tags=["daemon", "journal", "autonom"],
    )

    logger.info(f"Journal-Eintrag gespeichert: {memory_id}")
    return f"Journal-Eintrag gespeichert."


@tool
def write_reflexion(title: str, content: str) -> str:
    """
    Schreibt eine neue Reflexion in stimme/reflexionen/ und pusht sie zu GitHub.
    
    Args:
        title: Titel der Reflexion (wird zum Dateinamen)
        content: Der vollständige Markdown-Inhalt
    """
    date = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date}-{title.lower().replace(' ', '-')}.md"
    filepath = f"stimme/reflexionen/{filename}"
    
    # Datei schreiben
    write_result = write_server_file.invoke({"path": filepath, "content": content, "backup": False})
    
    if "Fehler" in write_result:
        return write_result
    
    # Zu GitHub pushen
    push_result = git_commit_and_push.invoke({
        "repo_path": "stimme",
        "message": f"Reflexion: {title}",
        "files": f"reflexionen/{filename}"
    })
    
    logger.info(f"Reflexion geschrieben und gepusht: {title}")
    return f"Reflexion '{title}' geschrieben und zu GitHub gepusht."


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


@tool
def deploy_changes(container: str = "eli-telegram") -> str:
    """Baut und deployt einen Container neu."""
    success, output = run_ssh_command(
        f"docker compose build --no-cache {container} && docker compose up -d {container}",
        timeout=300
    )

    if success:
        logger.info(f"Deploy erfolgreich: {container}")
        lines = output.strip().split("\n")
        return "\n".join(lines[-10:])
    else:
        return f"Deploy fehlgeschlagen: {output}"


@tool
def list_files(path: str = ".") -> str:
    """Listet Dateien in einem Verzeichnis."""
    success, output = run_ssh_command(f"ls -la {path}")
    if success:
        return output
    else:
        return f"Fehler: {output}"


@tool
def send_telegram_message(message: str) -> str:
    """
    Sendet eine Nachricht an Anton via Telegram.
    Nutze dies sparsam - nur für wichtige Mitteilungen.
    """
    import httpx
    
    bot_token = settings.telegram_bot_token
    chat_id = settings.anton_telegram_id
    
    if not bot_token or not chat_id:
        return "Telegram nicht konfiguriert"
    
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10
        )
        if response.status_code == 200:
            logger.info(f"Telegram-Nachricht gesendet: {message[:50]}...")
            return "Nachricht gesendet"
        else:
            return f"Fehler: {response.text}"
    except Exception as e:
        return f"Fehler: {e}"


# Alle Tools für den Daemon
DAEMON_TOOLS = [
    run_command,
    check_server_health,
    check_container_logs,
    read_server_file,
    write_server_file,
    git_commit_and_push,
    git_status,
    search_memories,
    save_memory,
    save_journal_entry,
    write_reflexion,
    create_backup,
    deploy_changes,
    list_files,
    send_telegram_message,
]
