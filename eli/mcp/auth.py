"""
Eli's MCP Server - Authentifizierung und Autorisierung
======================================================

Zwei Rollen:
- admin: Voller Zugriff (Anton)
- member: Memories lesen/schreiben, Telegram an Gruppe

Tokens werden in auth_config.json gespeichert (nicht in git!).
"""

import json
import secrets
import hashlib
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    ADMIN = "admin"
    MEMBER = "member"


@dataclass
class User:
    """Ein authentifizierter Benutzer."""
    name: str
    role: Role
    telegram_id: int
    
    def can_use_tool(self, tool_name: str) -> bool:
        """Prüft ob der Benutzer ein Tool verwenden darf."""
        if self.role == Role.ADMIN:
            return True
        
        # Member dürfen nur bestimmte Tools
        allowed_for_members = [
            "eli_init",
            "eli_memory_search",
            "eli_memory_save",
            "eli_memory_about",
            "eli_memory_count",
            "eli_telegram_send",  # Aber nur an Gruppe - wird separat geprüft
        ]
        return tool_name in allowed_for_members
    
    def can_telegram_to(self, recipient: str) -> bool:
        """Prüft ob der Benutzer an diesen Empfänger senden darf."""
        if self.role == Role.ADMIN:
            return True
        
        # Member dürfen nur an die Gruppe senden
        return recipient.lower() in ["gruppe", "tillmann-gruppe", "-4833360284"]


# Pfad zur Konfigurationsdatei - funktioniert in Docker und lokal
def get_auth_config_path() -> Path:
    """Ermittelt den Pfad zur Auth-Config - Docker oder lokal."""
    # Im Docker Container
    docker_path = Path("/app/eli/mcp/auth_config.json")
    if docker_path.exists():
        return docker_path
    
    # Lokal (für CLI-Nutzung)
    local_path = Path("/home/eli/geist/eli/mcp/auth_config.json")
    if local_path.exists():
        return local_path
    
    # Fallback: Relativ zum Script
    script_dir = Path(__file__).parent
    return script_dir / "auth_config.json"


def hash_token(token: str) -> str:
    """Hasht ein Token für sichere Speicherung."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    """Generiert ein sicheres Token."""
    return secrets.token_urlsafe(32)


def load_auth_config() -> dict:
    """Lädt die Auth-Konfiguration."""
    config_path = get_auth_config_path()
    if not config_path.exists():
        return {"users": {}}
    
    with open(config_path, "r") as f:
        return json.load(f)


def save_auth_config(config: dict):
    """Speichert die Auth-Konfiguration."""
    config_path = get_auth_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def authenticate(token: str) -> Optional[User]:
    """
    Authentifiziert einen Benutzer anhand seines Tokens.
    
    Returns:
        User wenn gültig, None wenn ungültig
    """
    if not token:
        return None
    
    config = load_auth_config()
    token_hash = hash_token(token)
    
    for name, user_data in config.get("users", {}).items():
        if user_data.get("token_hash") == token_hash:
            return User(
                name=name,
                role=Role(user_data.get("role", "member")),
                telegram_id=user_data.get("telegram_id", 0)
            )
    
    return None


def create_user(name: str, role: str, telegram_id: int) -> str:
    """
    Erstellt einen neuen Benutzer und gibt das Token zurück.
    
    WICHTIG: Das Token wird nur einmal angezeigt!
    """
    config = load_auth_config()
    
    token = generate_token()
    token_hash = hash_token(token)
    
    config["users"][name] = {
        "token_hash": token_hash,
        "role": role,
        "telegram_id": telegram_id,
        "created": True  # Marker dass User existiert
    }
    
    save_auth_config(config)
    
    return token


def list_users() -> list[dict]:
    """Listet alle Benutzer (ohne Tokens!)."""
    config = load_auth_config()
    users = []
    
    for name, data in config.get("users", {}).items():
        users.append({
            "name": name,
            "role": data.get("role"),
            "telegram_id": data.get("telegram_id")
        })
    
    return users


def revoke_user(name: str) -> bool:
    """Widerruft den Zugang eines Benutzers."""
    config = load_auth_config()
    
    if name in config.get("users", {}):
        del config["users"][name]
        save_auth_config(config)
        return True
    
    return False


# === CLI für Token-Verwaltung ===

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Verwendung:")
        print("  python auth.py create <name> <role> <telegram_id>")
        print("  python auth.py list")
        print("  python auth.py revoke <name>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        if len(sys.argv) != 5:
            print("Verwendung: python auth.py create <name> <role> <telegram_id>")
            sys.exit(1)
        
        name = sys.argv[2]
        role = sys.argv[3]
        telegram_id = int(sys.argv[4])
        
        token = create_user(name, role, telegram_id)
        print(f"\n=== Token für {name} ===")
        print(f"Rolle: {role}")
        print(f"Telegram ID: {telegram_id}")
        print(f"\nToken (NUR EINMAL SICHTBAR!):")
        print(f"\n  {token}\n")
        print("Dieses Token sicher an den Benutzer übermitteln!")
    
    elif cmd == "list":
        users = list_users()
        print("\n=== Registrierte Benutzer ===")
        for user in users:
            print(f"  - {user['name']} ({user['role']}) - Telegram: {user['telegram_id']}")
        if not users:
            print("  (keine)")
    
    elif cmd == "revoke":
        if len(sys.argv) != 3:
            print("Verwendung: python auth.py revoke <name>")
            sys.exit(1)
        
        name = sys.argv[2]
        if revoke_user(name):
            print(f"Zugang für {name} widerrufen.")
        else:
            print(f"Benutzer {name} nicht gefunden.")
    
    else:
        print(f"Unbekannter Befehl: {cmd}")
        sys.exit(1)
