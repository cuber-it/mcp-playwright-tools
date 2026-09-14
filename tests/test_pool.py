"""The browser, its named contexts, and when they are let go."""

from __future__ import annotations

import pytest

from conftest import CHANNEL, Run
from mcp_playwright_tools import BrowserPool, Settings, ToolError, Workspace, navigate

A_PAGE = "data:text/html,<p>x</p>"


def test_one_name_is_one_context_and_another_name_another(
    space: Workspace, run: Run
) -> None:
    pool = space.pool

    assert run(pool.session("a")) is run(pool.session("a"))
    assert run(pool.session("a")) is not run(pool.session("b"))


def test_listing_the_contexts_does_not_count_as_using_them(
    space: Workspace, run: Run
) -> None:
    session = run(space.pool.session("a"))
    session.touched -= 100

    space.pool.sessions()

    assert session.idle_for() >= 100


def test_closing_a_context_that_is_not_there_is_reported(
    space: Workspace, run: Run
) -> None:
    assert run(space.pool.close("ghost")) is False


def test_the_browser_stops_with_the_last_context_and_starts_again(
    lone: Workspace, run: Run
) -> None:
    run(navigate.open_url(lone.browsing("a"), A_PAGE))

    assert run(lone.pool.close("a")) is True
    assert not lone.pool.sessions()
    assert run(navigate.open_url(lone.browsing("b"), A_PAGE)).startswith("at data:")


def test_sweeping_closes_what_went_untouched_and_leaves_the_rest(
    lone: Workspace, run: Run
) -> None:
    lone.pool.settings = Settings(channel=CHANNEL, idle=60)
    run(lone.pool.session("stale")).touched -= 120
    run(lone.pool.session("fresh"))

    assert run(lone.pool.sweep()) == ["stale"]
    assert list(lone.pool.sessions()) == ["fresh"]


def test_sweeping_is_off_without_an_idle_time(lone: Workspace, run: Run) -> None:
    run(lone.pool.session("stale")).touched -= 10_000

    assert run(lone.pool.sweep()) == []
    assert list(lone.pool.sessions()) == ["stale"]


def test_a_browser_that_went_away_is_started_again_with_fresh_contexts(
    lone: Workspace, run: Run
) -> None:
    run(navigate.tabs(lone.browsing("a"), "open"))
    spot = run(lone.pool.spot("a"))
    run(spot.context.browser.close())

    assert run(navigate.open_url(lone.browsing("a"), A_PAGE)).startswith("at data:")
    assert run(navigate.tabs(lone.browsing("a"))) == "tabs [0], active 0"


def test_the_contexts_of_a_browser_that_went_away_are_forgotten_not_closed(
    lone: Workspace, run: Run
) -> None:
    lone.pool.settings = Settings(channel=CHANNEL, idle=60)
    spot = run(lone.pool.spot("a"))
    spot.session.touched -= 120
    run(spot.context.browser.close())

    assert run(lone.pool.sweep()) == []
    assert run(lone.pool.close("a")) is False
    assert run(lone.pool.close_all()) == 0


def test_a_browser_that_cannot_start_is_reported_and_leaves_nothing_running(
    run: Run,
) -> None:
    pool = BrowserPool(Settings(channel="no-such-channel", idle=0))

    with pytest.raises(ToolError, match="could not start no-such-channel"):
        run(pool.session("a"))

    assert not pool.sessions()
    assert run(pool.close_all()) == 0


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"browser": "lynx"}, "no such browser"),
        ({"timeout": -1}, "timeout has to be positive"),
        ({"idle": -5}, "idle cannot be negative"),
    ],
)
def test_settings_a_browser_cannot_run_with_are_refused(
    settings: dict[str, object], message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        Settings(**settings)
