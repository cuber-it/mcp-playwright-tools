"""Browser tools: open pages, find and act on elements, read and photograph them.

The tools are plain async functions in :mod:`~mcp_playwright_tools.navigate`,
:mod:`~mcp_playwright_tools.examine`, :mod:`~mcp_playwright_tools.act`,
:mod:`~mcp_playwright_tools.read`, :mod:`~mcp_playwright_tools.keep` and
:mod:`~mcp_playwright_tools.watch`. Every
one that works on a page takes a :class:`Browsing` as its first argument: a
named browser context of the :class:`Workspace` it works against.

    import asyncio
    from pathlib import Path
    from mcp_playwright_tools import Workspace, navigate, read

    async def main():
        space = Workspace(working_dir=Path.cwd())
        here = space.browsing()
        print(await navigate.open_url(here, "example.org"))
        print(await read.read(here, "h1"))
        await space.pool.close_all()

    asyncio.run(main())

Nothing here knows about MCP. :mod:`mcp_playwright_tools.server` publishes these
functions; the library itself never imports it.
"""

from importlib.metadata import PackageNotFoundError, version

from mcp_playwright_tools import act, examine, keep, navigate, read, watch
from mcp_playwright_tools.boundary import Boundary
from mcp_playwright_tools.errors import (
    GrantError,
    NotPermittedError,
    OutsideBoundaryError,
    ToolError,
)
from mcp_playwright_tools.pool import DEFAULT_CONTEXT, BrowserPool, Settings
from mcp_playwright_tools.read import Picture
from mcp_playwright_tools.workspace import Browsing, Workspace, workspace_from

try:
    __version__ = version("mcp-playwright-tools")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"

__all__ = [
    "DEFAULT_CONTEXT",
    "Boundary",
    "BrowserPool",
    "Browsing",
    "GrantError",
    "NotPermittedError",
    "OutsideBoundaryError",
    "Picture",
    "Settings",
    "ToolError",
    "Workspace",
    "__version__",
    "act",
    "examine",
    "keep",
    "navigate",
    "read",
    "watch",
    "workspace_from",
]
