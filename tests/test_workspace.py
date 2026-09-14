"""How paths are resolved and checked for reading, writing and uploading."""

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
from mcp_playwright_tools.boundary import TMP, Access
from mcp_playwright_tools.grant import GRANT_FILE, Grant, write_grant


@pytest.fixture
def walled(tmp_path: Path) -> Workspace:
    """Return a guarded workspace as a server runs: ``home`` as root, ``work`` in it."""
    home = tmp_path / "home"
    work = home / "work"
    work.mkdir(parents=True)
    return Workspace(
        working_dir=work,
        boundary=Boundary((home,), "guarded", (work,)),
        state_dir=tmp_path / "state",
    )


def later() -> float:
    """Return a moment a minute from now."""
    return time.time() + 60


def test_a_relative_path_starts_in_the_working_directory(walled: Workspace) -> None:
    assert walled.resolve("shots/a.png") == walled.working_dir / "shots" / "a.png"


def test_a_tilde_is_the_home_directory(tmp_path: Path) -> None:
    assert Workspace(working_dir=tmp_path).resolve("~/a.png") == Path.home() / "a.png"


def test_reading_reaches_outside_the_roots_when_guarded(
    walled: Workspace, tmp_path: Path
) -> None:
    assert walled.resolve("../../outside.html") == tmp_path / "outside.html"


def test_writing_reaches_the_whole_root(walled: Workspace, tmp_path: Path) -> None:
    assert walled.resolve("../shot.png", Access.WRITE) == tmp_path / "home" / "shot.png"


def test_writing_outside_the_roots_names_the_grant_that_would_allow_it(
    walled: Workspace, tmp_path: Path
) -> None:
    with pytest.raises(OutsideBoundaryError, match="for write") as refused:
        walled.resolve("../../shot.png", Access.WRITE)

    assert f"set --root {tmp_path} --for 1h" in str(refused.value)


def test_a_symlink_inside_does_not_carry_writing_outside(
    walled: Workspace, tmp_path: Path
) -> None:
    (walled.working_dir / "door").symlink_to(tmp_path)

    with pytest.raises(OutsideBoundaryError):
        walled.resolve("door/shot.png", Access.WRITE)


def test_strict_confines_reading_too(walled: Workspace) -> None:
    fence = walled.boundary
    walled.boundary = Boundary(fence.roots, "strict", fence.uploads)

    with pytest.raises(OutsideBoundaryError, match="for read"):
        walled.resolve("../../outside.html")


def test_files_are_uploaded_from_the_working_directory(walled: Workspace) -> None:
    assert walled.resolve("report.pdf", Access.UPLOAD) == (
        walled.working_dir / "report.pdf"
    )


def test_an_upload_from_elsewhere_in_the_home_names_the_grant(
    walled: Workspace, tmp_path: Path
) -> None:
    with pytest.raises(OutsideBoundaryError, match="uploads may come from") as refused:
        walled.resolve("../token.txt", Access.UPLOAD)

    assert f"set --root {tmp_path / 'home'} --for 1h" in str(refused.value)


@pytest.mark.parametrize("mode", ["guarded", "strict"])
@pytest.mark.parametrize("access", [Access.WRITE, Access.UPLOAD])
def test_tmp_is_within_reach_without_a_grant(
    walled: Workspace, mode: str, access: Access
) -> None:
    fence = walled.boundary
    walled.boundary = Boundary(fence.roots, mode, fence.uploads)

    assert walled.resolve(str(TMP / "shot.png"), access) == TMP / "shot.png"


def test_a_grant_adds_a_root_and_an_upload_directory(
    walled: Workspace, tmp_path: Path
) -> None:
    write_grant(walled.state_dir, Grant(later(), roots=(tmp_path,)))

    assert walled.resolve("../../a.txt", Access.UPLOAD) == tmp_path / "a.txt"
    assert walled.resolve("../../a.png", Access.WRITE) == tmp_path / "a.png"


def test_a_lapsed_grant_reaches_no_further(walled: Workspace, tmp_path: Path) -> None:
    write_grant(walled.state_dir, Grant(time.time() - 1, roots=(tmp_path,)))

    with pytest.raises(OutsideBoundaryError):
        walled.resolve("../../a.txt", Access.UPLOAD)


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
    write_grant(state, Grant(later(), mode="open"))

    with pytest.raises(NotPermittedError, match="grant file"):
        space.resolve(str(state / target), Access.WRITE)


def test_writing_beside_the_state_directory_is_not_mistaken_for_the_grant(
    tmp_path: Path,
) -> None:
    space = Workspace(working_dir=tmp_path, state_dir=tmp_path / "state")

    assert space.resolve("shot.png", Access.WRITE) == tmp_path / "shot.png"


def test_the_configuration_is_read(tmp_path: Path) -> None:
    space = workspace_from(
        {
            "working_dir": str(tmp_path),
            "allowed_roots": [str(tmp_path)],
            "mode": "strict",
            "state_dir": str(tmp_path / "state"),
            "browser": "firefox",
            "channel": "beta",
            "headless": False,
            "timeout": "5",
            "idle": 0,
        }
    )

    assert space.working_dir == tmp_path
    assert space.boundary == Boundary((tmp_path,), "strict", (tmp_path,))
    assert space.state_dir == tmp_path / "state"
    assert space.pool.settings == Settings("firefox", "beta", False, 5.0, 0.0)


def test_an_empty_configuration_uploads_from_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    space = workspace_from({})

    assert space.working_dir == tmp_path.resolve()
    assert space.boundary == Boundary((), "guarded", (tmp_path.resolve(),))
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
