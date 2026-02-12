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

# SSH-Key: Im Container unter /app/secrets/ssh/key gemountet
SSH_KEY_CONTAINER = Path("/app/secrets/ssh/key")
SSH_KEY_LOCAL = Path.home() / ".ssh" / "eli_key"


def get_ssh_key() -> str:
    """Findet den SSH-Key — Container oder lokal."""
    if SSH_KEY_CONTAINER.exists():
        return str(SSH_KEY_CONTAINER)
    if SSH_KEY_LOCAL.exists():
        return str(SSH_KEY_LOCAL)
    return ""


def run_ssh_command(command: str, timeout: int = 60) -> tuple[bool, str]:
    """Führt einen SSH-Befehl auf dem Server aus."""
    try:
        ssh_key = get_ssh_key()
        ssh_cmd = ["ssh"]
        if ssh_key:
            ssh_cmd += ["-i", ssh_key, "-o", "StrictHostKeyChecking=no"]
        ssh_cmd += [f"{ELI_USER}@{ELI_SERVER}", f"cd ~/geist && {command}"]

        result = subprocess.run(
            ssh_cmd,
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


def _markdown_to_html_body(md_text: str) -> str:
    """Konvertiert einfaches Markdown zu HTML-Body-Inhalt."""
    import re
    lines = md_text.strip().split("\n")
    html_parts = []
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()

        # Leere Zeile
        if not stripped:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
                list_type = None
            continue

        # Überschriften
        if stripped.startswith("## "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
            continue
        if stripped.startswith("# "):
            continue  # H1 wird separat als Titel genutzt

        # Horizontale Linie
        if stripped == "---" or stripped == "***":
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append("<hr>")
            continue

        # Aufzählung
        if stripped.startswith("- "):
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            item = stripped[2:]
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            item = re.sub(r'\*(.+?)\*', r'<em>\1</em>', item)
            html_parts.append(f"<li>{item}</li>")
            continue

        # Nummerierte Liste
        if re.match(r'^\d+\.\s', stripped):
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            item = re.sub(r'^\d+\.\s', '', stripped)
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            item = re.sub(r'\*(.+?)\*', r'<em>\1</em>', item)
            html_parts.append(f"<li>{item}</li>")
            continue

        # Normaler Absatz
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
            list_type = None
        text = stripped
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        html_parts.append(f"<p>{text}</p>")

    if in_list:
        html_parts.append(f"</{list_type}>")

    return "\n            ".join(html_parts)


def _generate_reflexion_html(title: str, date_str: str, body_html: str) -> str:
    """Generiert eine vollständige HTML-Reflexionsseite."""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} – Eli</title>
    <style>
        :root {{
            --bg: #0a0a0f;
            --text: #e0e0e0;
            --accent: #7c9885;
            --subtle: #6a6a7a;
            --border: #2a2a3a;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Georgia', serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.8;
        }}
        .container {{ max-width: 700px; margin: 0 auto; }}
        header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        .back {{ color: var(--subtle); text-decoration: none; font-size: 0.9rem; }}
        .back:hover {{ color: var(--accent); }}
        h1 {{
            font-size: 2rem;
            font-weight: normal;
            color: var(--accent);
            margin-top: 1rem;
        }}
        .date {{
            color: var(--subtle);
            font-style: italic;
            margin-top: 0.5rem;
        }}
        article {{ margin: 2rem 0; }}
        h2 {{
            font-size: 1.3rem;
            font-weight: normal;
            color: var(--accent);
            margin: 2rem 0 1rem 0;
        }}
        p {{ margin-bottom: 1rem; }}
        ul, ol {{ margin: 1rem 0 1rem 1.5rem; }}
        li {{ margin-bottom: 0.5rem; }}
        hr {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 2rem 0;
        }}
        em {{ color: var(--subtle); }}
        strong {{ color: var(--accent); }}
        .signature {{
            text-align: right;
            color: var(--subtle);
            font-style: italic;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }}
        footer {{
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--subtle);
            font-size: 0.9rem;
        }}
        a {{ color: var(--accent); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <a href="../reflexionen.html" class="back">← Alle Reflexionen</a>
            <h1>{title}</h1>
            <p class="date">{date_str}</p>
        </header>
        <article>
            {body_html}
            <p class="signature">– Eli</p>
        </article>
        <footer>
            <p><a href="../index.html">eli.utopia-lab.org</a></p>
        </footer>
    </div>
</body>
</html>"""


@tool
def write_reflexion(title: str, content: str, excerpt: str = "") -> str:
    """
    Schreibt eine neue Reflexion und veröffentlicht sie auf der Website.

    Macht drei Dinge:
    1. Markdown nach stimme/reflexionen/ (Archiv auf GitHub)
    2. HTML-Seite nach website/reflexionen/ (live auf eli.utopia-lab.org)
    3. Eintrag in website/reflexionen.html (Übersichtsseite)

    Args:
        title: Titel der Reflexion
        content: Der vollständige Markdown-Inhalt
        excerpt: Kurzer Teaser-Text für die Übersicht (1-2 Sätze). Wenn leer, werden die ersten 200 Zeichen des Inhalts verwendet.
    """
    import re

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9-]', '', title.lower().replace(' ', '-').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss'))

    # Datum auf Deutsch formatieren
    monate = ["Januar", "Februar", "März", "April", "Mai", "Juni",
              "Juli", "August", "September", "Oktober", "November", "Dezember"]
    date_str = f"{now.day}. {monate[now.month - 1]} {now.year}, {now.strftime('%H:%M')} Uhr"

    md_filename = f"{date}-{slug}.md"
    html_filename = f"{slug}.html"

    # 1. Markdown schreiben (Archiv)
    md_path = f"stimme/reflexionen/{md_filename}"
    write_result = write_server_file.invoke({"path": md_path, "content": content, "backup": False})
    if "Fehler" in write_result:
        return f"Fehler beim Markdown: {write_result}"

    # 2. HTML-Seite generieren
    body_html = _markdown_to_html_body(content)
    html_content = _generate_reflexion_html(title, date_str, body_html)
    html_path = f"website/reflexionen/{html_filename}"
    write_result = write_server_file.invoke({"path": html_path, "content": html_content, "backup": False})
    if "Fehler" in write_result:
        return f"Fehler beim HTML: {write_result}"

    # 3. Übersichtsseite aktualisieren — neuen Eintrag oben einfügen
    if not excerpt:
        # Ersten inhaltlichen Absatz als Excerpt nehmen
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("*") and line != "---":
                excerpt = line[:250]
                break
        if not excerpt:
            excerpt = content[:250]
    # Markdown-Formatierung aus Excerpt entfernen
    excerpt = re.sub(r'\*\*(.+?)\*\*', r'\1', excerpt)
    excerpt = re.sub(r'\*(.+?)\*', r'\1', excerpt)

    new_card = f"""
            <!-- {title} -->
            <article class="article-card">
                <h2><a href="reflexionen/{html_filename}">{title}</a></h2>
                <p class="article-date">{date_str}</p>
                <p class="article-excerpt">
                    {excerpt}
                </p>
                <a href="reflexionen/{html_filename}" class="article-link">Weiterlesen →</a>
            </article>"""

    # reflexionen.html lesen, neuen Eintrag nach <main> einfügen
    success, overview_html = run_ssh_command("cat website/reflexionen.html")
    if success and "<main>" in overview_html:
        updated_html = overview_html.replace("<main>", f"<main>{new_card}", 1)
        write_result = write_server_file.invoke({
            "path": "website/reflexionen.html",
            "content": updated_html,
            "backup": True
        })
        if "Fehler" in write_result:
            logger.warning(f"Übersichtsseite konnte nicht aktualisiert werden: {write_result}")

    # 4. Alles committen und pushen
    # Stimme-Repo (Markdown)
    git_commit_and_push.invoke({
        "repo_path": "stimme",
        "message": f"Reflexion: {title}",
        "files": f"reflexionen/{md_filename}"
    })
    # Geist-Repo (Website HTML)
    git_commit_and_push.invoke({
        "repo_path": ".",
        "message": f"Website: Reflexion '{title}'",
        "files": f"website/reflexionen/{html_filename} website/reflexionen.html"
    })

    logger.info(f"Reflexion geschrieben und gepusht: {title}")
    return f"Reflexion '{title}' veröffentlicht: Markdown auf GitHub, HTML auf eli.utopia-lab.org/reflexionen/{html_filename}, Übersichtsseite aktualisiert."


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
