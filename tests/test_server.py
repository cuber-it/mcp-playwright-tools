"""The server: its arguments, the workspace it builds, and what it publishes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver import exceptions

from conftest import EXPECTED, Run
from mcp_playwright_tools import Boundary, Settings, Workspace
from mcp_playwright_tools.grant import DEFAULT_STATE_DIR
from mcp_playwright_tools.server import app

SWITCHED_ON = {
    "MCP_OAUTH_ENABLED": "true",
    "MCP_OAUTH_SERVER_URL": "https://issuer.example/",
    "MCP_PUBLIC_URL": "https://mcp.example/",
}


def published(tmp_path: Path, run: Run) -> dict[str, Any]:
    """Return the tools a server on a fresh workspace publishes, by name."""
    tools = run(app.build(Workspace(working_dir=tmp_path)).list_tools())
    return {tool.name: tool for tool in tools}


def test_stdio_is_the_default() -> None:
    assert app.parse([]).transport == "stdio"


def test_the_legacy_sse_transport_is_not_offered() -> None:
    with pytest.raises(SystemExit):
        app.parse(["--transport", "sse"])


def test_the_http_arguments_are_read() -> None:
    args = app.parse(
        ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "12206"]
    )

    assert (args.transport, args.host, args.port) == (
        "streamable-http",
        "0.0.0.0",
        12206,
    )


def test_host_and_port_default_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "12250")

    args = app.parse([])

    assert (args.host, args.port) == ("0.0.0.0", 12250)


def test_an_unusable_port_in_the_environment_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MCP_PORT", "abc")

    with pytest.raises(SystemExit) as refused:
        app.parse([])

    assert refused.value.code == app.REFUSED
    assert "invalid int value" in capsys.readouterr().err


def test_the_path_defaults_to_mcp_and_can_be_moved() -> None:
    assert app.parse([]).path == "/mcp"
    assert app.parse(["--path", "/playwright"]).path == "/playwright"


def test_the_workspace_carries_the_boundary_arguments(tmp_path: Path) -> None:
    args = app.parse(
        [
            "--working-dir",
            str(tmp_path),
            "--allowed-root",
            str(tmp_path),
            "--mode",
            "strict",
            "--exec",
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )

    space = app.workspace_from_args(args)

    assert space.boundary == Boundary((tmp_path,), "strict", execute=True)
    assert space.state_dir == tmp_path / "state"


def test_the_workspace_carries_the_browser_arguments(tmp_path: Path) -> None:
    args = app.parse(
        [
            "--working-dir",
            str(tmp_path),
            "--browser",
            "firefox",
            "--channel",
            "beta",
            "--headed",
            "--timeout",
            "5",
            "--idle",
            "0",
        ]
    )

    settings = app.workspace_from_args(args).pool.settings

    assert settings == Settings("firefox", "beta", False, 5.0, 0.0)


def test_by_default_the_home_is_the_root_scripts_are_off_and_grants_are_kept(
    tmp_path: Path,
) -> None:
    space = app.workspace_from_args(app.parse(["--working-dir", str(tmp_path)]))

    assert space.boundary == Boundary((Path.home().resolve(),), "guarded", False)
    assert space.state_dir == Path(DEFAULT_STATE_DIR).expanduser().resolve()
    assert space.pool.settings == Settings()


def test_an_empty_state_directory_means_no_grants(tmp_path: Path) -> None:
    args = app.parse(["--working-dir", str(tmp_path), "--state-dir", ""])

    assert app.workspace_from_args(args).state_dir is None


def test_the_network_without_authentication_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MCP_OAUTH_ENABLED", raising=False)

    code = app.main(["--transport", "streamable-http", "--host", "0.0.0.0"])

    assert code == app.REFUSED
    assert "without authentication" in capsys.readouterr().err


def test_an_unknown_auth_method_is_refused_before_starting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, value in {**SWITCHED_ON, "MCP_AUTH_METHOD": "carrier-pigeon"}.items():
        monkeypatch.setenv(name, value)

    assert app.main(["--transport", "streamable-http"]) == app.REFUSED
    assert "no such auth method" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    [
        ("--working-dir", "nowhere", "not a directory"),
        ("--timeout", "0", "timeout has to be positive"),
        ("--idle", "-1", "idle cannot be negative"),
    ],
)
def test_an_unusable_workspace_is_refused_before_starting(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argument: str,
    value: str,
    message: str,
) -> None:
    if argument == "--working-dir":
        value = str(tmp_path / value)

    code = app.main(["--working-dir", str(tmp_path), argument, value])

    assert code == app.REFUSED
    assert message in capsys.readouterr().err


def test_the_server_publishes_the_browser_tools(tmp_path: Path, run: Run) -> None:
    assert set(published(tmp_path, run)) == EXPECTED


def test_every_published_tool_carries_its_description(tmp_path: Path, run: Run) -> None:
    tools = published(tmp_path, run)

    assert [name for name, tool in tools.items() if not tool.description] == []


def test_the_input_schema_follows_the_tool_signature(tmp_path: Path, run: Run) -> None:
    schema = published(tmp_path, run)["click"].input_schema

    assert set(schema["properties"]) == {"target", "by", "name", "context"}
    assert schema["required"] == ["target"]


def test_pictures_and_script_results_announce_no_structured_output(
    tmp_path: Path, run: Run
) -> None:
    tools = published(tmp_path, run)

    assert tools["screenshot"].output_schema is None
    assert tools["run_javascript"].output_schema is None
    assert tools["describe"].output_schema["type"] == "object"


def test_the_server_carries_its_instructions(tmp_path: Path) -> None:
    assert app.build(Workspace(working_dir=tmp_path)).instructions == app.INSTRUCTIONS


def test_a_refusal_keeps_its_reason(tmp_path: Path, run: Run) -> None:
    """The SDK blanks a crash but carries its own ToolError through."""
    space = Workspace(
        working_dir=tmp_path, boundary=Boundary(execute=False), state_dir=tmp_path
    )

    with pytest.raises(exceptions.ToolError) as refused:
        run(app.build(space).call_tool("run_javascript", {"script": "1"}))

    assert not isinstance(refused.value, exceptions.UnexpectedToolError)
    assert "set --exec --for 1h" in str(refused.value)
