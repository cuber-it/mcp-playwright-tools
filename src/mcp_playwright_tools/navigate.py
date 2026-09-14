"""Where the browser is: opening pages, the history, tabs and frames."""

from __future__ import annotations

from urllib.parse import urlsplit
from urllib.request import url2pathname

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


async def where_am_i(browsing: Browsing) -> dict[str, str]:
    """Return the address and the title of the page that is open."""
    page = (await browsing.spot()).page
    return {"url": page.url, "title": await page.title()}


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
        return f"tabs {sorted(session.pages)}, active {session.active}"
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
    """Act inside the frame a selector names from now on, or in the page again."""
    session = await browsing.session()
    session.frame = selector or None
    return f"acting inside {selector!r}" if selector else "acting in the page itself"


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
