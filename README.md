# mcp-playwright-tools

**Version 8.0 — completely rewritten and revised.**

Browser tools for AI assistants: open pages, find and act on elements, read
what is there, take screenshots and PDFs, work with tabs, frames, cookies,
requests, dialogs and downloads, read the console and the network log.
Twenty-eight tools, usable as a Python library, from the shell, or served over
the Model Context Protocol.

- **The way of pointing is a parameter.** Every tool that works on an element
  takes `by`: `css`, `role`, `text`, `label`, `placeholder` or `testid`.
- **Contexts by name.** Every tool takes `context`. Each name is a browser
  context with its own cookies, storage and tabs, closed when nobody has used
  it for a while; the browser stops with the last one. A context can pass for
  a device such as a phone, and its login can be saved and used again.
- **Nothing gets lost**: tabs a page opens itself are listed and become the
  active tab; console messages, responses, dialogs and downloads are recorded
  from the moment a context opens.
- **A screenshot arrives as a picture**, an image content block.
- **Boundary**: nothing inside the browser needs a permission. Screenshots are
  written inside the allowed roots and `/tmp`, files are uploaded from the
  working directory and `/tmp`; a person on the host widens that for a limited
  time with a grant.
- **Server** over stdio or streamable HTTP with the MCP SDK, protocol revision
  2026-07-28, OAuth for HTTP.

## Installation

Python 3.12 or later.

```bash
pip install mcp-playwright-tools            # the library and pw-browse
pip install "mcp-playwright-tools[server]"  # and the MCP server
playwright install chromium                 # the browser Playwright brings along
```

A Chrome already installed on the machine works as well: pass
`--channel chrome` instead of installing a browser.

## Quick start

A client that starts the server itself, over stdio:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "mcp-playwright-tools",
      "args": ["--channel", "chrome"]
    }
  }
}
```

Over HTTP, with OAuth:

```bash
MCP_OAUTH_ENABLED=true \
MCP_OAUTH_SERVER_URL=https://auth.example.org/ \
MCP_PUBLIC_URL=https://mcp.example.org/ \
mcp-playwright-tools --transport streamable-http --host 0.0.0.0 --port 12206 \
    --path /playwright --channel chrome
```

As a library:

```python
import asyncio
from pathlib import Path

from mcp_playwright_tools import Workspace, navigate, read


async def main():
    space = Workspace(working_dir=Path.cwd())
    here = space.browsing()  # the context named "default"
    print(await navigate.open_url(here, "example.org"))
    print(await read.read(here, "h1"))
    await space.pool.close_all()


asyncio.run(main())
```

From the shell, one run with a fixed order: open, fill, click, wait, show:

```bash
pw-browse example.org --text h1
pw-browse example.org --click "Learn more" --by text --url
pw-browse example.org --shot page.png
```

## Tools

| Tool | What it does |
|---|---|
| `open_url` | Open a page and wait until its document has loaded |
| `go` | Back, forward or reload |
| `where_am_i` | Address, title, tab, frame, the frames of the page, viewport |
| `tabs` | List, open, switch or close tabs, those a page opened included |
| `use_frame` | Act inside a frame, also one inside a frame, or in the page again |
| `viewport` | Report or set the size of the page area |
| `find` | Count and list the elements that match |
| `describe` | Tag, text, attributes and state of one element |
| `what_can_i_do` | Everything visible on the page that can be acted on |
| `outline` | The accessibility tree |
| `click` | Click an element |
| `act_on` | Double-click, right-click, hover, focus, check, uncheck, clear, scroll to |
| `fill` | Put text into a field, at once or key by key |
| `press_key` | Press a key on an element or on the page |
| `choose` | Choose an option in a dropdown |
| `drag` | Drag one element onto another |
| `scroll` | Scroll down, up, to the top or to the bottom |
| `attach_files` | Put files from the machine into a file input |
| `run_javascript` | Run JavaScript in the page |
| `read` | Text, the text of every match, markup, an attribute, the links |
| `screenshot` | A picture of the page or of one element, a PNG file, or a PDF |
| `wait_until` | Wait for an element, an address, a load state or a response |
| `storage` | Get, set or clear cookies and the local storage |
| `intercept` | Mock, block or release requests of the page |
| `contexts` | The browser and its contexts; open one as a device or from a saved state, save one, close one or all |
| `logs` | Console messages and page errors, responses and failed requests, dialogs |
| `dialogs` | Accept or dismiss alerts, confirms and prompts, with an answer for prompts |
| `downloads` | List what was downloaded, save a download |

A value that is not allowed is refused with the allowed ones named.

## Boundary and grants

Everything the tools do inside the browser is free, `run_javascript` included.
Three things reach the machine the browser runs on:

| Access | Tools | Without a grant (`guarded`) |
|---|---|---|
| reading | `open_url` with a `file:` address, `contexts` opening a state file | anywhere |
| writing | `screenshot` and `downloads` with `save_to`, `contexts` saving a state file | inside the allowed roots and `/tmp` |
| uploading | `attach_files` | from the working directory and `/tmp` |

`strict` confines reading to the roots as well, `open` lifts every limit. A
refusal names the grant that lifts it, to be run by a person on the host:

```bash
scripts/grant.sh set --root ~/Downloads --for 30m
scripts/grant.sh show
scripts/grant.sh reset
```

Details in
[doc/boundary.md](https://github.com/cuber-it/mcp-playwright-tools/blob/master/doc/boundary.md).

## Server options

| Option | Default | Meaning |
|---|---|---|
| `--transport` | `stdio` | `stdio` or `streamable-http` |
| `--host` | `MCP_HOST`, else `127.0.0.1` | address to bind (HTTP) |
| `--port` | `MCP_PORT`, else `8000` | port to bind (HTTP) |
| `--path` | `/mcp` | path the endpoint answers on (HTTP) |
| `--working-dir` | current directory | where relative paths start and files are uploaded from |
| `--allowed-root` | home directory | where files may be written besides `/tmp`; repeatable |
| `--state-dir` | `~/.mcp-playwright-tools` | where the grant is kept; empty for no grants |
| `--mode` | `guarded` | `open`, `guarded` or `strict` |
| `--browser` | `chromium` | `chromium`, `firefox` or `webkit` |
| `--channel` | none | an installed browser such as `chrome` |
| `--headed` | off | show the browser window |
| `--timeout` | `30` | seconds a single action may take |
| `--idle` | `900` | seconds a context may go unused before it is closed; `0` keeps them |

Authentication over HTTP is configured with `MCP_OAUTH_ENABLED`,
`MCP_OAUTH_SERVER_URL`, `MCP_PUBLIC_URL` and `MCP_AUTH_METHOD`; the server
refuses to listen beyond this machine without it.

## Development

Setup, checks, release steps and the rules the code keeps:
[doc/development.md](https://github.com/cuber-it/mcp-playwright-tools/blob/master/doc/development.md).
Changes are listed in
[CHANGES.md](https://github.com/cuber-it/mcp-playwright-tools/blob/master/CHANGES.md).

## License

MIT, see
[LICENSE](https://github.com/cuber-it/mcp-playwright-tools/blob/master/LICENSE).
