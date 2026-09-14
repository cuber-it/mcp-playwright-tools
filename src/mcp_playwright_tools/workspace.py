"""What the tools share: the browser, the working directory, the boundary.

Every path a tool touches, a page opened from disk, a screenshot to be written,
a file to be uploaded, is resolved here and checked against the boundary in
force. No tool checks a path on its own. The boundary in force is the
configured one as a grant changes it (:mod:`mcp_playwright_tools.grant`); the
grant file itself is out of every tool's reach for writing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_playwright_tools.boundary import DEFAULT_MODE, Access, Boundary
from mcp_playwright_tools.errors import (
    NotPermittedError,
    OutsideBoundaryError,
    ToolError,
)
from mcp_playwright_tools.grant import boundary_in_force, grant_call, grant_file, hint
from mcp_playwright_tools.pool import (
    DEFAULT_CONTEXT,
    BrowserPool,
    Session,
    Settings,
    Spot,
)


@dataclass
class Workspace:
    """The state the tools work against.

    Attributes:
        working_dir: Directory relative paths are resolved against.
        pool: The browser and its named contexts.
        boundary: How far the tools may reach, before any grant.
        state_dir: Where the grant is kept, or None for no grants.
    """

    working_dir: Path
    pool: BrowserPool = field(default_factory=BrowserPool)
    boundary: Boundary = field(default_factory=Boundary)
    state_dir: Path | None = None

    def browsing(self, context: str = DEFAULT_CONTEXT) -> Browsing:
        """Return a named browser context of this workspace; nothing is opened yet."""
        return Browsing(self, context)

    def current(self) -> Boundary:
        """Return the boundary in force: the configured one as a grant changes it.

        Raises:
            GrantError: A grant file is there but cannot be used.
        """
        return boundary_in_force(self.boundary, self.state_dir)

    def resolve(self, path: str, access: Access = Access.READ) -> Path:
        """Turn a path from a caller into an absolute, resolved one and check it.

        Raises:
            NotPermittedError: Writing would reach the grant file.
            OutsideBoundaryError: The boundary in force does not let this access
                reach the path. The message names the grant that would.
            GrantError: A grant file is there but cannot be used.
        """
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.working_dir / candidate
        resolved = candidate.resolve()
        if access is Access.WRITE and self.state_dir is not None:
            held = grant_file(self.state_dir)
            if resolved in (held, held.parent):
                raise NotPermittedError(
                    f"{resolved} holds the grant file, which only {grant_call()} "
                    "on the host changes"
                )
        if not self.current().admits(resolved, access):
            nearest = resolved if resolved.is_dir() else resolved.parent
            limit = (
                "the directories uploads may come from"
                if access is Access.UPLOAD
                else f"the allowed roots for {access}"
            )
            raise OutsideBoundaryError(
                f"outside {limit}: {resolved}; "
                + hint(self.state_dir, f"--root {nearest}")
            )
        return resolved


@dataclass(frozen=True)
class Browsing:
    """One named browser context of a workspace: what the page tools act in.

    Attributes:
        space: The workspace with the browser, the paths and the boundary.
        context: The name of the browser context.
    """

    space: Workspace
    context: str = DEFAULT_CONTEXT

    async def spot(self) -> Spot:
        """Return where a call acts: the active tab, opened if needed.

        Raises:
            ToolError: The browser or a tab could not be opened.
        """
        return await self.space.pool.spot(self.context)

    async def session(self) -> Session:
        """Return this context with its tabs, opened if needed.

        Raises:
            ToolError: The browser could not be started.
        """
        return await self.space.pool.session(self.context)


def workspace_from(config: dict[str, Any]) -> Workspace:
    """Build the workspace from a configuration mapping.

    The boundary is read from ``allowed_roots`` and ``mode``; files are uploaded
    from ``working_dir``. The browser is read from ``browser``, ``channel``,
    ``headless``, ``timeout`` and ``idle``.

    Raises:
        ToolError: ``working_dir`` is not a directory, or a setting is unusable.
    """
    working = Path(str(config.get("working_dir", Path.cwd()))).expanduser().resolve()
    if not working.is_dir():
        raise ToolError(f"working_dir is not a directory: {working}")
    roots = tuple(
        Path(str(entry)).expanduser().resolve()
        for entry in config.get("allowed_roots", ())
    )
    state = config.get("state_dir")
    return Workspace(
        working_dir=working,
        pool=BrowserPool(Settings.read(config)),
        boundary=Boundary(
            roots, str(config.get("mode", DEFAULT_MODE)), uploads=(working,)
        ),
        state_dir=Path(str(state)).expanduser().resolve() if state else None,
    )
