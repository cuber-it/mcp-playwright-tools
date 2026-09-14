"""What a context keeps a record of: console, network, dialogs and downloads.

A :class:`Record` listens to a context and its tabs from the moment they open,
so what happened before a tool asks is there to be read.
"""

from __future__ import annotations

import functools
from collections import deque
from dataclasses import dataclass, field

from playwright.async_api import (
    BrowserContext,
    ConsoleMessage,
    Dialog,
    Download,
    Page,
    Request,
    Response,
)
from playwright.async_api import Error as PlaywrightError

from mcp_playwright_tools.errors import brief

MAX_ENTRIES = 500


def _entries() -> deque[str]:
    """Return an empty log that lets its oldest entries go when it is full."""
    return deque(maxlen=MAX_ENTRIES)


@dataclass
class Record:
    """What happened in one context, and how its dialogs are answered.

    Attributes:
        console: Console messages and uncaught errors, each with its tab.
        network: Responses with their status, and failed requests.
        dialogs: Dialogs, each with its tab and how it was answered.
        downloads: Downloads, numbered by their place in the list.
        accept: Whether dialogs are accepted or dismissed.
        prompt_text: What an accepted prompt is answered with; empty for its
            own default.
    """

    console: deque[str] = field(default_factory=_entries)
    network: deque[str] = field(default_factory=_entries)
    dialogs: deque[str] = field(default_factory=_entries)
    downloads: list[Download] = field(default_factory=list)
    accept: bool = True
    prompt_text: str = ""

    def follow_context(self, context: BrowserContext) -> None:
        """Record the responses and failed requests of every tab in a context."""
        context.on("response", self._responded)
        context.on("requestfailed", self._failed)

    def follow_page(self, page: Page, tab: int) -> None:
        """Record what one tab logs, the dialogs it opens and what it downloads."""
        page.on("console", functools.partial(self._logged, tab))
        page.on("pageerror", functools.partial(self._raised, tab))
        page.on("dialog", functools.partial(self._answer, tab))
        page.on("download", self._downloaded)

    def _downloaded(self, download: Download) -> None:
        """Keep a download, to be listed and saved."""
        self.downloads.append(download)

    def _logged(self, tab: int, message: ConsoleMessage) -> None:
        """Record a console message."""
        self.console.append(f"tab {tab} {message.type}: {message.text}")

    def _raised(self, tab: int, error: PlaywrightError) -> None:
        """Record an error the page did not catch."""
        self.console.append(f"tab {tab} error: {error.message}")

    def _responded(self, response: Response) -> None:
        """Record a response."""
        self.network.append(
            f"{response.status} {response.request.method} {response.url}"
        )

    def _failed(self, request: Request) -> None:
        """Record a request that got no response."""
        self.network.append(f"failed {request.method} {request.url}: {request.failure}")

    async def _answer(self, tab: int, dialog: Dialog) -> None:
        """Accept or dismiss a dialog as set, and record it.

        A dialog that cannot be answered, because its tab went away meanwhile,
        is recorded as such; no caller is waiting to be told.
        """
        seen = f"tab {tab} {dialog.type}: {dialog.message}"
        try:
            if self.accept:
                await dialog.accept(self.prompt_text or dialog.default_value)
            else:
                await dialog.dismiss()
        except PlaywrightError as err:
            self.dialogs.append(f"{seen} -> not answered: {brief(err)}")
            return
        self.dialogs.append(f"{seen} -> {'accepted' if self.accept else 'dismissed'}")
