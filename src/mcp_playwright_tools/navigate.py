"""Where the browser is: opening pages, the history, tabs, frames and the viewport."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
from urllib.request import url2pathname

from playwright.async_api import Page

from mcp_playwright_tools.errors import ToolError, attempt, unknown
from mcp_playwright_tools.workspace import Browsing, Workspace

SETTLE = "domcontentloaded"
# Written without //: a data: address would otherwise become https://data:...
BARE_SCHEMES = ("data:", "about:", "blob:")
DIRECTIONS = ("back", "forward", "reload")
TAB_ACTIONS = ("list", "open", "switch", "close")


async def open_url(browsing: Browsing, url: str) -> str:
    """Open a page and wait until its document has loaded.

    Without a scheme, https is assumed. A ``file:`` address has to lie where
    reading may reach.

    Returns:
        The address the browser ended up at, which differs after a redirect.

    Raises:
        OutsideBoundaryError: A file: address lies outside what may be read.
        ToolError: The address is empty or a javascript: one, or the page could
            not be opened.
    """
    address = _address(browsing.space, url)
    spot = await browsing.spot()
    await attempt(spot.page.goto(address, wait_until=SETTLE), f"open {address}")
    return f"at {spot.page.url}"


async def go(browsing: Browsing, direction: str = "back") -> str:
    """Go back or forward in the history, or load the page again.

    Returns:
        Where the browser is afterwards.

    Raises:
        ToolError: There is no such direction, or the page could not be loaded.
    """
    if direction not in DIRECTIONS:
        raise unknown("direction", direction, DIRECTIONS)
    page = (await browsing.spot()).page
    moves = {"back": page.go_back, "forward": page.go_forward, "reload": page.reload}
    await attempt(moves[direction](wait_until=SETTLE), f"go {direction}")
    return f"at {page.url}"


async def where_am_i(browsing: Browsing) -> dict[str, Any]:
    """Return address, title, tab, frame acted in, the page's frames and viewport.

    Raises:
        ToolError: The title could not be read.
    """
    spot = await browsing.spot()
    page = spot.page
    return {
        "url": page.url,
        "title": await attempt(page.title(), "read the title"),
        "tab": spot.session.active,
        "frame": spot.session.frame or "",
        "frames": [
            f"{frame.name or '(no name)'} - {frame.url}"
            for frame in page.frames
            if frame.parent_frame is not None
        ],
        "viewport": _size(page),
    }


async def tabs(browsing: Browsing, action: str = "list", tab: int = -1) -> str:
    """List, open, switch or close tabs; switch and close need the tab's number.

    Raises:
        ToolError: There is no such action, or no such tab.
    """
    pool = browsing.space.pool
    if action == "list":
        session = await browsing.session()
        if not session.pages:
            return "no tab open"
        return "\n".join(
            [
                await _described(number, page, number == session.active)
                for number, page in sorted(session.pages.items())
            ]
        )
    if action == "open":
        return f"opened tab {await pool.open_tab(browsing.context)}"
    if action == "switch":
        await pool.switch_tab(browsing.context, tab)
        return f"active tab is now {tab}"
    if action == "close":
        await pool.close_tab(browsing.context, tab)
        return f"closed tab {tab}"
    raise unknown("action", action, TAB_ACTIONS)


async def use_frame(browsing: Browsing, selector: str = "") -> str:
    """Act inside the frame a selector names from now on, or in the page again.

    Steps into a frame inside a frame are joined with ``>>``.
    """
    session = await browsing.session()
    session.frame = selector or None
    return f"acting inside {selector!r}" if selector else "acting in the page itself"


async def viewport(browsing: Browsing, width: int = 0, height: int = 0) -> str:
    """Report the viewport of the active tab, or set it in pixels.

    Raises:
        ToolError: Only one side is given, a side is not positive, or the
            viewport could not be set.
    """
    if (width, height) != (0, 0) and (width <= 0 or height <= 0):
        raise ToolError(f"width and height have to be positive, not {width}x{height}")
    page = (await browsing.spot()).page
    if width:
        size = {"width": width, "height": height}
        await attempt(page.set_viewport_size(size), "set the viewport")
    return f"viewport {_size(page)}"


async def _described(number: int, page: Page, active: bool) -> str:
    """Return one line of the tab listing.

    Raises:
        ToolError: The title of the tab could not be read.
    """
    title = await attempt(page.title(), f"read the title of tab {number}")
    marker = " (active)" if active else ""
    return f"{number}{marker}: {title or '(no title)'} - {page.url}"


def _size(page: Page) -> str:
    """Return the viewport of a tab as width x height."""
    size = page.viewport_size
    return f"{size['width']}x{size['height']}" if size else "none"


def _address(space: Workspace, url: str) -> str:
    """Return the address to open for what a caller wrote.

    Raises:
        OutsideBoundaryError: A file: address lies outside what may be read.
        ToolError: The address is empty or a javascript: one.
    """
    written = url.strip()
    if not written:
        raise ToolError("no address given")
    scheme = urlsplit(written).scheme.lower()
    if scheme == "javascript":
        raise ToolError("a javascript: address runs a script; use run_javascript")
    if scheme == "file":
        return space.resolve(url2pathname(urlsplit(written).path)).as_uri()
    if "://" in written or written.startswith(BARE_SCHEMES):
        return written
    return f"https://{written}"
