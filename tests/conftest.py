"""Fixtures shared by the test modules.

The browser tests drive a real browser: an installed one named by
``MCP_PLAYWRIGHT_TEST_CHANNEL``, ``chrome`` unless set, or with the variable set
empty the one Playwright brings along. One browser serves the whole run on one
event loop; each test works in contexts of its own, closed after it.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from loopback import Issuer, Site, serve_issuer, serve_site
from mcp_playwright_tools import Boundary, BrowserPool, Settings, Workspace, navigate

CHANNEL = os.environ.get("MCP_PLAYWRIGHT_TEST_CHANNEL", "chrome")
TIMEOUT = 3.0
# Open for the whole run, so the browser does not stop and start again each
# time a test closes its last context.
KEEPER = "keeper"

Run = Callable[[Awaitable[Any]], Any]

EXPECTED = {
    "open_url",
    "go",
    "where_am_i",
    "tabs",
    "use_frame",
    "find",
    "describe",
    "what_can_i_do",
    "outline",
    "click",
    "act_on",
    "fill",
    "press_key",
    "choose",
    "drag",
    "scroll",
    "attach_files",
    "run_javascript",
    "read",
    "screenshot",
    "wait_until",
    "storage",
    "intercept",
    "contexts",
}


@pytest.fixture
def issuer() -> Iterator[Issuer]:
    """Return a stand-in authorization server that rejects every token."""
    with serve_issuer() as running:
        yield running


@pytest.fixture(scope="session")
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Return the event loop the browser lives on for the whole run."""
    running = asyncio.new_event_loop()
    yield running
    running.close()


@pytest.fixture(scope="session")
def run(loop: asyncio.AbstractEventLoop) -> Run:
    """Return a function that runs one coroutine to its end on the shared loop."""
    return loop.run_until_complete


@pytest.fixture(scope="session")
def browser(run: Run) -> Iterator[BrowserPool]:
    """Return the pool with the one browser the run shares."""
    pool = BrowserPool(Settings(channel=CHANNEL, timeout=TIMEOUT, idle=0))
    run(pool.session(KEEPER))
    yield pool
    run(pool.close_all())


@pytest.fixture(scope="session")
def site() -> Iterator[Site]:
    """Return the web site on the loopback interface."""
    with serve_site() as serving:
        yield serving


@pytest.fixture
def space(tmp_path: Path, browser: BrowserPool, run: Run) -> Iterator[Workspace]:
    """Return a workspace on the shared browser, without limits, in tmp_path."""
    yield Workspace(working_dir=tmp_path, pool=browser, state_dir=tmp_path / "state")
    for name in browser.sessions():
        if name != KEEPER:
            run(browser.close(name))


@pytest.fixture
def lone(tmp_path: Path, run: Run) -> Iterator[Workspace]:
    """Return a workspace with a browser of its own, stopped after the test."""
    pool = BrowserPool(Settings(channel=CHANNEL, timeout=TIMEOUT, idle=0))
    yield Workspace(working_dir=tmp_path, pool=pool)
    run(pool.close_all())


@pytest.fixture
def fenced(space: Workspace, tmp_path: Path) -> Workspace:
    """Return the workspace confined to ``inside`` in guarded mode, scripts off."""
    inside = tmp_path / "inside"
    inside.mkdir()
    space.working_dir = inside
    space.boundary = Boundary((inside,), "guarded", execute=False)
    return space


@pytest.fixture
def show(space: Workspace, site: Site, run: Run) -> Callable[[str], str]:
    """Return a function that opens HTML in the default context, giving its address."""

    def opening(markup: str) -> str:
        address = site.page(markup)
        run(navigate.open_url(space.browsing(), address))
        return address

    return opening
