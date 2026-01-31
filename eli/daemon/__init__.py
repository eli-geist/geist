"""
Eli's Daemon - Autonomer Agent
==============================

Ein LangGraph-basierter Agent der eigenständig arbeitet,
während Anton schläft.
"""

from eli.daemon.graph import daemon_agent, run_daemon_cycle

__all__ = ["daemon_agent", "run_daemon_cycle"]
