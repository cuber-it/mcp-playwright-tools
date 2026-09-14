"""Reading text, markup, attributes and links, screenshots, and waiting."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import Run
from loopback import Site
from mcp_playwright_tools import (
    NotPermittedError,
    OutsideBoundaryError,
    Picture,
    ToolError,
    Workspace,
    navigate,
    read,
)
from mcp_playwright_tools.boundary import TMP
from mcp_playwright_tools.grant import GRANT_FILE

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def size_of(data: bytes) -> tuple[int, int]:
    """Return width and height from the header of PNG data."""
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def later(script: str) -> str:
    """Return a script element that runs a script a moment after the page loaded."""
    return f"<script>setTimeout(() => {{ {script} }}, 200);</script>"


def test_the_text_of_the_page_is_read_without_a_target(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<h1>Title</h1><p>  body text  </p>")

    assert run(read.read(space.browsing())) == "Title\n\nbody text"


def test_the_text_of_one_element_is_read_and_trimmed(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p id='a'>   spaced   </p>")

    assert run(read.read(space.browsing(), "#a")) == "spaced"


def test_long_text_is_cut_and_says_how_much_was_dropped(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(f"<p id='long'>{'x' * 20_050}</p>")

    text = run(read.read(space.browsing(), "#long"))

    assert text.endswith("[... 50 more characters]")
    assert text.startswith("x" * 20_000 + "\n")


def test_reading_what_is_not_there_is_refused(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    with pytest.raises(ToolError, match="nothing matches css='#missing'"):
        run(read.read(space.browsing(), "#missing"))


def test_the_text_of_every_match_comes_one_per_line(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<ul><li> one </li><li>two</li></ul>")

    assert run(read.read(space.browsing(), "li", "texts")) == "one\ntwo"


def test_every_match_of_nothing_says_what_was_looked_for(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert run(read.read(space.browsing(), "li", "texts")) == "nothing matches css='li'"


def test_many_matches_are_cut_at_the_row_limit(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("".join(f"<li>{number}</li>" for number in range(205)))

    rows = run(read.read(space.browsing(), "li", "texts")).splitlines()

    assert len(rows) == 201
    assert rows[-1] == "[... 5 more]"


def test_every_match_needs_a_target(space: Workspace, run: Run) -> None:
    with pytest.raises(ToolError, match="needs a target"):
        run(read.read(space.browsing(), what="texts"))


def test_markup_without_a_target_is_that_of_the_whole_page(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<h1>Title</h1>")

    assert "<h1>Title</h1>" in run(read.read(space.browsing(), what="html"))


def test_markup_of_an_element_is_what_is_inside_it(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<div id='box'><b>bold</b></div>")

    assert run(read.read(space.browsing(), "#box", "html")) == "<b>bold</b>"


def test_an_attribute_that_is_set_comes_back_as_its_value(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<a id='home' href='/start'>Home</a>")

    assert run(read.read(space.browsing(), "#home", "attribute", "href")) == "/start"


def test_an_attribute_that_is_not_set_is_named(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<a id='home'>Home</a>")

    assert (
        run(read.read(space.browsing(), "#home", "attribute", "href"))
        == "href is not set"
    )


def test_an_attribute_needs_its_name(space: Workspace, run: Run) -> None:
    with pytest.raises(ToolError, match="needs its name"):
        run(read.read(space.browsing(), "#home", "attribute"))


def test_the_links_come_as_text_and_address(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    address = show("<a href='/one'>One</a><a href='/two'><img alt=''></a>")
    base = address.rsplit("/", 1)[0]

    assert run(read.read(space.browsing(), what="links")).splitlines() == [
        f"One -> {base}/one",
        f"(no text) -> {base}/two",
    ]


def test_links_and_markup_come_from_the_frame_acted_in(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(
        "<a href='/outer'>Outer</a>"
        "<iframe id='inner' srcdoc=\"<a href='/inner'>Inner</a>\"></iframe>"
    )
    here = space.browsing()
    run(navigate.use_frame(here, "#inner"))
    run(read.wait_until(here, "visible", "a"))

    assert run(read.read(here, what="links")).startswith("Inner -> ")
    markup = run(read.read(here, what="html"))
    assert "Inner" in markup
    assert "Outer" not in markup


def test_a_page_without_links_says_so(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert run(read.read(space.browsing(), what="links")) == "no links on this page"


def test_a_thing_to_read_that_does_not_exist_names_the_ones_that_do(
    space: Workspace, run: Run
) -> None:
    with pytest.raises(ToolError, match="known are text, texts, html, attribute"):
        run(read.read(space.browsing(), what="smell"))


def test_a_screenshot_is_a_png_picture_of_the_visible_page(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<div style='height:3000px'>tall</div>")

    shot = run(read.screenshot(space.browsing()))

    assert isinstance(shot, Picture)
    assert shot.image_format == "PNG"
    assert shot.data.startswith(PNG_SIGNATURE)
    assert size_of(shot.data)[1] < 3000


def test_a_full_screenshot_takes_the_whole_page(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<body style='margin:0'><div style='height:3000px'>tall</div></body>")

    assert size_of(run(read.screenshot(space.browsing(), full=True)).data)[1] == 3000


def test_a_screenshot_of_an_element_takes_only_that(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<div id='box' style='width:50px;height:40px;background:red'></div>")

    assert size_of(run(read.screenshot(space.browsing(), "#box")).data) == (50, 40)


def test_a_screenshot_of_what_is_not_there_is_refused(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    with pytest.raises(ToolError, match="nothing matches"):
        run(read.screenshot(space.browsing(), "#missing"))


def test_a_screenshot_is_written_where_it_was_asked_for(
    space: Workspace, show: Callable[[str], str], run: Run, tmp_path: Path
) -> None:
    show("<p>x</p>")

    answer = run(read.screenshot(space.browsing(), save_to="shots/page.png"))

    stored = tmp_path / "shots" / "page.png"
    assert answer == f"wrote {stored}, {stored.stat().st_size} bytes"
    assert stored.read_bytes().startswith(PNG_SIGNATURE)


def test_a_file_ending_in_pdf_gets_the_whole_page_as_a_pdf(
    space: Workspace, show: Callable[[str], str], run: Run, tmp_path: Path
) -> None:
    show("<p>printed</p>")

    answer = run(read.screenshot(space.browsing(), save_to="page.PDF"))

    stored = tmp_path / "page.PDF"
    assert answer == f"wrote {stored}, {stored.stat().st_size} bytes"
    assert stored.read_bytes().startswith(b"%PDF")


def test_a_pdf_of_one_element_is_refused(
    space: Workspace, show: Callable[[str], str], run: Run, tmp_path: Path
) -> None:
    show("<p id='a'>x</p>")

    with pytest.raises(ToolError, match="a PDF is always of the whole page"):
        run(read.screenshot(space.browsing(), "#a", save_to="page.pdf"))

    assert not (tmp_path / "page.pdf").exists()


def test_a_screenshot_outside_the_roots_is_refused_before_it_is_taken(
    fenced: Workspace, run: Run, tmp_path: Path
) -> None:
    with pytest.raises(OutsideBoundaryError, match=f"set --root {tmp_path}"):
        run(read.screenshot(fenced.browsing("never-opened"), save_to="../page.png"))

    assert not (tmp_path / "page.png").exists()
    assert "never-opened" not in fenced.pool.sessions()


def test_a_screenshot_goes_to_tmp_without_a_grant(
    fenced: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")
    shot = TMP / f"mcp-playwright-tools-{uuid.uuid4().hex}.png"
    try:
        answer = run(read.screenshot(fenced.browsing(), save_to=str(shot)))
        written = shot.read_bytes()
    finally:
        shot.unlink(missing_ok=True)

    assert answer.startswith(f"wrote {shot}, ")
    assert written.startswith(PNG_SIGNATURE)


def test_a_screenshot_is_never_written_over_the_grant_file(
    space: Workspace, run: Run
) -> None:
    grant = space.state_dir / GRANT_FILE

    with pytest.raises(NotPermittedError, match="grant file"):
        run(read.screenshot(space.browsing(), save_to=str(grant)))


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into read-only directories")
def test_a_failed_write_leaves_nothing_behind(
    space: Workspace, show: Callable[[str], str], run: Run, tmp_path: Path
) -> None:
    show("<p>x</p>")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(ToolError, match="could not write"):
            run(read.screenshot(space.browsing(), save_to="locked/page.png"))
        left = list(locked.iterdir())
    finally:
        locked.chmod(0o700)

    assert not left


def test_waiting_until_an_element_shows(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(later("document.body.innerHTML = '<p id=late>late</p>';"))

    assert (
        run(read.wait_until(space.browsing(), "visible", "#late"))
        == "css='#late' is visible"
    )


def test_waiting_until_an_element_hides(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show(
        "<p id='soon'>soon gone</p>"
        + later("document.getElementById('soon').remove();")
    )

    assert (
        run(read.wait_until(space.browsing(), "hidden", "#soon"))
        == "css='#soon' is hidden"
    )


def test_waiting_until_the_address_changes(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    address = show(later("location.hash = 'done';"))

    assert (
        run(read.wait_until(space.browsing(), "url", "#done")) == f"at {address}#done"
    )


def test_waiting_until_the_page_has_loaded(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert run(read.wait_until(space.browsing(), "load")) == "page reached load"
    assert run(read.wait_until(space.browsing(), "load", "networkidle")) == (
        "page reached networkidle"
    )


def test_waiting_until_a_response_arrives(
    space: Workspace, site: Site, show: Callable[[str], str], run: Run
) -> None:
    api = site.data('{"n": 1}')
    show(later(f"fetch('{api}');"))

    assert run(read.wait_until(space.browsing(), "response", api)) == f"200 from {api}"


def test_waiting_in_vain_says_what_and_how_long(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    with pytest.raises(
        ToolError, match=r"could not see css='#never' visible within 0.3s"
    ):
        run(read.wait_until(space.browsing(), "visible", "#never", seconds=0.3))


@pytest.mark.parametrize(
    ("waiting", "message"),
    [
        ({"what": "smell"}, "known are visible, hidden, url, load, response"),
        ({"what": "load", "value": "done"}, "known are load, domcontentloaded"),
        ({"what": "url"}, "needs a part of it"),
        ({"what": "visible", "value": "#x", "seconds": 0.0}, "has to be positive"),
    ],
)
def test_waiting_for_what_cannot_be_waited_for_is_refused(
    space: Workspace, run: Run, waiting: dict[str, object], message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(read.wait_until(space.browsing(), **waiting))
