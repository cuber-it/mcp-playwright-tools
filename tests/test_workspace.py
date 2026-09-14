"""How paths are resolved and checked, scripts permitted, and the workspace built."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from mcp_playwright_tools import (
    Boundary,
    GrantError,
    NotPermittedError,
    OutsideBoundaryError,
    Settings,
    ToolError,
    Workspace,
    workspace_from,
)
from mcp_playwright_tools.boundary import Access
from mcp_playwright_tools.grant import GRANT_FILE, Grant, write_grant


@pytest.fixture
def walled(tmp_path: Path) -> Workspace:
    """Return a guarded workspace confined to ``inside``, scripts off, with grants."""
    inside = tmp_path / "inside"
    inside.mkdir()
    return Workspace(
        working_dir=inside,
        boundary=Boundary((inside,), "guarded", execute=False),
        state_dir=tmp_path / "state",
    )


def test_a_relative_path_starts_in_the_working_directory(walled: Workspace) -> None:
    assert walled.resolve("shots/a.png") == walled.working_dir / "shots" / "a.png"


def test_a_tilde_is_the_home_directory(tmp_path: Path) -> None:
    assert Workspace(working_dir=tmp_path).resolve("~/a.png") == Path.home() / "a.png"


def test_reading_reaches_outside_the_roots_when_guarded(
    walled: Workspace, tmp_path: Path
) -> None:
    assert walled.resolve("../outside.txt") == tmp_path / "outside.txt"


def test_writing_outside_the_roots_names_the_grant_that_would_allow_it(
    walled: Workspace, tmp_path: Path
) -> None:
    with pytest.raises(OutsideBoundaryError, match="for write") as refused:
        walled.resolve("../shot.png", Access.WRITE)

    assert f"set --root {tmp_path} --for 1h" in str(refused.value)


def test_a_symlink_inside_does_not_carry_writing_outside(
    walled: Workspace, tmp_path: Path
) -> None:
    (walled.working_dir / "door").symlink_to(tmp_path)

    with pytest.raises(OutsideBoundaryError):
        walled.resolve("door/shot.png", Access.WRITE)


def test_strict_confines_reading_too(walled: Workspace) -> None:
    walled.boundary = Boundary(walled.boundary.roots, "strict")

    with pytest.raises(OutsideBoundaryError, match="for read"):
        walled.resolve("../outside.txt")


def test_a_grant_lets_writing_reach_an_added_root(
    walled: Workspace, tmp_path: Path
) -> None:
    write_grant(walled.state_dir, Grant(time.time() + 60, roots=(tmp_path,)))

    assert walled.resolve("../shot.png", Access.WRITE) == tmp_path / "shot.png"


def test_a_lapsed_grant_reaches_no_further(walled: Workspace, tmp_path: Path) -> None:
    write_grant(walled.state_dir, Grant(time.time() - 1, roots=(tmp_path,)))

    with pytest.raises(OutsideBoundaryError):
        walled.resolve("../shot.png", Access.WRITE)


def test_an_unusable_grant_file_refuses_even_reading(walled: Workspace) -> None:
    walled.state_dir.mkdir()
    (walled.state_dir / GRANT_FILE).write_text("not json", encoding="utf-8")

    with pytest.raises(GrantError):
        walled.resolve("a.png")


@pytest.mark.parametrize("mode", ["open", "guarded", "strict"])
@pytest.mark.parametrize("target", ["grant.json", "."])
def test_the_grant_file_and_its_directory_are_out_of_reach_for_writing(
    tmp_path: Path, mode: str, target: str
) -> None:
    state = tmp_path / "state"
    space = Workspace(
        working_dir=tmp_path, boundary=Boundary(mode=mode), state_dir=state
    )
    write_grant(state, Grant(time.time() + 60, execute=True))

    with pytest.raises(NotPermittedError, match="grant file"):
        space.resolve(str(state / target), Access.WRITE)


def test_writing_beside_the_state_directory_is_not_mistaken_for_the_grant(
    tmp_path: Path,
) -> None:
    space = Workspace(working_dir=tmp_path, state_dir=tmp_path / "state")

    assert space.resolve("shot.png", Access.WRITE) == tmp_path / "shot.png"


def test_switched_off_scripts_are_refused_with_the_grant(walled: Workspace) -> None:
    with pytest.raises(NotPermittedError, match="set --exec --for 1h"):
        walled.permit_execute()


def test_a_grant_switches_scripts_on(walled: Workspace) -> None:
    write_grant(walled.state_dir, Grant(time.time() + 60, execute=True))

    assert walled.permit_execute() is None


def test_without_a_state_directory_a_refusal_says_grants_need_one(
    walled: Workspace,
) -> None:
    walled.state_dir = None

    with pytest.raises(NotPermittedError, match="--state-dir"):
        walled.permit_execute()


def test_the_configuration_is_read(tmp_path: Path) -> None:
    space = workspace_from(
        {
            "working_dir": str(tmp_path),
            "allowed_roots": [str(tmp_path)],
            "mode": "strict",
            "execute": False,
            "state_dir": str(tmp_path / "state"),
            "browser": "firefox",
            "channel": "beta",
            "headless": False,
            "timeout": "5",
            "idle": 0,
        }
    )

    assert space.working_dir == tmp_path
    assert space.boundary == Boundary((tmp_path,), "strict", execute=False)
    assert space.state_dir == tmp_path / "state"
    assert space.pool.settings == Settings("firefox", "beta", False, 5.0, 0.0)


def test_an_empty_configuration_takes_the_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    space = workspace_from({})

    assert space.working_dir == tmp_path.resolve()
    assert space.boundary == Boundary()
    assert space.state_dir is None
    assert space.pool.settings == Settings()


def test_a_working_directory_that_is_no_directory_is_refused(tmp_path: Path) -> None:
    afile = tmp_path / "afile"
    afile.write_text("x", encoding="utf-8")

    with pytest.raises(ToolError, match="not a directory"):
        workspace_from({"working_dir": str(afile)})


@pytest.mark.parametrize(
    ("setting", "message"),
    [
        ({"mode": "loose"}, "no such mode"),
        ({"browser": "lynx"}, "no such browser: lynx; known are chromium"),
        ({"timeout": 0}, "timeout has to be positive"),
        ({"idle": -1}, "idle cannot be negative"),
        ({"timeout": "soon"}, "have to be numbers"),
    ],
)
def test_an_unusable_setting_is_refused(
    tmp_path: Path, setting: dict[str, object], message: str
) -> None:
    with pytest.raises(ToolError, match=message):
        workspace_from({"working_dir": str(tmp_path), **setting})
