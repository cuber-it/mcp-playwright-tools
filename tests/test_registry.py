"""What the catalogue hands a server.

No server is involved: the catalogue is plain data, which is the point of
keeping it free of any server library.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import EXPECTED, Run
from mcp_playwright_tools import DEFAULT_CONTEXT, Picture, ToolError, Workspace
from mcp_playwright_tools.server.registry import Catalogue, catalogue


@pytest.fixture
def unstarted(tmp_path: Path) -> Catalogue:
    """Return the catalogue on a workspace whose browser is never started."""
    return catalogue(Workspace(working_dir=tmp_path))


def test_the_whole_set_is_in_the_catalogue(unstarted: Catalogue) -> None:
    assert set(unstarted) == EXPECTED


def test_every_tool_is_a_coroutine_function(unstarted: Catalogue) -> None:
    assert [n for n, t in unstarted.items() if not inspect.iscoroutinefunction(t)] == []


def test_every_description_has_english_german_and_search_words(
    unstarted: Catalogue,
) -> None:
    incomplete = []
    for name, tool in unstarted.items():
        paragraphs = [part.strip() for part in tool.__doc__.split("\n\n")]
        if len(paragraphs) < 3 or not paragraphs[-1].startswith("Stichworte:"):
            incomplete.append(name)

    assert not incomplete


def test_every_tool_on_a_page_takes_the_context_by_name(unstarted: Catalogue) -> None:
    without = [
        name
        for name, tool in unstarted.items()
        if name != "contexts"
        and inspect.signature(tool).parameters.get("context") is None
    ]

    assert without == []
    assert inspect.signature(unstarted["click"]).parameters["context"].default == (
        DEFAULT_CONTEXT
    )


def test_a_tool_reaches_the_browser_of_the_workspace(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    address = show("<title>Bound</title>")

    assert run(catalogue(space)["where_am_i"]()) == {"url": address, "title": "Bound"}


def test_a_screenshot_is_handed_back_as_a_picture(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    assert isinstance(run(catalogue(space)["screenshot"]()), Picture)


def test_a_refusal_reaches_the_caller(space: Workspace, run: Run) -> None:
    with pytest.raises(ToolError, match="known are back, forward, reload"):
        run(catalogue(space)["go"]("sideways"))
