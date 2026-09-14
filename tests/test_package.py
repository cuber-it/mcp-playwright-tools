"""What the package offers a caller who just imported it."""

from __future__ import annotations

import subprocess
import sys

import mcp_playwright_tools

LOADED_SDK = (
    "import sys, mcp_playwright_tools, mcp_playwright_tools.server.registry, "
    "mcp_playwright_tools.cli; "
    "print(any(name == 'mcp' or name.startswith('mcp.') for name in sys.modules))"
)


def test_everything_promised_is_reachable() -> None:
    missing = [
        name
        for name in mcp_playwright_tools.__all__
        if not hasattr(mcp_playwright_tools, name)
    ]

    assert missing == []


def test_the_version_is_a_string() -> None:
    assert isinstance(mcp_playwright_tools.__version__, str)
    assert mcp_playwright_tools.__version__


def test_the_library_the_catalogue_and_the_cli_do_not_load_the_sdk() -> None:
    finished = subprocess.run(
        [sys.executable, "-c", LOADED_SDK],
        capture_output=True,
        text=True,
        check=True,
    )

    assert finished.stdout.strip() == "False"
