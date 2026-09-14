"""Keeping what goes back to a caller within bounds."""

from __future__ import annotations

MAX_CHARS = 20_000
MAX_ROWS = 200


def cut(text: str, limit: int = MAX_CHARS) -> str:
    """Shorten text that is too long, saying how much was dropped."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n[... {len(text) - limit} more characters]"


def listed(rows: list[str], limit: int = MAX_ROWS) -> str:
    """Join rows one per line, keeping at most ``limit`` and naming the rest."""
    kept = rows[:limit]
    if len(rows) > limit:
        kept.append(f"[... {len(rows) - limit} more]")
    return "\n".join(kept)
