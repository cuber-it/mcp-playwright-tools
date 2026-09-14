"""Opening pages, moving through the history, tabs and frames."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import Run, awaiting
from loopback import Site
from mcp_playwright_tools import (
    Boundary,
    OutsideBoundaryError,
    ToolError,
    Workspace,
    act,
    navigate,
    read,
)

OPENER = "<button id='open' onclick=\"window.open('{address}')\">open</button>"


def test_opening_a_page_reports_where_it_ended_up(
    space: Workspace, site: Site, run: Run
) -> None:
    address = site.page("<h1>hello</h1>")

    assert run(navigate.open_url(space.browsing(), address)) == f"at {address}"


def test_a_redirect_is_followed_and_the_final_address_reported(
    space: Workspace, site: Site, run: Run
) -> None:
    landing = site.page("<h1>landed</h1>")

    assert (
        run(navigate.open_url(space.browsing(), site.redirect(landing)))
        == f"at {landing}"
    )


@pytest.mark.parametrize(
    ("written", "opened"),
    [
        ("nowhere.invalid", "https://nowhere.invalid"),
        ("nowhere.invalid:8080", "https://nowhere.invalid:8080"),
    ],
)
def test_an_address_without_a_scheme_is_opened_over_https(
    space: Workspace, run: Run, written: str, opened: str
) -> None:
    with pytest.raises(ToolError, match=f"could not open {opened}"):
        run(navigate.open_url(space.browsing(), written))


def test_a_data_address_is_opened_as_it_is(space: Workspace, run: Run) -> None:
    assert run(
        navigate.open_url(space.browsing(), "data:text/html,<p>x</p>")
    ).startswith("at data:text/html")


def test_an_empty_address_is_refused(space: Workspace, run: Run) -> None:
    with pytest.raises(ToolError, match="no address"):
        run(navigate.open_url(space.browsing(), "  "))


def test_a_javascript_address_is_refused_in_favour_of_run_javascript(
    space: Workspace, run: Run
) -> None:
    with pytest.raises(ToolError, match="use run_javascript"):
        run(navigate.open_url(space.browsing(), "javascript:alert(1)"))


def test_a_page_on_disk_is_opened_where_reading_may_reach(
    fenced: Workspace, run: Run, tmp_path: Path
) -> None:
    page = tmp_path / "outside.html"
    page.write_text("<h1>from disk</h1>", encoding="utf-8")

    assert (
        run(navigate.open_url(fenced.browsing(), page.as_uri()))
        == f"at {page.as_uri()}"
    )
    assert run(read.read(fenced.browsing(), "h1")) == "from disk"


def test_a_page_on_disk_outside_strict_roots_is_refused(
    fenced: Workspace, run: Run, tmp_path: Path
) -> None:
    fenced.boundary = Boundary(fenced.boundary.roots, "strict")
    page = tmp_path / "outside.html"
    page.write_text("<h1>secret</h1>", encoding="utf-8")

    with pytest.raises(OutsideBoundaryError, match=f"set --root {tmp_path}"):
        run(navigate.open_url(fenced.browsing(), page.as_uri()))


def test_the_three_ways_through_the_history(
    space: Workspace, site: Site, run: Run
) -> None:
    first = site.page("<h1>one</h1>")
    second = site.page("<h1>two</h1>")
    run(navigate.open_url(space.browsing(), first))
    run(navigate.open_url(space.browsing(), second))

    assert run(navigate.go(space.browsing(), "back")) == f"at {first}"
    assert run(navigate.go(space.browsing(), "forward")) == f"at {second}"
    assert run(navigate.go(space.browsing(), "reload")) == f"at {second}"


def test_a_direction_that_does_not_exist_names_the_ones_that_do(
    space: Workspace, run: Run
) -> None:
    with pytest.raises(ToolError, match="known are back, forward, reload"):
        run(navigate.go(space.browsing(), "sideways"))


def test_where_am_i_reports_page_tab_frames_and_viewport(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    side = site.page("<p>side</p>")
    address = show(f"<title>Hello</title><iframe name='side' src='{side}'></iframe>")
    run(read.wait_until(space.browsing(), "load"))

    assert run(navigate.where_am_i(space.browsing())) == {
        "url": address,
        "title": "Hello",
        "tab": 0,
        "frame": "",
        "frames": [f"side - {side}"],
        "viewport": "1280x720",
    }


def test_tabs_are_opened_listed_switched_and_closed(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    first = show("<title>First</title>")

    assert run(navigate.tabs(space.browsing(), "open")) == "opened tab 1"
    assert run(navigate.tabs(space.browsing())).splitlines() == [
        f"0: First - {first}",
        "1 (active): (no title) - about:blank",
    ]
    assert run(navigate.tabs(space.browsing(), "switch", 0)) == "active tab is now 0"
    assert run(navigate.where_am_i(space.browsing()))["url"] == first
    assert run(navigate.tabs(space.browsing(), "close", 1)) == "closed tab 1"
    assert run(navigate.tabs(space.browsing())) == f"0 (active): First - {first}"


def test_a_tab_the_page_opens_is_listed_and_becomes_the_active_one(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    popup = site.page("<title>Popup</title><p id='where'>popup</p>")
    first = show(f"<a id='go' href='{popup}' target='_blank'>go</a>")
    context = run(space.browsing().session()).context

    opened = run(awaiting(context, "page", act.click(space.browsing(), "#go")))
    run(opened.wait_for_load_state())

    assert run(navigate.tabs(space.browsing())).splitlines() == [
        f"0: (no title) - {first}",
        f"1 (active): Popup - {popup}",
    ]
    assert run(read.read(space.browsing(), "#where")) == "popup"


def test_a_tab_that_closes_itself_is_dropped_and_the_work_goes_back(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    first = show(OPENER.format(address="about:blank"))
    context = run(space.browsing().session()).context
    opened = run(awaiting(context, "page", act.click(space.browsing(), "#open")))

    run(awaiting(opened, "close", opened.evaluate("setTimeout(() => window.close())")))

    assert run(navigate.tabs(space.browsing())) == f"0 (active): (no title) - {first}"


def test_closing_the_active_tab_hands_the_work_to_one_still_open(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    first = show("<p>first</p>")
    run(navigate.tabs(space.browsing(), "open"))

    run(navigate.tabs(space.browsing(), "close", 1))

    assert run(navigate.where_am_i(space.browsing()))["url"] == first


@pytest.mark.parametrize("action", ["switch", "close"])
def test_a_tab_that_is_not_open_is_named_with_the_open_ones(
    space: Workspace, show: Callable[[str], str], run: Run, action: str
) -> None:
    show("<p>x</p>")

    with pytest.raises(ToolError, match=r"no tab 7; open: \[0\]"):
        run(navigate.tabs(space.browsing(), action, 7))


def test_a_context_nothing_was_opened_in_has_no_tab(space: Workspace, run: Run) -> None:
    assert run(navigate.tabs(space.browsing("fresh"))) == "no tab open"


def test_an_unknown_thing_to_do_with_tabs_names_the_known_ones(
    space: Workspace, run: Run
) -> None:
    with pytest.raises(ToolError, match="known are list, open, switch, close"):
        run(navigate.tabs(space.browsing(), "shuffle"))


def test_two_contexts_do_not_share_a_page(
    space: Workspace, site: Site, run: Run
) -> None:
    one = site.page("<p>one</p>")
    two = site.page("<p>two</p>")

    run(navigate.open_url(space.browsing("one"), one))
    run(navigate.open_url(space.browsing("two"), two))

    assert run(navigate.where_am_i(space.browsing("one")))["url"] == one
    assert run(navigate.where_am_i(space.browsing("two")))["url"] == two


def test_a_frame_is_where_the_next_calls_look_until_it_is_left(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(
        '<p id="where">page</p>'
        '<iframe id="inner" srcdoc="<p id=\'where\'>frame</p>"></iframe>'
    )

    assert (
        run(navigate.use_frame(space.browsing(), "#inner")) == "acting inside '#inner'"
    )
    run(read.wait_until(space.browsing(), "visible", "#where"))
    assert run(read.read(space.browsing(), "#where")) == "frame"
    assert run(navigate.use_frame(space.browsing())) == "acting in the page itself"
    assert run(read.read(space.browsing(), "#where")) == "page"


def test_a_frame_inside_a_frame_is_reached_step_by_step(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    deep = site.page("<p id='where'>deep</p>")
    middle = site.page(
        f"<p id='where'>middle</p><iframe id='deep' src='{deep}'></iframe>"
    )
    show(f"<iframe id='middle' src='{middle}'></iframe>")

    run(navigate.use_frame(space.browsing(), "#middle >> #deep"))
    run(read.wait_until(space.browsing(), "visible", "#where"))

    assert run(read.read(space.browsing(), "#where")) == "deep"


def test_another_tab_is_acted_in_as_a_page_not_in_the_frame(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<iframe id='inner' srcdoc='<p>x</p>'></iframe>")
    run(navigate.use_frame(space.browsing(), "#inner"))

    run(navigate.tabs(space.browsing(), "open"))

    assert run(navigate.where_am_i(space.browsing()))["frame"] == ""


def test_the_viewport_is_reported_and_changed(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert run(navigate.viewport(space.browsing())) == "viewport 1280x720"
    assert run(navigate.viewport(space.browsing(), 390, 844)) == "viewport 390x844"
    page = run(space.browsing().spot()).page
    assert run(page.evaluate("[innerWidth, innerHeight]")) == [390, 844]


@pytest.mark.parametrize(("width", "height"), [(390, 0), (0, 844), (-1, 844)])
def test_a_viewport_without_two_positive_sides_is_refused(
    space: Workspace, run: Run, width: int, height: int
) -> None:
    with pytest.raises(ToolError, match="width and height have to be positive"):
        run(navigate.viewport(space.browsing(), width, height))
