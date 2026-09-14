"""Acting on a page: clicking, filling, keys, dropdowns, dragging, files, scripts."""

from __future__ import annotations

import functools
from typing import Any

from mcp_playwright_tools.errors import ToolError, attempt, unknown
from mcp_playwright_tools.locate import locate
from mcp_playwright_tools.workspace import Browsing

SCROLLS = {
    "down": "window.scrollBy(0, window.innerHeight)",
    "up": "window.scrollBy(0, -window.innerHeight)",
    "top": "window.scrollTo(0, 0)",
    "bottom": "window.scrollTo(0, document.body.scrollHeight)",
}


async def click(
    browsing: Browsing, target: str, by: str = "css", name: str = ""
) -> str:
    """Click an element once Playwright finds it can be clicked.

    Raises:
        ToolError: The pointing is refused, or the click could not be done.
    """
    element = locate(await browsing.spot(), target, by, name)
    await attempt(element.click(), f"click {by}={target!r}")
    return f"clicked {by}={target!r}"


async def act_on(browsing: Browsing, action: str, target: str, by: str = "css") -> str:
    """Double-click, right-click, hover, focus, check, uncheck, clear or scroll to.

    Raises:
        ToolError: There is no such action, or it could not be done.
    """
    element = locate(await browsing.spot(), target, by)
    doers = {
        "double_click": element.dblclick,
        "right_click": functools.partial(element.click, button="right"),
        "hover": element.hover,
        "focus": element.focus,
        "check": element.check,
        "uncheck": element.uncheck,
        "clear": element.clear,
        "scroll_to": element.scroll_into_view_if_needed,
    }
    doer = doers.get(action)
    if doer is None:
        raise unknown("action", action, doers)
    await attempt(doer(), f"{action} {by}={target!r}")
    return f"{action} on {by}={target!r}"


async def fill(
    browsing: Browsing,
    target: str,
    value: str,
    by: str = "label",
    typed: bool = False,
) -> str:
    """Put text into a field, at once or, with ``typed``, key by key.

    Raises:
        ToolError: The field could not be filled.
    """
    element = locate(await browsing.spot(), target, by)
    doing = f"fill {by}={target!r}"
    if typed:
        await attempt(element.clear(), doing)
        await attempt(element.press_sequentially(value), doing)
    else:
        await attempt(element.fill(value), doing)
    return f"filled {by}={target!r}"


async def press_key(
    browsing: Browsing, key: str, target: str = "", by: str = "css"
) -> str:
    """Press a key on an element, or on the page when no target is named.

    Raises:
        ToolError: The key could not be pressed.
    """
    spot = await browsing.spot()
    if target:
        pending = locate(spot, target, by).press(key)
    else:
        pending = spot.page.keyboard.press(key)
    await attempt(pending, f"press {key}")
    return f"pressed {key}"


async def choose(
    browsing: Browsing,
    target: str,
    option: str,
    by: str = "label",
    text: bool = False,
) -> str:
    """Choose an option of a dropdown by its value, or with ``text`` by its text.

    Raises:
        ToolError: There is no such option, or it could not be chosen.
    """
    element = locate(await browsing.spot(), target, by)
    pending = (
        element.select_option(label=option) if text else element.select_option(option)
    )
    chosen = await attempt(pending, f"choose {option!r} in {by}={target!r}")
    return f"chose {chosen} in {by}={target!r}"


async def drag(
    browsing: Browsing, source: str, destination: str, by: str = "css"
) -> str:
    """Drag one element onto another, both found the same way.

    Raises:
        ToolError: The drag could not be done.
    """
    spot = await browsing.spot()
    moving = locate(spot, source, by).drag_to(locate(spot, destination, by))
    await attempt(moving, f"drag {source!r} to {destination!r}")
    return f"dragged {source!r} to {destination!r}"


async def scroll(browsing: Browsing, amount: str = "down") -> str:
    """Scroll the page down, up, to the top or to the bottom.

    Raises:
        ToolError: There is no such way of scrolling.
    """
    script = SCROLLS.get(amount)
    if script is None:
        raise unknown("way of scrolling", amount, SCROLLS)
    page = (await browsing.spot()).page
    await attempt(page.evaluate(script), f"scroll {amount}")
    return f"scrolled {amount}"


async def attach_files(
    browsing: Browsing, target: str, paths: str, by: str = "css"
) -> str:
    """Put files into a file input; several paths are separated by commas.

    Relative paths start in the working directory, and every file has to lie
    where reading may reach.

    Raises:
        OutsideBoundaryError: A file lies outside what may be read.
        ToolError: No file was named, one does not exist, or they could not be
            attached.
    """
    named = [item.strip() for item in paths.split(",") if item.strip()]
    if not named:
        raise ToolError("no file named")
    files = [browsing.space.resolve(item) for item in named]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise ToolError(f"no such file: {', '.join(missing)}")
    element = locate(await browsing.spot(), target, by)
    await attempt(element.set_input_files(files), f"attach files to {by}={target!r}")
    return f"attached {', '.join(str(path) for path in files)}"


async def run_javascript(browsing: Browsing, script: str) -> Any:
    """Run JavaScript in the page and return what it gives back.

    Raises:
        NotPermittedError: Scripts are switched off; the message names the
            grant that switches them on.
        ToolError: The script failed.
    """
    browsing.space.permit_execute()
    page = (await browsing.spot()).page
    return await attempt(page.evaluate(script), "run the script")
