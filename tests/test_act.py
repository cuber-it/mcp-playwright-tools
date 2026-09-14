"""Clicking, acting on elements, filling, keys, dropdowns, dragging, files, scripts."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import Run
from mcp_playwright_tools import (
    OutsideBoundaryError,
    ToolError,
    Workspace,
    act,
    read,
)
from mcp_playwright_tools.boundary import TMP

# Every event on the element is written into #log, so a test reads what happened.
RECORDER = (
    '<p id="log"></p>'
    "<script>function note(what) {"
    " document.getElementById('log').textContent += what + ' '; }</script>"
)


def logged(space: Workspace, run: Run) -> list[str]:
    """Return the events the page noted, in order."""
    return run(read.read(space.browsing(), "#log")).split()


def test_clicking_reaches_the_element(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(RECORDER + "<button onclick=\"note('clicked')\">Save</button>")

    assert run(act.click(space.browsing(), "Save", "text")) == "clicked text='Save'"
    assert logged(space, run) == ["clicked"]


def test_clicking_by_role_picks_the_named_one(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(
        RECORDER + "<button onclick=\"note('save')\">Save</button>"
        "<button onclick=\"note('cancel')\">Cancel</button>"
    )

    run(act.click(space.browsing(), "button", "role", "Cancel"))

    assert logged(space, run) == ["cancel"]


def test_a_click_that_cannot_happen_says_what_was_attempted(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>nothing to click</p>")

    with pytest.raises(ToolError, match=r"could not click css='#missing': .*Timeout"):
        run(act.click(space.browsing(), "#missing"))


@pytest.mark.parametrize(
    ("action", "event"),
    [
        ("double_click", "dblclick"),
        ("right_click", "contextmenu"),
        ("hover", "mouseover"),
        ("focus", "focus"),
    ],
)
def test_each_action_reaches_the_element_as_its_own_event(
    space: Workspace, show: Callable[[str], str], run: Run, action: str, event: str
) -> None:
    show(RECORDER + f'<input id="box" on{event}="note(\'{event}\')">')

    assert (
        run(act.act_on(space.browsing(), action, "#box")) == f"{action} on css='#box'"
    )
    assert event in logged(space, run)


def test_checking_and_unchecking_change_the_box(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<input type="checkbox" id="agree">')
    checked = "document.getElementById('agree').checked"

    assert (
        run(act.act_on(space.browsing(), "check", "#agree")) == "check on css='#agree'"
    )
    assert run(act.run_javascript(space.browsing(), checked)) is True
    run(act.act_on(space.browsing(), "uncheck", "#agree"))
    assert run(act.run_javascript(space.browsing(), checked)) is False


def test_clearing_empties_a_field(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<input id="who" value="Ada">')

    assert run(act.act_on(space.browsing(), "clear", "#who")) == "clear on css='#who'"
    assert (
        run(
            act.run_javascript(space.browsing(), "document.getElementById('who').value")
        )
        == ""
    )


def test_scrolling_to_an_element_brings_it_into_view(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<div style="height:5000px"></div><p id="end">end</p>')

    run(act.act_on(space.browsing(), "scroll_to", "#end"))

    assert run(act.run_javascript(space.browsing(), "window.scrollY")) > 0


def test_an_action_that_does_not_exist_names_the_ones_that_do(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p id='x'>x</p>")

    with pytest.raises(ToolError, match="known are double_click, right_click, hover"):
        run(act.act_on(space.browsing(), "tickle", "#x"))


@pytest.mark.parametrize("typed", [False, True])
def test_filling_puts_the_value_into_the_field(
    space: Workspace, show: Callable[[str], str], run: Run, typed: bool
) -> None:
    show(
        RECORDER + '<label>Name <input id="who" value="old" '
        "onkeydown=\"note('key')\"></label>"
    )

    run(act.fill(space.browsing(), "Name", "Ada", typed=typed))

    assert run(
        act.run_javascript(space.browsing(), "document.getElementById('who').value")
    ) == ("Ada")
    assert ("key" in logged(space, run)) is typed


def test_a_key_goes_to_the_element_named(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(RECORDER + '<input id="who" onkeydown="note(event.key)">')

    assert run(act.press_key(space.browsing(), "Enter", "#who")) == "pressed Enter"
    assert logged(space, run) == ["Enter"]


def test_a_key_without_a_target_goes_to_the_page(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(RECORDER + "<script>document.onkeydown = e => note(e.key);</script>")

    run(act.press_key(space.browsing(), "Escape"))

    assert logged(space, run) == ["Escape"]


@pytest.mark.parametrize(("option", "text"), [("de", False), ("Deutsch", True)])
def test_an_option_is_chosen_by_value_or_by_its_text(
    space: Workspace, show: Callable[[str], str], run: Run, option: str, text: bool
) -> None:
    show(
        '<label>Language <select id="lang">'
        '<option value="en">English</option><option value="de">Deutsch</option>'
        "</select></label>"
    )

    assert run(act.choose(space.browsing(), "Language", option, text=text)) == (
        "chose ['de'] in label='Language'"
    )


def test_an_option_that_is_not_there_is_named(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<label>Language <select><option value="en">English</option></select></label>')

    with pytest.raises(ToolError, match="could not choose 'fr'"):
        run(act.choose(space.browsing(), "Language", "fr"))


def test_dragging_drops_one_element_on_the_other(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(
        RECORDER + '<div id="card" draggable="true" style="width:50px;height:50px">'
        'card</div><div id="bin" style="width:100px;height:100px" '
        'ondragover="event.preventDefault()" ondrop="note(\'dropped\')">bin</div>'
    )

    assert (
        run(act.drag(space.browsing(), "#card", "#bin")) == "dragged '#card' to '#bin'"
    )
    assert logged(space, run) == ["dropped"]


@pytest.mark.parametrize(("amount", "moved"), [("down", True), ("bottom", True)])
def test_scrolling_moves_the_page(
    space: Workspace, show: Callable[[str], str], run: Run, amount: str, moved: bool
) -> None:
    show('<div style="height:5000px">tall</div>')

    assert run(act.scroll(space.browsing(), amount)) == f"scrolled {amount}"
    assert (run(act.run_javascript(space.browsing(), "window.scrollY")) > 0) is moved


def test_scrolling_up_and_to_the_top_return_to_the_start(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show('<div style="height:5000px">tall</div>')
    run(act.scroll(space.browsing(), "bottom"))

    run(act.scroll(space.browsing(), "top"))

    assert run(act.run_javascript(space.browsing(), "window.scrollY")) == 0


def test_a_way_of_scrolling_that_does_not_exist_names_the_ones_that_do(
    space: Workspace, run: Run
) -> None:
    with pytest.raises(ToolError, match="known are down, up, top, bottom"):
        run(act.scroll(space.browsing(), "sideways"))


def test_files_are_attached_from_the_working_directory(
    space: Workspace, show: Callable[[str], str], run: Run, tmp_path: Path
) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    show(
        RECORDER + '<input type="file" id="up" multiple '
        'onchange="for (const f of this.files) note(f.name)">'
    )

    attached = run(act.attach_files(space.browsing(), "#up", " a.txt , b.txt "))

    assert attached == f"attached {tmp_path / 'a.txt'}, {tmp_path / 'b.txt'}"
    assert logged(space, run) == ["a.txt", "b.txt"]


def test_attaching_without_a_file_is_refused(space: Workspace, run: Run) -> None:
    with pytest.raises(ToolError, match="no file named"):
        run(act.attach_files(space.browsing(), "#up", " , "))


def test_attaching_a_file_that_does_not_exist_names_it(
    space: Workspace, run: Run, tmp_path: Path
) -> None:
    with pytest.raises(ToolError, match=f"no such file: {tmp_path / 'gone.txt'}"):
        run(act.attach_files(space.browsing(), "#up", "gone.txt"))


def test_a_file_from_outside_the_working_directory_is_refused_before_the_browser(
    fenced: Workspace, run: Run, tmp_path: Path
) -> None:
    (tmp_path / "token.txt").write_text("secret", encoding="utf-8")

    with pytest.raises(OutsideBoundaryError, match="uploads may come from"):
        run(act.attach_files(fenced.browsing("never-opened"), "#up", "../token.txt"))

    assert "never-opened" not in fenced.pool.sessions()


def test_a_file_from_tmp_is_attached_without_a_grant(
    fenced: Workspace, show: Callable[[str], str], run: Run
) -> None:
    upload = TMP / f"mcp-playwright-tools-{uuid.uuid4().hex}.txt"
    upload.write_text("from tmp", encoding="utf-8")
    show(RECORDER + '<input type="file" id="up" onchange="note(this.files[0].name)">')
    try:
        run(act.attach_files(fenced.browsing(), "#up", str(upload)))
    finally:
        upload.unlink()

    assert logged(fenced, run) == [upload.name]


def test_a_script_gives_back_what_it_returns(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<title>Scripted</title>")

    assert run(
        act.run_javascript(space.browsing(), "({title: document.title, n: 1 + 1})")
    ) == {
        "title": "Scripted",
        "n": 2,
    }


def test_a_script_that_fails_is_reported(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    with pytest.raises(ToolError, match="could not run the script: .*nowhere"):
        run(act.run_javascript(space.browsing(), "nowhere.at.all"))


def test_a_script_runs_without_a_grant_where_the_machine_is_fenced(
    fenced: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert run(act.run_javascript(fenced.browsing(), "1 + 1")) == 2
