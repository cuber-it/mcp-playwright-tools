"""pw-browse: one run in a browser from the shell."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import CHANNEL
from loopback import Site
from mcp_playwright_tools import ToolError, cli

FORM = (
    "<label>Name <input id='who'></label>"
    "<button onclick=\"out.textContent = who.value\">Save</button><p id='out'></p>"
)


def browse(*argv: str) -> int:
    """Run pw-browse with the test browser and return its exit status."""
    return cli.main([*argv, "--channel", CHANNEL, "--timeout", "5"])


def test_what_is_shown_comes_in_the_fixed_order(
    site: Site, capsys: pytest.CaptureFixture[str]
) -> None:
    address = site.page("<title>Hello</title><h1>Head</h1>")

    code = browse(address, "--text", "h1", "--url", "--title")

    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["Hello", address, "Head"]


def test_a_field_is_filled_before_the_click_and_its_value_may_hold_colons(
    site: Site, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["--fill", "Name:a:b", "--click", "Save", "--by", "text", "--text", "#out"]

    assert browse(site.page(FORM), *argv) == 0
    assert capsys.readouterr().out.strip() == "a:b"


def test_a_screenshot_is_written_and_named(
    site: Site, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    shot = tmp_path / "page.png"

    assert browse(site.page("<p>x</p>"), "--shot", str(shot)) == 0
    assert capsys.readouterr().out.startswith(f"wrote {shot}, ")
    assert shot.is_file()


def test_a_step_that_fails_is_reported_in_one_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert browse("nowhere.invalid") == cli.FAILED
    assert capsys.readouterr().err.startswith(
        "pw-browse: could not open https://nowhere.invalid"
    )


def test_the_address_flag_does_not_swallow_the_address_to_open() -> None:
    args = cli.parse(["example.org", "--url"])

    assert (args.url, args.show_url) == ("example.org", True)


def test_a_pair_without_a_colon_is_refused_with_the_option_named() -> None:
    with pytest.raises(ToolError, match="--wait wants LEFT:RIGHT, got 'visible'"):
        cli.split("visible", "--wait")
