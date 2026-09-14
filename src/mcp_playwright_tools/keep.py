"""What a context carries and lets through: cookies, storage, requests, contexts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.async_api import Route

from mcp_playwright_tools.boundary import Access
from mcp_playwright_tools.errors import ToolError, attempt, unknown
from mcp_playwright_tools.output import cut, stored
from mcp_playwright_tools.pool import BrowserPool, Spot
from mcp_playwright_tools.workspace import Browsing, Workspace

KINDS = ("cookies", "local")
STORE_ACTIONS = ("get", "set", "clear")
ROUTE_ACTIONS = ("mock", "abort", "clear")
CONTEXT_ACTIONS = ("list", "open", "save", "close")
# A state file holds the cookies of a login.
PRIVATE = 0o600
MAX_COOKIES = 100


async def storage(
    browsing: Browsing,
    kind: str = "cookies",
    action: str = "get",
    key: str = "",
    value: str = "",
) -> str:
    """Get, set or clear the cookies of a context or the local storage of its page.

    Cookies to set are a JSON object or array in ``value``; a local entry is
    named by ``key`` and holds ``value``.

    Raises:
        ToolError: There is no such kind or action, the cookies are unusable,
            or the page will not give its storage up.
    """
    if kind not in KINDS:
        raise unknown("kind of storage", kind, KINDS)
    if action not in STORE_ACTIONS:
        raise unknown("action", action, STORE_ACTIONS)
    spot = await browsing.spot()
    if kind == "cookies":
        return await _cookies(spot, action, value)
    return await _local(spot, action, key, value)


async def intercept(
    browsing: Browsing,
    action: str,
    pattern: str,
    body: str = "",
    status: int = 200,
) -> str:
    """Answer requests of the page with ``body`` and ``status``, block them, or stop.

    Raises:
        ToolError: There is no such action, or no pattern was named.
    """
    if action not in ROUTE_ACTIONS:
        raise unknown("action", action, ROUTE_ACTIONS)
    if not pattern:
        raise ToolError("intercepting needs a pattern, for instance **/api/**")
    page = (await browsing.spot()).page
    if action == "mock":

        async def answer(route: Route) -> None:
            await route.fulfill(status=status, body=body)

        await attempt(page.route(pattern, answer), f"mock {pattern}")
        return f"mocking {pattern} with {status}"
    if action == "abort":

        async def block(route: Route) -> None:
            await route.abort()

        await attempt(page.route(pattern, block), f"block {pattern}")
        return f"blocking {pattern}"
    await attempt(page.unroute(pattern), f"stop interfering with {pattern}")
    return f"no longer interfering with {pattern}"


async def contexts(
    space: Workspace,
    action: str = "list",
    name: str = "",
    device: str = "",
    state: str = "",
) -> str:
    """List, open, save or close contexts.

    ``open`` starts the context ``name``, passing for ``device`` and holding the
    cookies and storage of the file ``state`` when they are given; ``save``
    writes those of an open context to ``state``. ``close`` without a name
    closes every context and the browser.

    Raises:
        OutsideBoundaryError: The state file lies where it may not be read or
            written.
        NotPermittedError: Saving would write the grant file.
        ToolError: There is no such action, a needed name or state file is
            missing or unusable, or a context could not be opened, saved or
            closed cleanly.
    """
    pool = space.pool
    if action == "list":
        return _listing(pool)
    if action == "open":
        return await _opening(space, name, device, state)
    if action == "save":
        return await _saving(space, name, state)
    if action == "close":
        if not name:
            return f"closed {await pool.close_all()} context(s), browser stopped"
        closed = await pool.close(name)
        return f"closed context {name!r}" if closed else f"no context {name!r}"
    raise unknown("action", action, CONTEXT_ACTIONS)


def _listing(pool: BrowserPool) -> str:
    """Return the browser, then each open context with its tabs and idle time."""
    found = pool.sessions()
    if not found:
        return "no browser context is open"
    rows = [
        f"{named}: {len(session.pages)} tab(s), active {session.active}, "
        f"idle {session.idle_for():.0f}s"
        for named, session in found.items()
    ]
    return "\n".join([pool.about(), *rows])


async def _opening(space: Workspace, name: str, device: str, state: str) -> str:
    """Open a context, as a device and from a state file as far as they are given.

    Raises:
        OutsideBoundaryError: The state file lies where it may not be read.
        ToolError: The name is missing, the state file cannot be read, or the
            context could not be opened.
    """
    if not name:
        raise ToolError("opening a context needs a name")
    source = space.resolve(state) if state else None
    await space.pool.open(name, device, None if source is None else _state(source))
    said = f"opened context {name!r}"
    if device:
        said += f" as {device}"
    if source is not None:
        said += f" with the state from {source}"
    return said


async def _saving(space: Workspace, name: str, state: str) -> str:
    """Write the cookies and storage of an open context to a file only its owner reads.

    Raises:
        OutsideBoundaryError: The file lies where it may not be written.
        NotPermittedError: The file would be the grant file.
        ToolError: The name or the file is missing, no such context is open,
            or the state could not be taken or written.
    """
    if not name or not state:
        raise ToolError("saving a context needs its name and a state file")
    destination = space.resolve(state, Access.WRITE)
    session = space.pool.sessions().get(name)
    if session is None:
        raise ToolError(f"no context {name!r}")
    held = await attempt(session.context.storage_state(), f"save context {name!r}")
    stored(destination, json.dumps(held, indent=2).encode(), PRIVATE)
    return f"saved context {name!r} to {destination}"


def _state(source: Path) -> dict[str, Any]:
    """Return what a state file holds.

    Raises:
        ToolError: The file cannot be read or holds no JSON.
    """
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ToolError(f"could not read the state file {source}: {err}") from err


async def _cookies(spot: Spot, action: str, payload: str) -> str:
    """Get, set or clear the cookies of a context.

    Raises:
        ToolError: The cookies to set are not JSON objects, or the browser
            refuses them.
    """
    if action == "get":
        found = await attempt(spot.context.cookies(), "read the cookies")
        if not found:
            return "no cookies"
        shown = json.dumps(found[:MAX_COOKIES], indent=2)
        if len(found) > MAX_COOKIES:
            shown += f"\n[... {len(found) - MAX_COOKIES} more]"
        return shown
    if action == "clear":
        await attempt(spot.context.clear_cookies(), "clear the cookies")
        return "cookies cleared"
    try:
        decoded = json.loads(payload)
    except ValueError as err:
        raise ToolError(f"cookies to set have to be JSON: {err}") from err
    wanted = decoded if isinstance(decoded, list) else [decoded]
    if not wanted or not all(isinstance(cookie, dict) for cookie in wanted):
        raise ToolError(
            "cookies to set are JSON objects with name, value and domain or url"
        )
    await attempt(spot.context.add_cookies(wanted), "set the cookies")
    return f"set {len(wanted)} cookie(s)"


async def _local(spot: Spot, action: str, key: str, value: str) -> str:
    """Get, set or clear the local storage of the page that is open.

    Raises:
        ToolError: A key is missing for set, or the page will not give its
            storage up, as a page opened from a data: address does.
    """
    page = spot.page
    reaching = "reach the local storage"
    if action == "get" and key:
        entry = page.evaluate("k => localStorage.getItem(k)", key)
        found = await attempt(entry, reaching)
        return cut(str(found)) if found is not None else f"{key} is not set"
    if action == "get":
        everything = await attempt(page.evaluate("() => ({...localStorage})"), reaching)
        return (
            cut(json.dumps(everything, indent=2)) if everything else "storage is empty"
        )
    if action == "set":
        if not key:
            raise ToolError("setting a local entry needs its key")
        script = "([k, v]) => localStorage.setItem(k, v)"
        await attempt(page.evaluate(script, [key, value]), reaching)
        return f"set {key}"
    await attempt(page.evaluate("() => localStorage.clear()"), reaching)
    return "storage cleared"
