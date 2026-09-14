"""Getting things off a page: text, markup, attributes, links, pictures, events."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path

from mcp_playwright_tools.boundary import Access
from mcp_playwright_tools.errors import ToolError, attempt, unknown
from mcp_playwright_tools.locate import document, existing, locate
from mcp_playwright_tools.output import cut, listed
from mcp_playwright_tools.pool import Spot
from mcp_playwright_tools.workspace import Browsing

READABLE = ("text", "texts", "html", "attribute", "links")
WAITS = ("visible", "hidden", "url", "load", "response")
LOAD_STATES = ("load", "domcontentloaded", "networkidle")
MAX_LINK_TEXT = 80
LINKS_SCRIPT = (
    "root => Array.from(root.ownerDocument.querySelectorAll('a[href]'))"
    ".map(a => ({text: a.innerText.trim(), href: a.href}))"
)


@dataclass(frozen=True)
class Picture:
    """An encoded picture, to be handed out as a picture.

    Attributes:
        data: The encoded picture.
        image_format: Its format, for instance ``PNG``.
    """

    data: bytes
    image_format: str


async def read(
    browsing: Browsing,
    target: str = "",
    what: str = "text",
    attribute: str = "",
    by: str = "css",
) -> str:
    """Read text, the text of every match, markup, an attribute or the links.

    Without a target, text and html are those of the whole page, or of the
    frame acted in.

    Raises:
        ToolError: There is no such thing to read, nothing matches, or a
            needed target or attribute name is missing.
    """
    if what not in READABLE:
        raise unknown("thing to read", what, READABLE)
    spot = await browsing.spot()
    if what == "links":
        return await _links(spot)
    if what == "texts":
        return await _texts(spot, target, by)
    if what == "attribute":
        return await _attribute(spot, target, attribute, by)
    if what == "html" and not target:
        markup = document(spot).evaluate("root => root.outerHTML")
        return cut(await attempt(markup, "read the page"))
    element = await existing(spot, target or "body", by if target else "css")
    reading = f"read {by}={target!r}"
    if what == "html":
        return cut(await attempt(element.inner_html(), reading))
    return cut((await attempt(element.inner_text(), reading)).strip())


async def screenshot(
    browsing: Browsing,
    target: str = "",
    by: str = "css",
    full: bool = False,
    save_to: str = "",
) -> Picture | str:
    """Photograph the visible page, the whole page or one element.

    With ``save_to`` the PNG is written to that file instead of handed back;
    writing has to be allowed there, which is checked before the picture is
    taken.

    Returns:
        The picture, or a line naming the file written.

    Raises:
        OutsideBoundaryError: Writing may not reach ``save_to``.
        NotPermittedError: ``save_to`` would reach the grant file.
        ToolError: Nothing matches, the picture could not be taken, or the
            file could not be written.
    """
    space = browsing.space
    destination = space.resolve(save_to, Access.WRITE) if save_to else None
    spot = await browsing.spot()
    if target:
        element = await existing(spot, target, by)
        pending = element.screenshot(type="png")
    else:
        pending = spot.page.screenshot(type="png", full_page=full)
    data = await attempt(pending, "take the screenshot")
    if destination is None:
        return Picture(data, "PNG")
    return _stored(destination, data)


async def wait_until(
    browsing: Browsing,
    what: str,
    value: str = "",
    by: str = "css",
    seconds: float = 30.0,
) -> str:
    """Wait until an element shows or hides, an address, a load state or a response.

    Raises:
        ToolError: There is no such thing to wait for, a needed value is
            missing, or it did not happen in time.
    """
    if what not in WAITS:
        raise unknown("thing to wait for", what, WAITS)
    if seconds <= 0:
        raise ToolError(f"seconds has to be positive, not {seconds:g}")
    spot = await browsing.spot()
    page = spot.page
    timeout = seconds * 1000
    within = f"within {seconds:g}s"
    if what in ("visible", "hidden"):
        pending = locate(spot, value, by).wait_for(state=what, timeout=timeout)
        await attempt(pending, f"see {by}={value!r} {what} {within}")
        return f"{by}={value!r} is {what}"
    if what == "url":
        if not value:
            raise ToolError("waiting for an address needs a part of it in value")
        pending = page.wait_for_url(f"**{value}**", timeout=timeout)
        await attempt(pending, f"reach an address with {value!r} {within}")
        return f"at {page.url}"
    if what == "load":
        state = value or "load"
        if state not in LOAD_STATES:
            raise unknown("load state", state, LOAD_STATES)
        loading = page.wait_for_load_state(state, timeout=timeout)
        await attempt(loading, f"load {within}")
        return f"page reached {state}"
    pending = page.wait_for_event(
        "response", lambda answer: value in answer.url, timeout=timeout
    )
    answer = await attempt(pending, f"see a response from {value!r} {within}")
    return f"{answer.status} from {answer.url}"


async def _texts(spot: Spot, target: str, by: str) -> str:
    """Return the text of every match, one per line.

    Raises:
        ToolError: No target was named.
    """
    if not target:
        raise ToolError("reading every match needs a target")
    found = await attempt(locate(spot, target, by).all_inner_texts(), "read the texts")
    if not found:
        return f"nothing matches {by}={target!r}"
    return listed([line.strip() for line in found])


async def _attribute(spot: Spot, target: str, attribute: str, by: str) -> str:
    """Return one attribute of the first match, or say that it is not set.

    Raises:
        ToolError: No attribute was named, or nothing matches.
    """
    if not attribute:
        raise ToolError("reading an attribute needs its name, for instance href")
    element = await existing(spot, target, by)
    value = await attempt(element.get_attribute(attribute), f"read {attribute}")
    return value if value is not None else f"{attribute} is not set"


async def _links(spot: Spot) -> str:
    """Return every link in the page or frame acted in, as text and address."""
    found = await attempt(document(spot).evaluate(LINKS_SCRIPT), "list the links")
    if not found:
        return "no links on this page"
    return listed(
        [
            f"{item['text'][:MAX_LINK_TEXT] or '(no text)'} -> {item['href']}"
            for item in found
        ]
    )


def _stored(path: Path, data: bytes) -> str:
    """Write picture data to a file, so that a failed write leaves nothing behind.

    Raises:
        ToolError: The file could not be written.
    """
    partial = path.with_name(f".{path.name}.partial")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial.write_bytes(data)
        partial.replace(path)
    except OSError as err:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise ToolError(f"could not write {path}: {err}") from err
    return f"wrote {path}, {len(data)} bytes"
