"""What a context records: console, network, dialogs, and the downloads."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from conftest import Run, awaiting
from loopback import Site
from mcp_playwright_tools import (
    OutsideBoundaryError,
    ToolError,
    Workspace,
    act,
    keep,
    read,
    watch,
)
from mcp_playwright_tools.record import MAX_ENTRIES, Record

ASKER = (
    "<p id='answer'></p><button id='ask' "
    "onclick=\"answer.textContent = '[' + {question} + ']'\">ask</button>"
)


def answered(
    space: Workspace, show: Callable[[str], str], run: Run, question: str
) -> str:
    """Open a page that asks a question on a click, and return what it was told."""
    show(ASKER.format(question=question))
    run(act.click(space.browsing(), "#ask"))
    run(read.wait_until(space.browsing(), "visible", "#answer:not(:empty)"))
    return run(read.read(space.browsing(), "#answer"))


def downloaded(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> str:
    """Download a small text file in the default context; return its address.

    The link lies on the same site, as a browser ignores ``download`` otherwise.
    """
    address = site.data("hello", "text/plain")
    show(f"<a id='get' href='{address}' download='hello.txt'>get</a>")
    page = run(space.browsing().spot()).page
    run(awaiting(page, "download", act.click(space.browsing(), "#get")))
    return address


def test_console_messages_and_page_errors_are_kept_with_their_tab(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    show("<p>x</p>")
    page = run(space.browsing().spot()).page

    run(awaiting(page, "console", page.evaluate("console.warn('careful')")))
    failing = page.evaluate("setTimeout(() => { throw new Error('boom') })")
    run(awaiting(page, "pageerror", failing))

    entries = run(watch.logs(space.browsing())).splitlines()
    assert "tab 0 warning: careful" in entries
    assert entries.index("tab 0 warning: careful") < entries.index("tab 0 error: boom")


def test_responses_and_failed_requests_are_kept(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    address = show("<p>x</p>")
    run(keep.intercept(space.browsing(), "abort", "**/api/thing"))
    spot = run(space.browsing().spot())

    fetching = spot.page.evaluate("fetch('/api/thing').catch(() => null)")
    run(awaiting(spot.context, "requestfailed", fetching))

    entries = run(watch.logs(space.browsing(), "network")).splitlines()
    assert f"200 GET {address}" in entries
    assert f"failed GET {site.base}/api/thing: net::ERR_FAILED" in entries


def test_entries_are_filtered_by_what_they_contain(space: Workspace, run: Run) -> None:
    record = run(space.browsing().session()).record
    record.console.extend(["tab 0 log: hello", "tab 0 warning: careful"])

    assert run(watch.logs(space.browsing(), contains="care")) == (
        "tab 0 warning: careful"
    )
    assert run(watch.logs(space.browsing(), contains="gone")) == (
        "no console entries with 'gone'"
    )


def test_only_the_latest_entries_are_shown_and_the_earlier_ones_counted(
    space: Workspace, run: Run
) -> None:
    record = run(space.browsing().session()).record
    record.console.extend(f"line {number}" for number in range(250))

    shown = run(watch.logs(space.browsing())).splitlines()

    assert shown[:2] == ["[... 50 earlier]", "line 50"]
    assert shown[-1] == "line 249"


def test_a_record_lets_the_oldest_entries_go() -> None:
    record = Record()

    record.network.extend(str(number) for number in range(MAX_ENTRIES + 1))

    assert len(record.network) == MAX_ENTRIES
    assert record.network[0] == "1"


def test_clearing_a_log_empties_that_one_only(space: Workspace, run: Run) -> None:
    record = run(space.browsing().session()).record
    record.console.append("tab 0 log: hello")
    record.network.append("200 GET http://127.0.0.1/")

    assert run(watch.logs(space.browsing(), "console", "clear")) == (
        "console log cleared"
    )
    assert run(watch.logs(space.browsing())) == "no console entries"
    assert run(watch.logs(space.browsing(), "network")) == "200 GET http://127.0.0.1/"


@pytest.mark.parametrize(
    ("kind", "action", "message"),
    [
        ("errors", "read", "known are console, network, dialogs"),
        ("console", "drop", "known are read, clear"),
    ],
)
def test_an_unknown_log_or_action_names_the_known_ones(
    space: Workspace, run: Run, kind: str, action: str, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(watch.logs(space.browsing(), kind, action))


def test_a_dialog_is_accepted_unless_told_otherwise_and_logged(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    assert answered(space, show, run, "confirm('Sure?')") == "[true]"
    assert run(watch.logs(space.browsing(), "dialogs")) == (
        "tab 0 confirm: Sure? -> accepted"
    )


def test_dialogs_are_dismissed_when_told_so(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    assert run(watch.dialogs(space.browsing(), "dismiss")) == "dialogs are dismissed"
    assert answered(space, show, run, "confirm('Sure?')") == "[false]"
    assert run(watch.logs(space.browsing(), "dialogs")) == (
        "tab 0 confirm: Sure? -> dismissed"
    )


def test_a_prompt_gets_the_answer_it_was_given(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    assert run(watch.dialogs(space.browsing(), "accept", "Ada")) == (
        "dialogs are accepted, prompts answered with 'Ada'"
    )
    assert answered(space, show, run, "prompt('Name?')") == "[Ada]"


def test_a_prompt_without_an_answer_gets_its_default(
    space: Workspace, show: Callable[[str], str], run: Run
) -> None:
    assert answered(space, show, run, "prompt('Name?', 'Bob')") == "[Bob]"


@pytest.mark.parametrize(
    ("answer", "text", "message"),
    [
        ("ignore", "", "known are accept, dismiss"),
        ("dismiss", "Ada", "an answer to prompts only goes with accept"),
    ],
)
def test_a_way_of_answering_dialogs_that_does_not_fit_is_refused(
    space: Workspace, run: Run, answer: str, text: str, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(watch.dialogs(space.browsing(), answer, text))


def test_a_download_is_listed_and_saved_to_a_file(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    address = downloaded(space, show, site, run)
    saved = space.working_dir / "saved.txt"

    assert run(watch.downloads(space.browsing())) == f"0: hello.txt - {address}"
    assert run(watch.downloads(space.browsing(), "save", 0, "saved.txt")) == (
        f"saved download 0 to {saved}"
    )
    assert saved.read_text(encoding="utf-8") == "hello"


def test_a_download_saved_to_a_directory_keeps_its_name(
    space: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    (space.working_dir / "got").mkdir()
    downloaded(space, show, site, run)

    run(watch.downloads(space.browsing(), "save", 0, "got"))

    saved = space.working_dir / "got" / "hello.txt"
    assert saved.read_text(encoding="utf-8") == "hello"


def test_a_download_is_not_saved_outside_the_roots(
    fenced: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    downloaded(fenced, show, site, run)
    outside = fenced.working_dir.parent / "out.txt"

    with pytest.raises(OutsideBoundaryError, match="outside the allowed roots"):
        run(watch.downloads(fenced.browsing(), "save", 0, str(outside)))

    assert not outside.exists()


def test_a_download_into_a_directory_does_not_follow_a_link_out_of_the_roots(
    fenced: Workspace, show: Callable[[str], str], site: Site, run: Run
) -> None:
    downloaded(fenced, show, site, run)
    outside = fenced.working_dir.parent / "outside.txt"
    (fenced.working_dir / "hello.txt").symlink_to(outside)

    with pytest.raises(OutsideBoundaryError, match="outside the allowed roots"):
        run(watch.downloads(fenced.browsing(), "save", 0, "."))

    assert not outside.exists()


def test_a_context_without_downloads_says_so(space: Workspace, run: Run) -> None:
    assert run(watch.downloads(space.browsing())) == "no downloads"


@pytest.mark.parametrize(
    ("action", "save_to", "message"),
    [
        ("save", "x.txt", r"no download 0; there are 0"),
        ("save", "", "saving a download needs save_to"),
        ("open", "", "known are list, save"),
    ],
)
def test_a_download_that_cannot_be_saved_is_refused(
    space: Workspace, run: Run, action: str, save_to: str, message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        run(watch.downloads(space.browsing(), action, 0, save_to))
