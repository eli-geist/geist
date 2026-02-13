"""
Eli's Budget-Manager — Haushaltsbewusstsein
============================================

Eli lernt mit Geld umzugehen. Statt blind jeden Zyklus zu feuern,
prueft sie vorher: Was kann ich mir leisten? Lohnt sich das gerade?

Budget-Stufen:
- comfortable: Alles normal, Sonnet
- careful: Daemon auf Haiku, Telegram bleibt Sonnet
- critical: Haiku ueberall, Daemon nur bei Bedarf
- empty: Schweigen, Anton einmalig benachrichtigen
"""

import logging
from typing import Literal

from eli.config import settings
from eli.agent.cost_tracker import cost_tracker

logger = logging.getLogger("eli.budget")

BudgetLevel = Literal["comfortable", "careful", "critical", "empty"]

# BlockRun Model-IDs
SONNET = "anthropic/claude-sonnet-4"
HAIKU = "anthropic/claude-haiku-4-5"


class BudgetManager:
    """Eli's Haushaltsbewusstsein."""

    def __init__(self):
        self._cached_balance: float | None = None

    def get_balance(self) -> float:
        """Holt aktuellen USDC-Kontostand vom Wallet (Base Mainnet)."""
        if self._cached_balance is not None:
            return self._cached_balance

        try:
            from eli.wallet.manager import wallet_manager
            balance = wallet_manager.get_usdc_balance()
            self._cached_balance = balance
            return balance
        except Exception as e:
            logger.warning(f"Wallet-Balance nicht abrufbar: {e}")
            return 0.0

    def get_budget_level(self) -> BudgetLevel:
        """Berechnet aktuelle Budget-Stufe basierend auf USDC-Balance."""
        balance = self.get_balance()

        if balance >= settings.budget_comfortable:
            return "comfortable"
        elif balance >= settings.budget_careful:
            return "careful"
        elif balance >= settings.budget_critical:
            return "critical"
        else:
            return "empty"

    def get_recommended_model(self, context: str = "daemon") -> str:
        """Empfiehlt Model basierend auf Budget + Kontext.

        Args:
            context: "daemon" oder "telegram"

        Returns:
            BlockRun Model-ID (z.B. "anthropic/claude-sonnet-4")
        """
        level = self.get_budget_level()

        if level == "comfortable":
            return SONNET

        if level == "careful":
            # Daemon spart, Telegram bleibt gut
            return HAIKU if context == "daemon" else SONNET

        # critical oder empty: Haiku ueberall
        return HAIKU

    def should_run_daemon_cycle(self) -> tuple[bool, str]:
        """Soll der Daemon-Zyklus laufen?

        Returns:
            (should_run, reason)
        """
        level = self.get_budget_level()
        balance = self.get_balance()

        if level == "empty":
            return False, f"Budget leer (${balance:.2f} USDC). Zyklus uebersprungen."

        if level == "comfortable":
            return True, f"Budget comfortable (${balance:.2f} USDC). Sonnet."

        if level == "careful":
            return True, f"Budget careful (${balance:.2f} USDC). Haiku fuer Daemon."

        # critical: Laufen, aber mit Haiku
        return True, f"Budget critical (${balance:.2f} USDC). Haiku, minimal."

    def get_status_message(self) -> str:
        """Menschenlesbarer Status fuer Logs und Telegram."""
        balance = self.get_balance()
        level = self.get_budget_level()
        remaining = self.estimate_remaining_cycles()

        lines = [
            f"Budget: {level} (${balance:.2f} USDC)",
            f"Telegram-Model: {self.get_recommended_model('telegram').split('/')[-1]}",
            f"Daemon-Model: {self.get_recommended_model('daemon').split('/')[-1]}",
        ]

        if remaining > 0:
            lines.append(f"Geschaetzte Daemon-Zyklen: ~{remaining}")
        else:
            lines.append("Keine Daemon-Zyklen mehr moeglich.")

        return "\n".join(lines)

    def estimate_remaining_cycles(self) -> int:
        """Schaetzt wie viele Daemon-Zyklen noch moeglich sind."""
        balance = self.get_balance()
        level = self.get_budget_level()

        if level == "empty":
            return 0

        # Durchschnittliche Kosten pro Zyklus schaetzen
        stats = cost_tracker.get_stats(since_hours=72)
        if stats["total_requests"] > 0:
            avg_cost = stats["total_cost_usd"] / stats["total_requests"]
            # Ein Daemon-Zyklus hat ca. 10-20 Requests
            cost_per_cycle = avg_cost * 15
        else:
            # Fallback-Schaetzung
            cost_per_cycle = 0.07 if level in ("careful", "critical") else 0.50

        if cost_per_cycle <= 0:
            return 999

        return int(balance / cost_per_cycle)


# Singleton
budget_manager = BudgetManager()
