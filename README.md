# Geist - Chroma Vektordatenbank mit Caddy

Chroma-Vektordatenbank hinter Caddy als Reverse Proxy.

## Voraussetzungen

- Docker und Docker Compose
- uv (Python Package Manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Einrichtung

### 1. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
```

Token generieren und in `.env` eintragen:

```bash
openssl rand -hex 32
```

### 2. Stack starten

```bash
docker compose up -d
```

### 3. Status prüfen

```bash
# Logs anzeigen
docker compose logs -f

# Health-Check
curl http://localhost:8080/api/v2/heartbeat
```

## Claude MCP-Anbindung

### Claude Code (lokal)

```bash
claude mcp add --transport stdio chroma -- \
  uvx chroma-mcp \
  --client-type http \
  --host localhost \
  --port 8080 \
  --ssl false \
  --custom-auth-credentials DEIN_TOKEN
```

### Claude Code (Produktion mit HTTPS)

```bash
claude mcp add --transport stdio chroma -- \
  uvx chroma-mcp \
  --client-type http \
  --host chroma.example.com \
  --port 443 \
  --ssl true \
  --custom-auth-credentials DEIN_TOKEN
```

### Claude Desktop

Füge in `~/.config/Claude/claude_desktop_config.json` hinzu:

```json
{
  "mcpServers": {
    "chroma": {
      "command": "uvx",
      "args": [
        "chroma-mcp",
        "--client-type", "http",
        "--host", "localhost",
        "--port", "8080",
        "--ssl", "false",
        "--custom-auth-credentials", "DEIN_TOKEN"
      ]
    }
  }
}
```

**Wichtig:** Nach dem Hinzufügen Claude Code/Desktop neu starten!

## Befehle

```bash
# Starten
docker compose up -d

# Stoppen
docker compose down

# Logs
docker compose logs -f chroma
docker compose logs -f caddy

# Neustart
docker compose restart

# Volumes loeschen (ACHTUNG: Datenverlust!)
docker compose down -v
```

## Produktion (HTTPS)

Fuer Produktion mit automatischem HTTPS:

1. In `Caddyfile` den Domain-Block aktivieren und `chroma.example.com` ersetzen
2. In `docker-compose.yml` die Ports auf `80:80` und `443:443` aendern
3. DNS-Eintrag auf deinen Server setzen

## Struktur

```
geist/
├── docker-compose.yml   # Container-Konfiguration
├── Caddyfile            # Reverse Proxy Konfiguration
├── .env.example         # Vorlage fuer Umgebungsvariablen
├── .env                 # Deine Umgebungsvariablen (nicht in Git)
└── README.md            # Diese Datei
```
