"""Finding out what is on a page: matches, one element, what can be done."""

from __future__ import annotations

from typing import Any

from mcp_playwright_tools.errors import ToolError, attempt
from mcp_playwright_tools.locate import describe_one, document, locate
from mcp_playwright_tools.output import cut, listed
from mcp_playwright_tools.workspace import Browsing

MAX_LISTED = 20
ATTRIBUTES_SCRIPT = (
    "element => Object.fromEntries("
    "Array.from(element.attributes).map(a => [a.name, a.value]))"
)
# Rendered boxes rather than offsetParent: that is null for fixed elements too,
# and cookie banners and headers are fixed.
INTERACTIVE_SCRIPT = (
    "root => Array.from(root.ownerDocument.querySelectorAll("
    "'a[href],button,input,select,textarea,[role],[onclick]'))"
    ".filter(e => e.getClientRects().length > 0)"
    ".map(e => ({tag: e.tagName.toLowerCase(), type: e.type || '',"
    " text: (e.innerText || e.value || e.placeholder || '').trim().slice(0, 60),"
    " id: e.id || '', role: e.getAttribute('role') || ''}))"
)


async def find(browsing: Browsing, target: str, by: str = "css", name: str = "") -> str:
    """Return how many elements match and what the first twenty of them are.

    Raises:
        ToolError: The pointing is refused.
    """
    matches = locate(await browsing.spot(), target, by, name)
    count = await matches.count()
    if count == 0:
        return f"nothing matches {by}={target!r}"
    rows = [
        f"{index + 1}. {await describe_one(matches.nth(index))}"
        for index in range(min(count, MAX_LISTED))
    ]
    if count > MAX_LISTED:
        rows.append(f"[... {count - MAX_LISTED} more]")
    return f"{count} match {by}={target!r}:\n" + "\n".join(rows)


async def describe(browsing: Browsing, target: str, by: str = "css") -> dict[str, Any]:
    """Return what the first match is: tag and text, attributes, state, matches.

    Raises:
        ToolError: Nothing matches, or the element went away while looking.
    """
    matches = locate(await browsing.spot(), target, by)
    count = await matches.count()
    if count == 0:
        raise ToolError(f"nothing matches {by}={target!r}")
    first = matches.first
    looked = f"describe {by}={target!r}"
    return {
        "describes": await describe_one(first),
        "attributes": await attempt(first.evaluate(ATTRIBUTES_SCRIPT), looked),
        "visible": await attempt(first.is_visible(), looked),
        "enabled": await attempt(first.is_enabled(), looked),
        "matches": count,
    }


async def what_can_i_do(browsing: Browsing) -> str:
    """Return the visible things one can act on, in the page or frame acted in."""
    root = document(await browsing.spot())
    found = await attempt(root.evaluate(INTERACTIVE_SCRIPT), "list the controls")
    if not found:
        return "nothing to act on here"
    rows = []
    for item in found:
        marks = [f"<{item['tag']}>"]
        if item["type"]:
            marks.append(f"type={item['type']}")
        if item["id"]:
            marks.append(f"#{item['id']}")
        if item["role"]:
            marks.append(f"role={item['role']}")
        rows.append(f"{' '.join(marks)} {item['text']}".rstrip())
    return listed(rows)


async def outline(browsing: Browsing) -> str:
    """Return the accessibility tree of the page or the frame acted in."""
    body = (await browsing.spot()).root.locator("body")
    return cut(await attempt(body.aria_snapshot(), "read the accessibility tree"))
