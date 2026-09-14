"""Cookies, the local storage, intercepted requests and the contexts."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from conftest import Run
from mcp_playwright_tools import ToolError, Workspace, act, keep, navigate, read

COOKIE = {"name": "who", "value": "ada", "url": "http://127.0.0.1"}
FETCHER = (
    "<p id='log'></p><button id='load' onclick=\"fetch('/api/thing')"
    ".then(r => r.text()).then(t => log.textContent = t)"
    ".catch(() => log.textContent = 'failed')\">load</button>"
)


def fetched(space: Workspace, run: Run) -> str:
    """Click the button that fetches, and return what the page shows afterwards."""
    run(act.click(space.browsing(), "#load"))
    run(read.wait_until(space.browsing(), "visible", "#log:not(:empty)"))
    return run(read.read(space.browsing(), "#log"))


def test_a_fresh_context_has_no_cookies(space: Workspace, run: Run) -> None:
    assert run(keep.storage(space.browsing("fresh"))) == "no cookies"


def test_a_cookie_is_set_as_an_object_and_read_back(space: Workspace, run: Run) -> None:
    assert run(
        keep.storage(space.browsing(), "cookies", "set", value=json.dumps(COOKIE))
    ) == ("set 1 cookie(s)")

    found = json.loads(run(keep.storage(space.browsing())))
    assert [(item["name"], item["value"]) for item in found] == [("who", "ada")]


def test_several_cookies_are_set_as_an_array(space: Workspace, run: Run) -> None:
    both = [COOKIE, {**COOKIE, "name": "lang", "value": "de"}]

    assert run(
        keep.storage(space.browsing(), "cookies", "set", value=json.dumps(both))
    ) == ("set 2 cookie(s)")


def test_clearing_the_cookies_leaves_none(space: Workspace, run: Run) -> None:
    run(keep.storage(space.browsing(), "cookies", "set", value=json.dumps(COOKIE)))

    assert run(keep.storage(space.browsing(), "cookies", "clear")) == "cookies cleared"
    assert run(keep.storage(space.browsing())) == "no cookies"


def test_two_contexts_do_not_share_their_cookies(space: Workspace, run: Run) -> None:
    run(keep.storage(space.browsing("one"), "cookies", "set", value=json.dumps(COOKIE)))

    assert run(keep.storage(space.browsing("two"))) == "no cookies"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not json", "have to be JSON"),
        ("[1, 2]", "JSON objects with name, value"),
        ("[]", "JSON objects with name, value"),
        ('{"name": "who", "value": "ada"}', "could not set the cookies"),
    ],
)
def test_cookies_that_cannot_be_set_are_refused(
    space: Workspace, run: Run, payload: str, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(keep.storage(space.browsing(), "cookies", "set", value=payload))

    assert run(keep.storage(space.browsing())) == "no cookies"


def test_a_local_entry_is_set_and_read_back(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert (
        run(keep.storage(space.browsing(), "local", "set", "lang", "de")) == "set lang"
    )
    assert run(keep.storage(space.browsing(), "local", "get", "lang")) == "de"
    assert json.loads(run(keep.storage(space.browsing(), "local"))) == {"lang": "de"}


def test_a_local_entry_that_is_not_set_is_named(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert (
        run(keep.storage(space.browsing(), "local", "get", "lang")) == "lang is not set"
    )


def test_clearing_the_local_storage_empties_it(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")
    run(keep.storage(space.browsing(), "local", "set", "lang", "de"))

    assert run(keep.storage(space.browsing(), "local", "clear")) == "storage cleared"
    assert run(keep.storage(space.browsing(), "local")) == "storage is empty"


def test_setting_a_local_entry_needs_its_key(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    with pytest.raises(ToolError, match="needs its key"):
        run(keep.storage(space.browsing(), "local", "set", value="de"))


def test_a_page_that_will_not_give_up_its_storage_is_reported(
    space: Workspace, run: Run
) -> None:
    run(navigate.open_url(space.browsing(), "data:text/html,<p>x</p>"))

    with pytest.raises(ToolError, match="could not reach the local storage"):
        run(keep.storage(space.browsing(), "local"))


@pytest.mark.parametrize(
    ("kind", "action", "message"),
    [
        ("session", "get", "known are cookies, local"),
        ("cookies", "drop", "known are get, set, clear"),
    ],
)
def test_an_unknown_kind_or_action_names_the_known_ones(
    space: Workspace, run: Run, kind: str, action: str, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(keep.storage(space.browsing(), kind, action))


def test_a_mocked_request_gets_the_answer_it_was_given(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FETCHER)

    assert run(keep.intercept(space.browsing(), "mock", "**/api/thing", "mocked")) == (
        "mocking **/api/thing with 200"
    )
    assert fetched(space, run) == "mocked"


def test_a_blocked_request_fails_in_the_page(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FETCHER)

    assert run(keep.intercept(space.browsing(), "abort", "**/api/thing")) == (
        "blocking **/api/thing"
    )
    assert fetched(space, run) == "failed"


def test_a_cleared_route_lets_the_request_through_again(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FETCHER)
    run(keep.intercept(space.browsing(), "mock", "**/api/thing", "mocked"))

    assert run(keep.intercept(space.browsing(), "clear", "**/api/thing")) == (
        "no longer interfering with **/api/thing"
    )
    assert fetched(space, run) == "not here"


@pytest.mark.parametrize(
    ("action", "pattern", "message"),
    [
        ("rewrite", "**", "known are mock, abort, clear"),
        ("mock", "", "needs a pattern"),
    ],
)
def test_interfering_in_a_way_that_does_not_exist_is_refused(
    space: Workspace, run: Run, action: str, pattern: str, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(keep.intercept(space.browsing(), action, pattern))


def test_the_open_contexts_are_listed_with_their_tabs(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    listing = run(keep.contexts(space)).splitlines()

    assert "default: 1 tab(s), active 0, idle 0s" in listing


def test_closing_one_context_leaves_the_others(space: Workspace, run: Run) -> None:
    run(navigate.tabs(space.browsing("one"), "open"))
    run(navigate.tabs(space.browsing("two"), "open"))

    assert run(keep.contexts(space, "close", "one")) == "closed context 'one'"
    names = [line.split(":")[0] for line in run(keep.contexts(space)).splitlines()]
    assert "one" not in names
    assert "two" in names


def test_closing_a_context_that_is_not_there_says_so(
    space: Workspace, run: Run
) -> None:
    assert run(keep.contexts(space, "close", "ghost")) == "no context 'ghost'"


def test_closing_everything_reports_the_count_and_stops_the_browser(
    lone: Workspace, run: Run
) -> None:
    run(navigate.tabs(lone.browsing("one"), "open"))
    run(navigate.tabs(lone.browsing("two"), "open"))

    assert run(keep.contexts(lone, "close")) == "closed 2 context(s), browser stopped"
    assert run(keep.contexts(lone)) == "no browser context is open"


def test_an_unknown_thing_to_do_with_contexts_names_the_known_ones(
    space: Workspace, run: Run
) -> None:
    with pytest.raises(ToolError, match="known are list, close"):
        run(keep.contexts(space, "rename"))
