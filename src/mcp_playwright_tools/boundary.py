"""How far the tools may reach on the machine: the roots, the uploads, the mode.

This is the one place that decides. A tool names what it is about to do with a
path, and the boundary answers. It knows nothing about the tools.

- Reading covers pages opened from disk. ``guarded`` lets it go anywhere,
  ``strict`` confines it to the roots.
- Writing covers screenshots stored in a file, confined to the roots.
- Uploading hands a file to a web page, which can send it anywhere. It is
  confined to the upload directories.

``open`` lifts every limit, and ``/tmp`` is always within reach. Empty roots
or empty upload directories mean no limit for what they confine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mcp_playwright_tools.errors import ToolError

MODES = ("open", "guarded", "strict")
DEFAULT_MODE = "guarded"
TMP = Path("/tmp")


class Access(StrEnum):
    """What a tool is about to do with a path."""

    READ = "read"
    WRITE = "write"
    UPLOAD = "upload"


@dataclass(frozen=True)
class Boundary:
    """Where reading, writing and uploading may reach, and how far that holds.

    Attributes:
        roots: Directories writing, and in ``strict`` reading, is confined to;
            empty for no limit.
        mode: How far the limits reach, one of :data:`MODES`.
        uploads: Directories files may be uploaded from; empty for no limit.
    """

    roots: tuple[Path, ...] = ()
    mode: str = DEFAULT_MODE
    uploads: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        """Refuse a mode that does not exist.

        Raises:
            ToolError: The mode is not one of :data:`MODES`.
        """
        if self.mode not in MODES:
            raise ToolError(f"no such mode {self.mode!r}, choose from {MODES}")

    def admits(self, resolved: Path, access: Access = Access.READ) -> bool:
        """Say whether this access may reach a resolved path."""
        if self.mode == "open" or _within(resolved, (TMP,)):
            return True
        if access is Access.UPLOAD:
            return not self.uploads or _within(resolved, self.uploads)
        if self.mode == "guarded" and access is Access.READ:
            return True
        return not self.roots or _within(resolved, self.roots)


def _within(path: Path, directories: tuple[Path, ...]) -> bool:
    """Say whether a path is one of the directories or lies below one."""
    return any(
        path == directory or directory in path.parents for directory in directories
    )
