"""
Eli's Geist - MCP Server Entry Point
====================================

Starte mit: python -m eli.mcp
"""

import asyncio
from eli.mcp.server import run_server

if __name__ == "__main__":
    asyncio.run(run_server())
