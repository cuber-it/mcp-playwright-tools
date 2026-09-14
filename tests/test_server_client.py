"""The server as a client sees it, in process.

A client built on the server object speaks to it directly, without a port or a
subprocess, and negotiates the current protocol revision while doing it. That
makes this the place to pin what a caller actually receives: above all that a
screenshot arrives as an image content block.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from mcp import Client

from conftest import EXPECTED, Run
from loopback import Site
from mcp_playwright_tools import Workspace
from mcp_playwright_tools.server import app

CURRENT_REVISION = "2026-07-28"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def served(space: Workspace, run: Run, work: Callable[[Any], Awaitable[Any]]) -> Any:
    """Run one piece of client work against a server on this workspace."""
    built = app.build(space)

    async def talk() -> Any:
        async with Client(built) as client:
            return await work(client)

    return run(talk())


def called(space: Workspace, run: Run, name: str, arguments: dict[str, Any]) -> Any:
    """Call one tool through a client and return its answer."""

    async def work(client: Any) -> Any:
        return await client.call_tool(name, arguments)

    return served(space, run, work)


def test_the_current_revision_is_spoken(space: Workspace, run: Run) -> None:
    async def work(client: Any) -> Any:
        return client.protocol_version

    assert served(space, run, work) == CURRENT_REVISION


def test_the_server_names_itself(space: Workspace, run: Run) -> None:
    async def work(client: Any) -> Any:
        return client.server_info

    info = served(space, run, work)

    assert info.name == "mcp-playwright-tools"
    assert info.version


def test_the_tools_are_offered_with_descriptions(space: Workspace, run: Run) -> None:
    async def work(client: Any) -> Any:
        return await client.list_tools()

    listed = served(space, run, work).tools

    assert {tool.name for tool in listed} == EXPECTED
    assert [tool.name for tool in listed if not tool.description] == []


def test_a_page_is_opened_and_read_through_the_client(
    space: Workspace, site: Site, run: Run
) -> None:
    address = site.page("<h1>Served</h1>")

    opened = called(space, run, "open_url", {"url": address})
    text = called(space, run, "read", {"target": "h1"})

    assert opened.content[0].text == f"at {address}"
    assert text.content[0].text == "Served"


def test_a_screenshot_arrives_as_an_image(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    answer = called(space, run, "screenshot", {})

    [block] = answer.content
    assert (block.type, block.mime_type) == ("image", "image/png")
    assert base64.b64decode(block.data).startswith(PNG_SIGNATURE)


def test_a_saved_screenshot_arrives_as_the_line_naming_the_file(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    answer = called(space, run, "screenshot", {"save_to": "page.png"})

    assert not answer.is_error
    assert answer.content[0].text.startswith(f"wrote {space.working_dir / 'page.png'}")


def test_a_description_arrives_as_structured_content(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<button id='go'>Go</button>")

    answer = called(space, run, "describe", {"target": "#go"})

    assert answer.structured_content["describes"] == "<button> Go"
    assert answer.structured_content["matches"] == 1


def test_a_script_result_arrives_as_json_text(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")

    answer = called(space, run, "run_javascript", {"script": "({n: 1 + 1})"})

    assert not answer.is_error
    assert answer.content[0].text.replace(" ", "").replace("\n", "") == '{"n":2}'


def test_a_refusal_arrives_with_the_grant_that_lifts_it(
    fenced: Workspace, run: Run, tmp_path: Path
) -> None:
    arguments = {"target": "#up", "paths": "../token.txt"}

    answer = called(fenced, run, "attach_files", arguments)

    assert answer.is_error
    assert f"set --root {tmp_path} --for 1h" in answer.content[0].text
