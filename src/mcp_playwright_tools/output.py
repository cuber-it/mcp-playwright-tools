"""What goes back to a caller: text and listings within bounds, files written whole."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from mcp_playwright_tools.errors import ToolError

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


def latest(rows: list[str], limit: int = MAX_ROWS) -> str:
    """Join the last ``limit`` rows one per line, counting the earlier ones first."""
    if len(rows) <= limit:
        return "\n".join(rows)
    return "\n".join([f"[... {len(rows) - limit} earlier]", *rows[-limit:]])


def stored(path: Path, data: bytes, mode: int = 0o666) -> str:
    """Write data to a file, so that a failed write leaves nothing behind.

    ``mode`` is what the file may allow before the umask takes its share.

    Raises:
        ToolError: The file could not be written.
    """
    partial = path.with_name(f".{path.name}.partial")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial.unlink(missing_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        with open(os.open(partial, flags, mode), "wb") as out:
            out.write(data)
        partial.replace(path)
    except OSError as err:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise ToolError(f"could not write {path}: {err}") from err
    return f"wrote {path}, {len(data)} bytes"
