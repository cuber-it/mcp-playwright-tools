"""What a context carries and lets through: cookies, storage, requests, contexts."""

from __future__ import annotations

import json

from playwright.async_api import Route

from mcp_playwright_tools.errors import ToolError, attempt, unknown
from mcp_playwright_tools.pool import Spot
from mcp_playwright_tools.workspace import Browsing, Workspace

KINDS = ("cookies", "local")
STORE_ACTIONS = ("get", "set", "clear")
ROUTE_ACTIONS = ("mock", "abort", "clear")
CONTEXT_ACTIONS = ("list", "close")
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


async def contexts(space: Workspace, action: str = "list", name: str = "") -> str:
    """List the open contexts, or close one, or close all and stop the browser.

    Raises:
        ToolError: There is no such action, or a context did not close cleanly.
    """
    pool = space.pool
    if action == "list":
        found = pool.sessions()
        if not found:
            return "no browser context is open"
        return "\n".join(
            f"{named}: {len(session.pages)} tab(s), active {session.active}, "
            f"idle {session.idle_for():.0f}s"
            for named, session in found.items()
        )
    if action == "close":
        if not name:
            return f"closed {await pool.close_all()} context(s), browser stopped"
        closed = await pool.close(name)
        return f"closed context {name!r}" if closed else f"no context {name!r}"
    raise unknown("action", action, CONTEXT_ACTIONS)


async def _cookies(spot: Spot, action: str, payload: str) -> str:
    """Get, set or clear the cookies of a context.

    Raises:
        ToolError: The cookies to set are not JSON objects, or the browser
            refuses them.
    """
    if action == "get":
        found = await attempt(spot.context.cookies(), "read the cookies")
        return json.dumps(found[:MAX_COOKIES], indent=2) if found else "no cookies"
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
        return str(found) if found is not None else f"{key} is not set"
    if action == "get":
        everything = await attempt(page.evaluate("() => ({...localStorage})"), reaching)
        return json.dumps(everything, indent=2) if everything else "storage is empty"
    if action == "set":
        if not key:
            raise ToolError("setting a local entry needs its key")
        script = "([k, v]) => localStorage.setItem(k, v)"
        await attempt(page.evaluate(script, [key, value]), reaching)
        return f"set {key}"
    await attempt(page.evaluate("() => localStorage.clear()"), reaching)
    return "storage cleared"
