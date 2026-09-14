# Boundary and grants

The boundary decides how far the tools reach on the machine the browser runs
on. It is checked for every path a tool resolves: files handed to a page,
pages opened from disk and screenshots written to a file.

## Roots, mode and scripts

A boundary has three parts.

**Roots** are the directories the tools are confined to. Without roots there is
no limit. The server uses the home directory unless `--allowed-root` names
others.

**The mode** decides what the roots confine:

| Mode | Reading | Writing |
|---|---|---|
| `open` | anywhere | anywhere |
| `guarded` (default) | anywhere | inside the roots |
| `strict` | inside the roots | inside the roots |

**Scripts** are a switch of their own. `run_javascript` runs code with the
rights of the page, also in a session somebody is logged into, and no path
check can confine that. The server starts with scripts off; `--exec` switches
them on for good, a grant for a while.

## What each tool needs

| Access | Tools |
|---|---|
| reading | `attach_files`, `open_url` with a `file:` address |
| writing | `screenshot` with `save_to` |
| scripts | `run_javascript` |
| none | every other tool |

A `javascript:` address is refused by `open_url` in every mode; it runs a
script, which is what `run_javascript` is for.

## Refusals

A refused path raises `OutsideBoundaryError`, switched-off scripts
`NotPermittedError`. Both messages end with the grant that would lift them:

```text
running JavaScript is switched off; a person on the host can allow it with:
/path/to/mcp-playwright-tools/scripts/grant.sh --state-dir
/home/you/.mcp-playwright-tools set --exec --for 1h
```

The suggested root is the refused path if it is a directory, otherwise the
directory it lies in. The suggested duration is always one hour.

## Grants

A grant widens or narrows the boundary of a running server for a limited time.
It takes effect at the next tool call and lapses on its own; the server does not
restart.

```bash
scripts/grant.sh set --exec --for 30m            # scripts run
scripts/grant.sh set --root /opt/shots --for 2h  # writing reaches /opt/shots too
scripts/grant.sh set --mode open --for 15m       # no confinement at all
scripts/grant.sh set --mode strict --for 1d      # reading confined as well
scripts/grant.sh set --no-exec --for 1d          # scripts off, even with --exec
scripts/grant.sh show
scripts/grant.sh reset
```

| Option | Effect |
|---|---|
| `--for` | required; a number with `s`, `m`, `h` or `d`, for instance `30m` |
| `--root PATH` | adds a root; repeatable. Without configured roots there is no limit, and a grant adds none |
| `--mode` | replaces the configured mode |
| `--exec`, `--no-exec` | switch scripts on or off |
| `--state-dir` | state directory of the server, `~/.mcp-playwright-tools` unless given |

A grant has to change something. A new grant replaces the previous one. Lasting
changes belong in the server's own options.

`scripts/grant.sh` finds the repository from its own location, also through a
symlink, and runs `python -m mcp_playwright_tools.tools.mcp_playwright_grant`
with the interpreter of the repository's `.venv`. Installed from PyPI, without
a checkout, the same module is called with the interpreter the server runs
with, and refusals name that call instead:

```bash
/path/to/venv/bin/python -m mcp_playwright_tools.tools.mcp_playwright_grant show
```

## The grant file

The grant is `grant.json` in the state directory, readable by its owner only:

```json
{
  "until": 1789000000.0,
  "mode": "open",
  "roots": ["/opt/shots"],
  "execute": true
}
```

`until` is a Unix time. `mode` and `execute` may be `null`, meaning unchanged.
`roots` must be absolute.

- The file is written to a temporary name and renamed, so the server sees the
  old grant or the new one, never half of either.
- The tools cannot write the file: a screenshot is refused for the file and
  for its directory.
- A grant file that cannot be read or does not hold a valid grant makes every
  check fail with `GrantError` until it is fixed or removed with
  `scripts/grant.sh reset`.
- Without a state directory there are no grants, and refusals say so.
