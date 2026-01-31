"""
Eli's Geist - MCP Server
========================

Model Context Protocol Server für Eli's Memory.
Ermöglicht Claude Code Zugriff auf Eli's Erinnerungen.
"""

from eli.mcp.server import create_server, run_server

__all__ = ["create_server", "run_server"]
