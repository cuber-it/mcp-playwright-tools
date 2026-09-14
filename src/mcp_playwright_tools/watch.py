"""What happened in a context: its logs, how dialogs are answered, its downloads."""

from __future__ import annotations

from pathlib import Path

from mcp_playwright_tools.boundary import Access
from mcp_playwright_tools.errors import ToolError, attempt, unknown
from mcp_playwright_tools.output import cut, latest, listed
from mcp_playwright_tools.workspace import Browsing

LOGS = ("console", "network", "dialogs")
LOG_ACTIONS = ("read", "clear")
ANSWERS = ("accept", "dismiss")
DOWNLOAD_ACTIONS = ("list", "save")


async def logs(
    browsing: Browsing, kind: str = "console", action: str = "read", contains: str = ""
) -> str:
    """Read the console, network or dialog log of a context, or clear it.

    Reading gives the latest entries, oldest first, and only those containing
    ``contains`` when it is given.

    Raises:
        ToolError: There is no such log or action.
    """
    if kind not in LOGS:
        raise unknown("log", kind, LOGS)
    if action not in LOG_ACTIONS:
        raise unknown("action", action, LOG_ACTIONS)
    record = (await browsing.session()).record
    entries = {
        "console": record.console,
        "network": record.network,
        "dialogs": record.dialogs,
    }[kind]
    if action == "clear":
        entries.clear()
        return f"{kind} log cleared"
    found = [entry for entry in entries if contains in entry]
    if not found:
        return f"no {kind} entries" + (f" with {contains!r}" if contains else "")
    return cut(latest(found))


async def dialogs(browsing: Browsing, answer: str = "accept", text: str = "") -> str:
    """Set how the dialogs of a context are answered from now on.

    Raises:
        ToolError: There is no such answer, or a prompt answer was given with
            dismiss.
    """
    if answer not in ANSWERS:
        raise unknown("answer", answer, ANSWERS)
    if text and answer == "dismiss":
        raise ToolError("an answer to prompts only goes with accept")
    record = (await browsing.session()).record
    record.accept = answer == "accept"
    record.prompt_text = text
    if not record.accept:
        return "dialogs are dismissed"
    if text:
        return f"dialogs are accepted, prompts answered with {text!r}"
    return "dialogs are accepted"


async def downloads(
    browsing: Browsing, action: str = "list", number: int = -1, save_to: str = ""
) -> str:
    """List the downloads of a context, or save one of them.

    ``save_to`` names a file, or a directory the download keeps its own name
    in. Writing has to be allowed there, which is checked first.

    Raises:
        OutsideBoundaryError: Writing may not reach ``save_to``.
        NotPermittedError: ``save_to`` would reach the grant file.
        ToolError: There is no such action or download, ``save_to`` is
            missing, or the download could not be saved.
    """
    if action not in DOWNLOAD_ACTIONS:
        raise unknown("action", action, DOWNLOAD_ACTIONS)
    if action == "list":
        found = (await browsing.session()).record.downloads
        if not found:
            return "no downloads"
        return listed(
            [
                f"{place}: {download.suggested_filename} - {download.url}"
                for place, download in enumerate(found)
            ]
        )
    if not save_to:
        raise ToolError("saving a download needs save_to")
    destination = browsing.space.resolve(save_to, Access.WRITE)
    found = (await browsing.session()).record.downloads
    if not 0 <= number < len(found):
        raise ToolError(f"no download {number}; there are {len(found)}")
    download = found[number]
    if destination.is_dir():
        # Checked again: the name may already be a link leading elsewhere.
        named = destination / Path(download.suggested_filename).name
        destination = browsing.space.resolve(str(named), Access.WRITE)
    await attempt(download.save_as(destination), f"save download {number}")
    return f"saved download {number} to {destination}"
