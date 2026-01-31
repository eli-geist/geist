"""
Eli's Daemon - Entry Point
"""

from eli.daemon.runner import run_once, run_scheduled
import sys

if __name__ == "__main__":
    if "--mode" in sys.argv and "scheduled" in sys.argv:
        run_scheduled()
    else:
        run_once()
