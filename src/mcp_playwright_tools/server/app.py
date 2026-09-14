"""The server: the browser tools over stdio or HTTP, through the MCP SDK.

This is the only module that imports the SDK. It takes the catalogue from
:mod:`mcp_playwright_tools.server.registry` and the authentication from
:mod:`mcp_playwright_tools.server.auth` and hands both to the SDK, so a change
in the SDK is felt here and nowhere else.
"""

from __future__ import annotations

import argparse
import functools
import inspect
import operator
import os
import sys
from pathlib import Path
from typing import Any, get_args, get_type_hints

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError as AnticipatedError

from mcp_playwright_tools import __version__
from mcp_playwright_tools.boundary import DEFAULT_MODE, MODES
from mcp_playwright_tools.errors import ToolError
from mcp_playwright_tools.grant import DEFAULT_STATE_DIR
from mcp_playwright_tools.pool import BROWSERS, DEFAULT_IDLE, DEFAULT_TIMEOUT
from mcp_playwright_tools.read import Picture
from mcp_playwright_tools.server.auth import (
    AuthConfig,
    ConfigurationError,
    TokenCheck,
    auth_from_environment,
    guard_exposure,
)
from mcp_playwright_tools.server.registry import Tool, catalogue
from mcp_playwright_tools.workspace import Workspace, workspace_from

INSTRUCTIONS = (
    "Browser tools: open pages, find and act on elements, read what is there, "
    "take screenshots and PDFs, work with tabs, frames, cookies, requests, "
    "dialogs and downloads, read the console and network logs. Every tool takes "
    "context, a name; each name is a browser context of its own with its own "
    "cookies and tabs. A tab a page opens becomes the active tab. Close "
    "contexts with the contexts tool when done. Files are written to /tmp or the "
    "allowed roots and uploaded from the working directory or /tmp; anything "
    "else is refused with the grant call a person runs on the host.\n\n"
    "Browser-Werkzeuge: Seiten öffnen, Elemente finden und bedienen, Inhalte "
    "lesen, Bildschirmfotos und PDFs, Tabs, Frames, Cookies, Anfragen, Dialoge "
    "und Downloads, Konsole und Netzwerkprotokoll. Jedes Werkzeug nimmt context, "
    "einen Namen; jeder Name ist ein eigener Browser-Kontext mit eigenen Cookies "
    "und Tabs. Ein Tab, den eine Seite öffnet, wird zum aktiven Tab. Wenn "
    "fertig, Kontexte mit dem Werkzeug contexts schließen. Dateien gehen nach "
    "/tmp oder in die erlaubten Wurzeln, hochgeladen wird aus dem "
    "Arbeitsverzeichnis oder /tmp; alles andere wird mit dem Freigabe-Aufruf "
    "abgelehnt, den ein Mensch auf dem Host ausführt."
)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
REFUSED = 2


def _published(tool: Tool) -> Tool:
    """Wrap a tool for the SDK: refusals keep their reason, pictures become images.

    The SDK tells a deliberate refusal from a crash by the exception class:
    its own ``ToolError`` reaches the caller carrying its message, while
    anything else is a crash and the caller is told no more than "Error
    executing tool <name>". The tools raise our own ``ToolError``, which would
    land in that second case. Only those are translated; any other exception
    stays a crash.

    A :class:`Picture` is answered as the SDK's ``Image``, which reaches the
    client as an image content block. The SDK builds the output schema from
    the return annotation, so ``Picture`` becomes ``Image`` there as well.

    The tools are coroutines, and so is the wrapper: the SDK awaits only what
    it sees declared as a coroutine function.
    """

    @functools.wraps(tool)
    async def translated(*args: Any, **kwargs: Any) -> Any:
        try:
            result = await tool(*args, **kwargs)
        except ToolError as err:
            raise AnticipatedError(str(err)) from err
        if isinstance(result, Picture):
            return Image(data=result.data, format=result.image_format.lower())
        return result

    returned = get_type_hints(tool).get("return")
    parts = get_args(returned) or (returned,)
    if Picture in parts:
        shown = functools.reduce(
            operator.or_, [Image if part is Picture else part for part in parts]
        )
        signature = inspect.signature(tool).replace(return_annotation=shown)
        translated.__signature__ = signature
        translated.__annotations__ = {**tool.__annotations__, "return": shown}
    return translated


class _Verifier:
    """Answers the SDK's question about a token by asking a :class:`TokenCheck`."""

    def __init__(self, check: TokenCheck) -> None:
        """Bind the verifier to the check it asks."""
        self._check = check

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return the SDK's access token for a valid token, None otherwise."""
        info = await self._check.check(token)
        if info is None:
            return None
        return AccessToken(
            token=token,
            client_id=info.client_id,
            scopes=list(info.scopes),
            subject=info.subject,
            expires_at=info.expires_at,
        )


def _auth_arguments(auth: AuthConfig | None) -> dict[str, Any]:
    """Translate the authentication for the SDK's constructor.

    Resource validation stays off: it is not established that the authorization
    server names the resource a token was issued for.
    """
    if auth is None:
        return {}
    return {
        "token_verifier": _Verifier(auth.check),
        "auth": AuthSettings(
            issuer_url=auth.issuer_url,
            resource_server_url=auth.resource_url,
            required_scopes=list(auth.required_scopes),
            validate_token_resource=False,
        ),
    }


def build(space: Workspace, auth: AuthConfig | None = None) -> MCPServer:
    """Return a server with the browser tools published on it.

    With ``auth``, every HTTP request has to carry a bearer token the check
    accepts, and the server publishes its protected resource metadata. stdio
    is not affected, because a pipe carries no token.
    """
    server = MCPServer(
        name="mcp-playwright-tools",
        version=__version__,
        instructions=INSTRUCTIONS,
        **_auth_arguments(auth),
    )
    for name, tool in catalogue(space).items():
        server.add_tool(_published(tool), name=name)
    return server


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the server's arguments; host and port default to the environment."""
    parser = argparse.ArgumentParser(
        prog="mcp-playwright-tools",
        description="Serve the browser tools over MCP. Authentication is read from "
        "MCP_OAUTH_ENABLED, MCP_OAUTH_SERVER_URL, MCP_PUBLIC_URL and "
        "MCP_AUTH_METHOD.",
    )
    serving = parser.add_argument_group("serving")
    serving.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="stdio for a client that starts the server itself, "
        "streamable-http to listen on a port (default: stdio)",
    )
    serving.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", DEFAULT_HOST),
        help="HTTP: address to bind (default: MCP_HOST or 127.0.0.1)",
    )
    serving.add_argument(
        "--port",
        type=int,
        default=os.environ.get("MCP_PORT", str(DEFAULT_PORT)),
        help="HTTP: port to bind (default: MCP_PORT or 8000)",
    )
    serving.add_argument(
        "--path", default="/mcp", help="HTTP: path the server answers on"
    )
    _boundary_arguments(parser)
    _browser_arguments(parser)
    return parser.parse_args(argv)


def _boundary_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the options for the working directory, the boundary and grants."""
    group = parser.add_argument_group("boundary")
    group.add_argument(
        "--working-dir",
        default=str(Path.cwd()),
        help="Where relative paths start and files are uploaded from "
        "(default: the current directory)",
    )
    group.add_argument(
        "--allowed-root",
        action="append",
        default=[],
        metavar="PATH",
        help="Where screenshots may be written besides /tmp; repeatable "
        "(default: the home directory)",
    )
    group.add_argument(
        "--state-dir",
        default=DEFAULT_STATE_DIR,
        help="Where the grant is kept; empty for no grants (default: %(default)s)",
    )
    group.add_argument(
        "--mode",
        choices=MODES,
        default=DEFAULT_MODE,
        help="open lifts every limit, guarded confines writing and uploads, "
        f"strict confines reading too (default: {DEFAULT_MODE})",
    )


def _browser_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the options for starting the browser and keeping its contexts."""
    group = parser.add_argument_group("browser")
    group.add_argument(
        "--browser",
        choices=BROWSERS,
        default="chromium",
        help="Engine to start (default: %(default)s)",
    )
    group.add_argument(
        "--channel",
        default="",
        help="An installed browser to start instead, such as chrome "
        "(default: the one Playwright brings along)",
    )
    group.add_argument("--headed", action="store_true", help="Show the browser window")
    group.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Seconds a single action may take (default: %(default)s)",
    )
    group.add_argument(
        "--idle",
        type=float,
        default=DEFAULT_IDLE,
        help="Seconds a context may go unused before it is closed; 0 keeps "
        "them (default: %(default)s)",
    )


def workspace_from_args(args: argparse.Namespace) -> Workspace:
    """Build the workspace the tools will share.

    Raises:
        ToolError: The working directory does not exist, or a browser setting
            is unusable.
    """
    settings: dict[str, Any] = {
        "working_dir": args.working_dir,
        "allowed_roots": args.allowed_root or [str(Path.home())],
        "mode": args.mode,
        "browser": args.browser,
        "channel": args.channel,
        "headless": not args.headed,
        "timeout": args.timeout,
        "idle": args.idle,
    }
    if args.state_dir:
        settings["state_dir"] = args.state_dir
    return workspace_from(settings)


def main(argv: list[str] | None = None) -> int:
    """Run the server until it is stopped.

    Returns:
        0 after the server stopped, 2 when the configuration was refused
        before it started.
    """
    args = parse(argv)
    try:
        auth = auth_from_environment(os.environ, args.path)
        guard_exposure(args.transport, args.host, auth)
        space = workspace_from_args(args)
    except (ConfigurationError, ToolError) as err:
        print(f"mcp-playwright-tools: {err}", file=sys.stderr)
        return REFUSED

    server = build(space, auth)
    if args.transport == "stdio":
        server.run("stdio")
        return 0

    # Sessionless: nothing ties a caller to this process between requests.
    server.run(
        "streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path=args.path,
        stateless_http=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
