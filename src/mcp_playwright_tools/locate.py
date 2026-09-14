"""Pointing at elements on a page, by one way or another.

Every tool that works on an element takes ``by``: a CSS selector by default, or
one of the semantic ways Playwright offers, a role, visible text, a form label,
a placeholder or a test id. Whoever learns it once knows it everywhere.
"""

from __future__ import annotations

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator

from mcp_playwright_tools.errors import ToolError, unknown
from mcp_playwright_tools.pool import Spot

WAYS = ("css", "role", "text", "label", "placeholder", "testid")
MAX_TEXT = 80
DESCRIBE_SCRIPT = (
    "element => ({tag: element.tagName.toLowerCase(),"
    " text: (element.innerText || element.value || '').trim()})"
)


def locate(spot: Spot, target: str, by: str = "css", name: str = "") -> Locator:
    """Return a locator for what a caller pointed at; it may match nothing or many.

    ``name`` is the accessible name that tells apart elements of one role, used
    with ``by="role"`` only.

    Raises:
        ToolError: The target is empty, or ``by`` is not a way of pointing.
    """
    if not target:
        raise ToolError("nothing to point at: the target is empty")
    root = spot.root
    if by == "role":
        return root.get_by_role(target, name=name or None)
    finders = {
        "css": root.locator,
        "text": root.get_by_text,
        "label": root.get_by_label,
        "placeholder": root.get_by_placeholder,
        "testid": root.get_by_test_id,
    }
    finder = finders.get(by)
    if finder is None:
        raise unknown("way of pointing", by, WAYS)
    return finder(target)


async def existing(spot: Spot, target: str, by: str = "css") -> Locator:
    """Return the first element a caller pointed at.

    Raises:
        ToolError: Nothing matches, or the pointing itself is refused.
    """
    element = locate(spot, target, by)
    if await element.count() == 0:
        raise ToolError(f"nothing matches {by}={target!r}")
    return element.first


async def describe_one(element: Locator) -> str:
    """Return one line saying what an element is: its tag and its text or value."""
    try:
        seen = await element.evaluate(DESCRIBE_SCRIPT)
    except PlaywrightError:
        return "(element went away)"
    text = seen["text"]
    shortened = text[:MAX_TEXT] + ("…" if len(text) > MAX_TEXT else "")
    return f"<{seen['tag']}> {shortened}".rstrip()
