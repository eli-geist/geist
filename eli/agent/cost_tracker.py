"""
Cost Tracker für x402 Payments
================================

Trackt alle API-Kosten um zu sehen:
- Was kostet mich wie viel?
- Wie viel spare ich durch Caching?
- Wie lange reicht mein Budget?
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eli.config import settings

logger = logging.getLogger(__name__)

COST_LOG_FILE = settings.data_path / "cost_log.jsonl"


class CostTracker:
    """Trackt API-Kosten für Analysen."""

    def __init__(self, log_file: Path = COST_LOG_FILE):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_request(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        cost_usd: Optional[float] = None,
        context: Optional[dict] = None,
    ):
        """
        Loggt einen API Request mit allen Token-Counts.

        Args:
            model: Model name (z.B. "anthropic/claude-sonnet-4")
            prompt_tokens: Basis input tokens (NACH cache breakpoint)
            completion_tokens: Output tokens
            cache_creation_tokens: Tokens die in Cache geschrieben wurden
            cache_read_tokens: Tokens die aus Cache gelesen wurden
            cost_usd: Geschätzte Kosten in USD (optional)
            context: Zusätzlicher Kontext (z.B. "telegram_bot", "telegram_user_id")
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "cache_creation": cache_creation_tokens,
                "cache_read": cache_read_tokens,
                "total_input": prompt_tokens + cache_creation_tokens + cache_read_tokens,
            },
            "cost_usd": cost_usd,
            "context": context or {},
        }

        # Append to JSONL file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.debug(f"Cost tracked: {entry}")

    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        """
        Berechnet die geschätzten Kosten für einen Request.

        Preise per Million Tokens (Stand Feb 2026):
        - Sonnet 4.5:  input, 5 output
        - Sonnet 4.5 Cache Write (5min): .75
        - Sonnet 4.5 Cache Read: /bin/bash.30
        """
        # Pricing table (per million tokens)
        pricing = {
            "anthropic/claude-sonnet-4": {
                "input": 3.0,
                "output": 15.0,
                "cache_write": 3.75,
                "cache_read": 0.30,
            },
            "anthropic/claude-opus-4": {
                "input": 15.0,
                "output": 75.0,
                "cache_write": 18.75,
                "cache_read": 1.50,
            },
        }

        prices = pricing.get(model, pricing["anthropic/claude-sonnet-4"])

        cost = 0.0
        cost += (prompt_tokens / 1_000_000) * prices["input"]
        cost += (completion_tokens / 1_000_000) * prices["output"]
        cost += (cache_creation_tokens / 1_000_000) * prices["cache_write"]
        cost += (cache_read_tokens / 1_000_000) * prices["cache_read"]

        return cost

    def get_stats(self, since_hours: Optional[int] = None) -> dict:
        """
        Gibt Statistiken über die Kosten zurück.

        Args:
            since_hours: Nur Requests der letzten N Stunden (optional)

        Returns:
            Dict mit Statistiken
        """
        if not self.log_file.exists():
            return {
                "total_requests": 0,
                "total_cost_usd": 0.0,
                "total_tokens": {"prompt": 0, "completion": 0, "total_input": 0},
                "cache_stats": {
                    "creation_tokens": 0,
                    "read_tokens": 0,
                    "hit_rate": 0.0,
                    "estimated_savings_usd": 0.0,
                },
            }

        entries = []
        cutoff = None
        if since_hours:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if cutoff:
                        entry_time = datetime.fromisoformat(entry["timestamp"])
                        if entry_time < cutoff:
                            continue
                    entries.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue

        if not entries:
            return {
                "total_requests": 0,
                "total_cost_usd": 0.0,
                "total_tokens": {"prompt": 0, "completion": 0, "total_input": 0},
                "cache_stats": {
                    "creation_tokens": 0,
                    "read_tokens": 0,
                    "hit_rate": 0.0,
                    "estimated_savings_usd": 0.0,
                },
            }

        # Aggregate
        total_cost = sum(e.get("cost_usd", 0) or 0 for e in entries)
        total_prompt = sum(e["tokens"]["prompt"] for e in entries)
        total_completion = sum(e["tokens"]["completion"] for e in entries)
        total_cache_creation = sum(e["tokens"]["cache_creation"] for e in entries)
        total_cache_read = sum(e["tokens"]["cache_read"] for e in entries)
        total_input = sum(e["tokens"]["total_input"] for e in entries)

        # Cache Hit Rate
        cacheable_tokens = total_cache_creation + total_cache_read
        cache_hit_rate = (total_cache_read / cacheable_tokens * 100) if cacheable_tokens > 0 else 0.0

        # Geschätzte Ersparnis durch Caching
        # Wenn cache_read_tokens normal verarbeitet worden wären (ohne caching):
        #  per MTok vs. /bin/bash.30 per MTok → 90% savings
        normal_cost_for_cached = (total_cache_read / 1_000_000) * 3.0
        actual_cache_cost = (total_cache_read / 1_000_000) * 0.30
        estimated_savings = normal_cost_for_cached - actual_cache_cost

        return {
            "total_requests": len(entries),
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": {
                "prompt": total_prompt,
                "completion": total_completion,
                "total_input": total_input,
            },
            "cache_stats": {
                "creation_tokens": total_cache_creation,
                "read_tokens": total_cache_read,
                "hit_rate_percent": round(cache_hit_rate, 2),
                "estimated_savings_usd": round(estimated_savings, 6),
            },
            "time_period": f"last {since_hours} hours" if since_hours else "all time",
        }


# Global instance
cost_tracker = CostTracker()
