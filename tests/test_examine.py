"""Finding elements, describing one, and what a page offers."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from conftest import Run
from mcp_playwright_tools import ToolError, Workspace, examine, navigate, read

FORM = (
    "<h1>Sign in</h1>"
    '<label for="who">Name</label><input id="who" placeholder="your name">'
    '<button data-testid="go">Save</button><button>Cancel</button>'
    '<a href="/help">Help</a>'
)


@pytest.mark.parametrize(
    ("pointing", "count"),
    [
        ({"target": "button", "by": "css"}, 2),
        ({"target": "button", "by": "role", "name": "Save"}, 1),
        ({"target": "Cancel", "by": "text"}, 1),
        ({"target": "Name", "by": "label"}, 1),
        ({"target": "your name", "by": "placeholder"}, 1),
        ({"target": "go", "by": "testid"}, 1),
    ],
)
def test_every_way_of_pointing_finds_what_it_names(
    space: Workspace,
    show: Callable[[str], str],
    run: Run,
    pointing: dict[str, str],
    count: int,
) -> None:
    show(FORM)

    found = run(examine.find(space.browsing(), **pointing))

    assert found.startswith(f"{count} match {pointing['by']}={pointing['target']!r}")


def test_what_was_found_is_listed_with_tag_and_text(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FORM)

    listing = run(examine.find(space.browsing(), "button"))

    assert listing.splitlines()[1:] == ["1. <button> Save", "2. <button> Cancel"]


def test_an_input_is_described_by_its_value(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<input id="who" value="Ada">')

    assert (
        run(examine.find(space.browsing(), "#who")).splitlines()[1] == "1. <input> Ada"
    )


def test_finding_nothing_says_what_was_looked_for_and_how(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FORM)

    assert (
        run(examine.find(space.browsing(), "Delete", "text"))
        == "nothing matches text='Delete'"
    )


def test_a_long_list_is_cut_and_says_how_many_were_left_out(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("".join(f"<li>{number}</li>" for number in range(25)))

    listing = run(examine.find(space.browsing(), "li")).splitlines()

    assert listing[0] == "25 match css='li':"
    assert len(listing) == 22
    assert listing[-1] == "[... 5 more]"


def test_an_unknown_way_of_pointing_names_the_known_ones(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FORM)

    with pytest.raises(ToolError, match="known are css, role, text, label"):
        run(examine.find(space.browsing(), "button", "xpath"))


def test_an_empty_target_is_refused(space: Workspace, run: Run) -> None:
    with pytest.raises(ToolError, match="target is empty"):
        run(examine.find(space.browsing(), ""))


def test_describing_the_first_match_counts_every_match_hidden_or_not(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<button id="a" disabled>Save</button><button hidden>Save</button>')

    described = run(examine.describe(space.browsing(), "Save", "text"))

    assert described == {
        "describes": "<button> Save",
        "attributes": {"id": "a", "disabled": ""},
        "visible": True,
        "enabled": False,
        "matches": 2,
    }


def test_describing_what_is_not_there_is_refused(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FORM)

    with pytest.raises(ToolError, match="nothing matches css='#missing'"):
        run(examine.describe(space.browsing(), "#missing"))


def test_what_can_be_done_lists_the_visible_controls(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FORM + '<button style="display:none">Hidden</button>')

    assert run(examine.what_can_i_do(space.browsing())).splitlines() == [
        "<input> type=text #who your name",
        "<button> type=submit Save",
        "<button> type=submit Cancel",
        "<a> Help",
    ]


def test_what_can_be_done_includes_a_control_fixed_on_the_screen(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<button id="accept" style="position:fixed;bottom:0">Accept</button>')

    assert run(examine.what_can_i_do(space.browsing())) == (
        "<button> type=submit #accept Accept"
    )


def test_what_can_be_done_in_a_frame_is_what_the_frame_offers(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(
        "<button>Outside</button>"
        "<iframe id='inner' srcdoc='<button>Inside</button>'></iframe>"
    )
    here = space.browsing()
    run(navigate.use_frame(here, "#inner"))
    run(read.wait_until(here, "visible", "button"))

    assert run(examine.what_can_i_do(here)) == "<button> type=submit Inside"


def test_a_page_with_nothing_to_act_on_says_so(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>just words</p>")

    assert run(examine.what_can_i_do(space.browsing())) == "nothing to act on here"


def test_the_outline_names_headings_and_controls(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(FORM)

    tree = run(examine.outline(space.browsing()))

    assert 'heading "Sign in"' in tree
    assert 'button "Save"' in tree
