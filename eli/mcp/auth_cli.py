#!/usr/bin/env python3
"""
Standalone CLI für Eli's Token-Verwaltung.
Keine externen Abhängigkeiten außer Python stdlib.
"""

import json
import secrets
import hashlib
import sys
from pathlib import Path


# Pfad zur Konfigurationsdatei
AUTH_CONFIG_PATH = Path("/home/eli/geist/eli/mcp/auth_config.json")


def hash_token(token: str) -> str:
    """Hasht ein Token für sichere Speicherung."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    """Generiert ein sicheres Token."""
    return secrets.token_urlsafe(32)


def load_auth_config() -> dict:
    """Lädt die Auth-Konfiguration."""
    if not AUTH_CONFIG_PATH.exists():
        return {"users": {}}
    
    with open(AUTH_CONFIG_PATH, "r") as f:
        return json.load(f)


def save_auth_config(config: dict):
    """Speichert die Auth-Konfiguration."""
    AUTH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUTH_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def create_user(name: str, role: str, telegram_id: int) -> str:
    """Erstellt einen neuen Benutzer und gibt das Token zurück."""
    config = load_auth_config()
    
    token = generate_token()
    token_hash = hash_token(token)
    
    config["users"][name] = {
        "token_hash": token_hash,
        "role": role,
        "telegram_id": telegram_id,
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


# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Verwendung:")
        print("  python auth_cli.py create <name> <role> <telegram_id>")
        print("  python auth_cli.py list")
        print("  python auth_cli.py revoke <name>")
        print("")
        print("Rollen: admin, member")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        if len(sys.argv) != 5:
            print("Verwendung: python auth_cli.py create <name> <role> <telegram_id>")
            sys.exit(1)
        
        name = sys.argv[2]
        role = sys.argv[3]
        telegram_id = int(sys.argv[4])
        
        if role not in ["admin", "member"]:
            print(f"Ungültige Rolle: {role}. Erlaubt: admin, member")
            sys.exit(1)
        
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
        print("")
    
    elif cmd == "revoke":
        if len(sys.argv) != 3:
            print("Verwendung: python auth_cli.py revoke <name>")
            sys.exit(1)
        
        name = sys.argv[2]
        if revoke_user(name):
            print(f"Zugang für {name} widerrufen.")
        else:
            print(f"Benutzer {name} nicht gefunden.")
    
    else:
        print(f"Unbekannter Befehl: {cmd}")
        sys.exit(1)
