"""How far the tools may reach: the roots, the mode, and whether scripts run.

This is the one place that decides. A tool names what it is about to do with a
path, and the boundary answers. It knows nothing about the tools.

How far the roots reach depends on the mode:

- ``open`` ignores them.
- ``guarded`` lets reading go anywhere and confines writing to them.
- ``strict`` confines reading as well.

Reading covers files handed to a page and pages opened from disk, writing
covers screenshots stored in a file. Empty roots mean no limit in every mode.
Whether JavaScript may be run in a page is a separate setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mcp_playwright_tools.errors import ToolError

MODES = ("open", "guarded", "strict")
DEFAULT_MODE = "guarded"


class Access(StrEnum):
    """What a tool is about to do with a path."""

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class Boundary:
    """The roots the tools are confined to, how far that reaches, and scripts.

    Attributes:
        roots: Directories the tools are confined to, empty for no limit.
        mode: How far the roots reach, one of :data:`MODES`.
        execute: Whether JavaScript may be run in a page.
    """

    roots: tuple[Path, ...] = ()
    mode: str = DEFAULT_MODE
    execute: bool = True

    def __post_init__(self) -> None:
        """Refuse a mode that does not exist.

        Raises:
            ToolError: The mode is not one of :data:`MODES`.
        """
        if self.mode not in MODES:
            raise ToolError(f"no such mode {self.mode!r}, choose from {MODES}")

    def admits(self, resolved: Path, access: Access = Access.READ) -> bool:
        """Say whether this access may reach a resolved path."""
        if not self.roots or self.mode == "open":
            return True
        if self.mode == "guarded" and access is Access.READ:
            return True
        return any(resolved == root or root in resolved.parents for root in self.roots)
