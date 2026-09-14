"""What tests run on the loopback interface: free ports, an issuer, a web site."""

from __future__ import annotations

import json
import socket
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs

POLL_SECONDS = 0.01
HTML = "text/html; charset=utf-8"


def free_port() -> int:
    """Return a loopback port nothing listens on right now."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def _serving(handler: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    """Serve a handler on a free loopback port for as long as the block lasts.

    Yields:
        The base URL it listens on.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": POLL_SECONDS},
        daemon=True,
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@dataclass
class Issuer:
    """What the stand-in authorization server answers, and what it was asked.

    Attributes:
        url: Base URL it listens on.
        answer: Object sent back as JSON.
        status: HTTP status sent back.
        body: Raw body sent instead of ``answer`` when set.
        tokens: The tokens it was asked about, in order.
    """

    url: str = ""
    answer: Any = field(default_factory=lambda: {"active": False})
    status: int = 200
    body: bytes | None = None
    tokens: list[str] = field(default_factory=list)

    @property
    def introspection(self) -> str:
        """Return the URL of the introspection endpoint."""
        return f"{self.url}/introspect"


@contextmanager
def serve_issuer() -> Iterator[Issuer]:
    """Run a stand-in authorization server for as long as the block lasts."""
    issuer = Issuer()

    class Introspection(BaseHTTPRequestHandler):
        """Answers every POST from the state of ``issuer``."""

        def do_POST(self) -> None:
            """Record the token asked about and send the configured answer."""
            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode())
            issuer.tokens.extend(form.get("token", []))
            body = issuer.body
            if body is None:
                body = json.dumps(issuer.answer).encode()
            self.send_response(issuer.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            """Keep the test output quiet."""

    with _serving(Introspection) as base:
        issuer.url = base
        yield issuer


@dataclass(frozen=True)
class Response:
    """What one address of the site answers.

    Attributes:
        status: HTTP status.
        content_type: Value of the Content-Type header.
        body: The body.
        location: Where a redirect points, empty for none.
    """

    status: int
    content_type: str
    body: bytes
    location: str = ""


NOT_FOUND = Response(404, "text/plain", b"not here")


@dataclass
class Site:
    """The answers of the site by path, each under an address of its own.

    Attributes:
        base: Base URL the site listens on.
        responses: What each path answers.
    """

    base: str = ""
    responses: dict[str, Response] = field(default_factory=dict)

    def page(self, markup: str) -> str:
        """Serve HTML under a fresh address and return it."""
        return self._served(Response(200, HTML, markup.encode()))

    def data(self, body: str, content_type: str = "application/json") -> str:
        """Serve a body of any type under a fresh address and return it."""
        return self._served(Response(200, content_type, body.encode()))

    def redirect(self, to: str) -> str:
        """Serve a redirect to another address under a fresh one and return it."""
        return self._served(Response(302, "text/plain", b"", location=to))

    def _served(self, response: Response) -> str:
        """File a response under a fresh path and return its address."""
        path = f"/{uuid.uuid4().hex}"
        self.responses[path] = response
        return self.base + path


@contextmanager
def serve_site() -> Iterator[Site]:
    """Run the web site for as long as the block lasts."""
    site = Site()

    class Pages(BaseHTTPRequestHandler):
        """Answers every GET from the responses of ``site``."""

        def do_GET(self) -> None:
            """Send what the path was filed with, or a 404."""
            response = site.responses.get(self.path.split("?")[0], NOT_FOUND)
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            if response.location:
                self.send_header("Location", response.location)
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, *_args: Any) -> None:
            """Keep the test output quiet."""

    with _serving(Pages) as base:
        site.base = base
        yield site
