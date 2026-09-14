# Development

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

The tests drive a real browser. By default they start the Chrome installed on
the machine; `MCP_PLAYWRIGHT_TEST_CHANNEL` names another installed browser, and
set empty it makes the tests use the one Playwright brings along, which
`.venv/bin/playwright install chromium` downloads.

## Checks

All of them have to pass before a change is committed.

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m pylint src tests
.venv/bin/python -m pytest
shellcheck scripts/grant.sh
```

The limits are those in `pyproject.toml`: line length 88, cyclomatic complexity
10, and pylint's design checks. What a linter reports is taken apart, not
silenced.

The tests need no network beyond the loopback interface: pages come from a
small site and the authentication tests ask a stand-in authorization server,
both in `tests/loopback.py`. Temporary directories go to `.pytest-tmp` rather
than `/tmp`, which the boundary always admits; there a refusal a test expects
would not happen. One browser
serves the whole run on one event loop; a few tests start a browser of their
own, where stopping and starting it is what they check.

## Release

1. Raise `version` in `pyproject.toml` and describe the change in `CHANGES.md`.
2. Build into an empty directory and check both archives:

   ```bash
   .venv/bin/python -m build --outdir /tmp/mcp-playwright-tools-dist
   .venv/bin/python -m twine check --strict /tmp/mcp-playwright-tools-dist/*
   ```

3. Upload with an API token of the PyPI account that owns
   `mcp-playwright-tools`; twine asks for it, the user name is `__token__`:

   ```bash
   .venv/bin/python -m twine upload /tmp/mcp-playwright-tools-dist/*
   ```

The wheel holds the package only. The source archive also carries the tests,
the documentation, `scripts/` and `CHANGES.md` (see `MANIFEST.in`), and the
test suite passes from it.

## Layout

```text
src/mcp_playwright_tools/
  __init__.py        public names of the library
  errors.py          ToolError and its subclasses, Playwright failures as refusals
  boundary.py        roots, upload directories, mode: what may be reached
  grant.py           reading and writing grants
  workspace.py       the shared state; every path check happens here
  pool.py            the browser, named contexts, tabs, the idle sweep
  locate.py          the ways of pointing at an element
  output.py          cutting long text and listings
  navigate.py        pages, history, tabs, frames
  examine.py         finding, describing, what can be done, the outline
  act.py             clicking, filling, keys, dropdowns, dragging, files, scripts
  read.py            text, markup, attributes, links, screenshots, waiting
  keep.py            cookies, local storage, intercepted requests, contexts
  cli.py             pw-browse
  server/
    registry.py      the tools as a catalogue, no SDK
    auth.py          token checks and their configuration, no SDK
    app.py           the MCP server, the only module importing the SDK
  tools/
    mcp_playwright_grant.py  the grant program, part of the package
scripts/
  grant.sh           runs the grant program with the repository's venv
tests/
doc/
```

## Rules the code keeps

- **One module imports the SDK.** Only `server/app.py` imports `mcp`; Ruff
  refuses it anywhere else, and a test makes sure the library, the catalogue
  and `pw-browse` load without it.
- **A tool on a page takes a `Browsing`**, a workspace and a context name bound
  together by `space.browsing(name)`; nothing is opened until the tool asks
  for its spot. Only `contexts` takes the workspace, since it spans them all.
- **The tools are coroutines, and so is their wrapper in the server.** The SDK
  awaits only what it sees declared as a coroutine function.
- **A picture leaves the library as a `Picture`.** The server turns it into the
  SDK's image and puts `Image` into the return type; with `Picture` there, the
  SDK builds an output schema and every call fails.
- **Every path check happens in `workspace.py`.** A tool names the access it
  needs and never checks a path itself.
- **Refusals are `ToolError`s.** What Playwright reports goes through
  `errors.attempt` and arrives as a refusal saying what was being done; a value
  that is not allowed is refused with the allowed ones named.
- **The docstring of a catalogue entry is the description a client reads.** It
  has an English part, a German paragraph and a line starting with
  `Stichworte:`; a test holds every tool to that.
- **The documentation keeps up.** Tests check that the README names every tool,
  every server option and every environment variable, and links only
  absolutely.
