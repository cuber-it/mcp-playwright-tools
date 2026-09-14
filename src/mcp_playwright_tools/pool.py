"""Browsers, contexts and tabs, and when to let go of them.

A caller names a context. Each name gets its own browser context, with its own
cookies and storage, inside one browser, because a context is cheap and a
browser is not. A context nobody has used for a while is closed with
everything in it, and when the last one goes, so does the browser.

An incoming request carries nothing a context could be told apart by, so the
name is a parameter of every tool.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    FrameLocator,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError

from mcp_playwright_tools.errors import ToolError, attempt, brief, unknown

DEFAULT_CONTEXT = "default"
BROWSERS = ("chromium", "firefox", "webkit")
DEFAULT_TIMEOUT = 30.0
DEFAULT_IDLE = 900.0
SWEEP_SECONDS = 60.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """How the browser is started and how long its parts are kept.

    Attributes:
        browser: Which engine, one of :data:`BROWSERS`.
        channel: A browser installed on the machine, such as ``chrome``, or
            empty for the one Playwright brings along.
        headless: Whether the browser runs without a window.
        timeout: Seconds a single action may take.
        idle: Seconds a context may go unused before it is closed; 0 keeps
            contexts until they are closed by hand.
    """

    browser: str = "chromium"
    channel: str = ""
    headless: bool = True
    timeout: float = DEFAULT_TIMEOUT
    idle: float = DEFAULT_IDLE

    def __post_init__(self) -> None:
        """Refuse settings the browser cannot be run with.

        Raises:
            ToolError: The engine is unknown, the timeout not positive, or the
                idle time negative.
        """
        if self.browser not in BROWSERS:
            raise unknown("browser", self.browser, BROWSERS)
        if self.timeout <= 0:
            raise ToolError(f"timeout has to be positive, not {self.timeout:g}")
        if self.idle < 0:
            raise ToolError(f"idle cannot be negative, not {self.idle:g}")

    @classmethod
    def read(cls, config: dict[str, Any]) -> Settings:
        """Return the settings a configuration mapping names.

        Raises:
            ToolError: A setting is unusable.
        """
        try:
            timeout = float(config.get("timeout", DEFAULT_TIMEOUT))
            idle = float(config.get("idle", DEFAULT_IDLE))
        except (TypeError, ValueError) as err:
            raise ToolError(f"timeout and idle have to be numbers: {err}") from err
        return cls(
            browser=str(config.get("browser", "chromium")),
            channel=str(config.get("channel", "")),
            headless=bool(config.get("headless", True)),
            timeout=timeout,
            idle=idle,
        )


@dataclass
class Session:
    """One named context and the tabs open in it.

    Attributes:
        context: The browser context, isolated from the others.
        pages: Open tabs by their number.
        active: The tab the tools act on.
        next_tab: Number the next tab gets.
        frame: Selector of the frame the tools act in, if any.
        touched: When it was last used, as a monotonic reading.
    """

    context: BrowserContext
    pages: dict[int, Page] = field(default_factory=dict)
    active: int = 0
    next_tab: int = 1
    frame: str | None = None
    touched: float = field(default_factory=time.monotonic)

    def idle_for(self) -> float:
        """Return how many seconds nobody has used this context."""
        return time.monotonic() - self.touched


@dataclass(frozen=True)
class Spot:
    """Where a call acts: the active tab of a context, and the frame in it.

    It holds the context rather than the tab and reads the tab afresh every
    time, so a spot kept across a tab switch or a frame change follows along.

    Attributes:
        session: The named context this belongs to.
    """

    session: Session

    @property
    def page(self) -> Page:
        """Return the active tab.

        Raises:
            ToolError: The active tab is not open.
        """
        page = self.session.pages.get(self.session.active)
        if page is None or page.is_closed():
            raise ToolError(f"tab {self.session.active} is not open")
        return page

    @property
    def root(self) -> Page | FrameLocator:
        """Return what elements are looked for in: the tab, or a frame in it."""
        frame = self.session.frame
        return self.page.frame_locator(frame) if frame else self.page

    @property
    def context(self) -> BrowserContext:
        """Return the browser context, which holds the cookies."""
        return self.session.context


class BrowserPool:
    """The browser, the named contexts in it, and the sweeper that ends them."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Bind the pool to its settings; nothing is started yet."""
        self.settings = settings or Settings()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._sessions: dict[str, Session] = {}
        self._sweeper: asyncio.Task[None] | None = None

    async def spot(self, name: str = DEFAULT_CONTEXT) -> Spot:
        """Return where a call in the named context acts, opening what is missing.

        Raises:
            ToolError: The browser or a tab could not be opened.
        """
        session = await self.session(name)
        page = session.pages.get(session.active)
        if page is None or page.is_closed():
            session.pages[session.active] = await self._new_page(session)
        return Spot(session)

    async def session(self, name: str = DEFAULT_CONTEXT) -> Session:
        """Return the named context, opening it if it is not there.

        Raises:
            ToolError: The browser could not be started.
        """
        self._forget_lost_browser()
        found = self._sessions.get(name)
        if found is None:
            browser = await self._started()
            context = await attempt(browser.new_context(), f"open context {name!r}")
            found = Session(context=context)
            self._sessions[name] = found
            logger.info("browser context %r opened", name)
        found.touched = time.monotonic()
        self._start_sweeper()
        return found

    def sessions(self) -> dict[str, Session]:
        """Return the open contexts by name, without counting that as using them."""
        self._forget_lost_browser()
        return dict(sorted(self._sessions.items()))

    async def open_tab(self, name: str) -> int:
        """Open another tab in a context and make it the active one.

        Returns:
            The new tab's number.
        """
        session = await self.session(name)
        number = session.next_tab
        session.pages[number] = await self._new_page(session)
        session.active = number
        session.next_tab += 1
        return number

    async def switch_tab(self, name: str, tab: int) -> None:
        """Make another open tab the one the tools act on.

        Raises:
            ToolError: That tab is not open.
        """
        session = await self.session(name)
        if tab not in session.pages:
            raise ToolError(f"no tab {tab}; open: {sorted(session.pages)}")
        session.active = tab

    async def close_tab(self, name: str, tab: int) -> None:
        """Close one tab; when it was the active one, the lowest other takes over.

        Raises:
            ToolError: That tab is not open, or it could not be closed.
        """
        session = await self.session(name)
        page = session.pages.get(tab)
        if page is None:
            raise ToolError(f"no tab {tab}; open: {sorted(session.pages)}")
        await attempt(page.close(), f"close tab {tab}")
        del session.pages[tab]
        if session.active == tab:
            session.active = min(session.pages, default=0)

    async def close(self, name: str) -> bool:
        """Close one context with its tabs, and the browser with the last one.

        Returns:
            Whether there was one to close.

        Raises:
            ToolError: It did not close cleanly. It is gone from the pool all
                the same and ends with the browser.
        """
        session = self._sessions.pop(name, None)
        if session is None:
            return False
        clean = await self._shut(name, session)
        await self._stop_if_empty()
        if not clean:
            raise ToolError(
                f"context {name!r} did not close cleanly; it is gone from the list "
                "and ends with the browser"
            )
        return True

    async def close_all(self) -> int:
        """Close every context and the browser.

        Returns:
            How many contexts were open.
        """
        names = list(self._sessions)
        for name in names:
            await self._shut(name, self._sessions.pop(name))
        await self._stop_if_empty()
        return len(names)

    async def sweep(self) -> list[str]:
        """Close what nobody has used for longer than the idle time.

        Returns:
            The names that were closed.
        """
        if self.settings.idle <= 0:
            return []
        stale = [
            name
            for name, session in self._sessions.items()
            if session.idle_for() > self.settings.idle
        ]
        for name in stale:
            logger.info("browser context %r closed after being idle", name)
            await self._shut(name, self._sessions.pop(name))
        if stale:
            await self._stop_if_empty()
        return stale

    def _forget_lost_browser(self) -> None:
        """Drop the contexts of a browser that went away; the next call starts anew."""
        if self._browser is not None and not self._browser.is_connected():
            logger.warning("the browser went away, and its contexts with it")
            self._sessions.clear()
            self._browser = None

    async def _started(self) -> Browser:
        """Return the browser, starting Playwright and the browser if needed.

        Raises:
            ToolError: It could not be started.
        """
        if self._browser is not None:
            return self._browser
        settings = self.settings
        options: dict[str, Any] = {"headless": settings.headless}
        if settings.channel:
            options["channel"] = settings.channel
        named = settings.channel or settings.browser
        try:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            launcher = getattr(self._playwright, settings.browser)
            self._browser = await launcher.launch(**options)
        except PlaywrightError as err:
            await self._stop_if_empty()
            raise ToolError(f"could not start {named}: {brief(err)}") from err
        logger.info("browser %s started, headless=%s", named, settings.headless)
        return self._browser

    async def _new_page(self, session: Session) -> Page:
        """Open a tab in a context with the action timeout set.

        Raises:
            ToolError: The tab could not be opened.
        """
        page = await attempt(session.context.new_page(), "open a tab")
        page.set_default_timeout(self.settings.timeout * 1000)
        return page

    async def _shut(self, name: str, session: Session) -> bool:
        """Close one context with its tabs.

        Returns:
            Whether it closed; a failure is logged, because a context that will
            not close must not keep the others open.
        """
        try:
            await session.context.close()
        except PlaywrightError:
            logger.exception("could not close context %r", name)
            return False
        return True

    async def _stop_if_empty(self) -> None:
        """Stop the browser, Playwright and the sweeper once no context is left."""
        if self._sessions or self._playwright is None:
            return
        try:
            if self._browser is not None and self._browser.is_connected():
                await self._browser.close()
            await self._playwright.stop()
        except PlaywrightError:
            logger.exception("could not stop the browser")
        self._browser = None
        self._playwright = None
        if self._sweeper is not None and self._sweeper is not asyncio.current_task():
            self._sweeper.cancel()
        logger.info("browser stopped, no context left")

    def _start_sweeper(self) -> None:
        """Start the task that closes idle contexts, unless it runs or is off."""
        running = self._sweeper is not None and not self._sweeper.done()
        if self.settings.idle <= 0 or running:
            return
        self._sweeper = asyncio.get_running_loop().create_task(self._sweeping())

    async def _sweeping(self) -> None:
        """Sweep every so often until no context is left."""
        while self._sessions:
            await asyncio.sleep(min(SWEEP_SECONDS, self.settings.idle))
            await self.sweep()
