"""The refusals the tools raise.

Every refusal is a :class:`ToolError`, so a caller tells a deliberate refusal
from a crash by the class alone. What Playwright reports goes through
:func:`attempt` and arrives as a refusal that says what was being done.
"""

from __future__ import annotations

from collections.abc import Awaitable, Iterable

from playwright.async_api import Error as PlaywrightError


class ToolError(Exception):
    """A tool refused to do what it was asked."""


class OutsideBoundaryError(ToolError):
    """The path lies outside what this installation may touch."""


class NotPermittedError(ToolError):
    """No boundary permits the action, such as writing the grant file."""


class GrantError(ToolError):
    """A grant cannot be written, read or understood."""


def unknown(what: str, value: object, known: Iterable[str]) -> ToolError:
    """Return the refusal for a value that is not one of the known ones."""
    return ToolError(f"no such {what}: {value}; known are {', '.join(known)}")


def brief(err: PlaywrightError) -> str:
    """Return what Playwright says went wrong, without its call log."""
    return str(err).split("\nCall log:", 1)[0].strip()


async def attempt[T](pending: Awaitable[T], doing: str) -> T:
    """Wait for a Playwright call, turning its failure into a refusal.

    Raises:
        ToolError: Playwright failed; the message says what was being done.
    """
    try:
        return await pending
    except PlaywrightError as err:
        raise ToolError(f"could not {doing}: {brief(err)}") from err
