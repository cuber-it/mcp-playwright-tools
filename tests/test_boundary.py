"""Where reading, writing and uploading may reach in each mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_playwright_tools import Boundary, ToolError
from mcp_playwright_tools.boundary import TMP, Access

HOME = Path("/home/someone")
WORK = HOME / "Workspace"
OUTSIDE = Path("/etc/hostname")
FENCE = Boundary((HOME,), "guarded", (WORK,))


def test_guarded_is_the_default_mode() -> None:
    assert Boundary().mode == "guarded"


def test_an_unknown_mode_is_refused() -> None:
    with pytest.raises(ToolError, match="no such mode"):
        Boundary(mode="loose")


@pytest.mark.parametrize(
    ("mode", "access", "admitted"),
    [
        ("open", Access.READ, True),
        ("open", Access.WRITE, True),
        ("open", Access.UPLOAD, True),
        ("guarded", Access.READ, True),
        ("guarded", Access.WRITE, False),
        ("guarded", Access.UPLOAD, False),
        ("strict", Access.READ, False),
        ("strict", Access.WRITE, False),
        ("strict", Access.UPLOAD, False),
    ],
)
def test_the_mode_decides_how_far_the_limits_reach(
    mode: str, access: Access, admitted: bool
) -> None:
    assert Boundary((HOME,), mode, (WORK,)).admits(OUTSIDE, access) is admitted


@pytest.mark.parametrize("mode", ["open", "guarded", "strict"])
def test_tmp_is_within_reach_for_every_access_in_every_mode(mode: str) -> None:
    boundary = Boundary((HOME,), mode, (WORK,))

    assert all(boundary.admits(TMP / "shots" / "a.png", access) for access in Access)
    assert all(boundary.admits(TMP, access) for access in Access)


def test_a_directory_that_only_starts_like_tmp_is_not_tmp() -> None:
    assert not FENCE.admits(Path("/tmpfiles/a.png"), Access.WRITE)


def test_writing_reaches_the_home_but_uploads_only_the_working_directory() -> None:
    secret = HOME / ".ssh" / "id_ed25519"

    assert FENCE.admits(secret, Access.WRITE)
    assert not FENCE.admits(secret, Access.UPLOAD)
    assert FENCE.admits(WORK / "report.pdf", Access.UPLOAD)


def test_a_sibling_with_a_shared_prefix_is_outside() -> None:
    assert not FENCE.admits(HOME / "Workspace-old" / "a.pdf", Access.UPLOAD)


def test_without_roots_or_upload_directories_nothing_is_confined() -> None:
    boundary = Boundary(mode="strict")

    assert all(boundary.admits(OUTSIDE, access) for access in Access)


def test_the_test_directories_lie_outside_tmp(tmp_path: Path) -> None:
    """Otherwise every refusal the tests expect would be admitted as /tmp."""
    assert TMP not in tmp_path.resolve().parents
