# Boundary and grants

Everything the tools do inside the browser needs no permission, `run_javascript`
included. The boundary only decides how far the tools reach on the machine the
browser runs on, and it is checked for every path a tool resolves.

## What is checked

| Access | Tools | `guarded` (default) | `strict` | `open` |
|---|---|---|---|---|
| reading | `open_url` with a `file:` address | anywhere | inside the roots | anywhere |
| writing | `screenshot` with `save_to` | inside the roots | inside the roots | anywhere |
| uploading | `attach_files` | from the upload directories | from the upload directories | anywhere |

- **The roots** are the home directory unless `--allowed-root` names others.
- **The upload directory** is the working directory. An upload hands a file to
  a web page, which can send it anywhere, so the home directory with `~/.ssh`
  and `~/.config` stays out of reach for it.
- **`/tmp` is always within reach**, for every access and in every mode.
- A `javascript:` address is refused by `open_url`; it runs a script, which is
  what `run_javascript` is for.

Empty roots or empty upload directories mean no limit for what they confine.
That is how the library runs when a `Workspace` is built without a boundary.

## Refusals

A refused path raises `OutsideBoundaryError`, and the message ends with the
grant that would lift it:

```text
outside the directories uploads may come from: /home/you/.config/token.txt; a
person on the host can allow it with: /path/to/mcp-playwright-tools/scripts/grant.sh
--state-dir /home/you/.mcp-playwright-tools set --root /home/you/.config --for 1h
```

The suggested root is the refused path if it is a directory, otherwise the
directory it lies in. The suggested duration is always one hour.

## Grants

A grant widens or narrows the boundary of a running server for a limited time.
It takes effect at the next tool call and lapses on its own; the server does not
restart.

```bash
scripts/grant.sh set --root ~/Downloads --for 30m  # uploads and screenshots reach it
scripts/grant.sh set --mode open --for 15m         # no limit at all
scripts/grant.sh set --mode strict --for 1d        # reading confined as well
scripts/grant.sh show
scripts/grant.sh reset
```

| Option | Effect |
|---|---|
| `--for` | required; a number with `s`, `m`, `h` or `d`, for instance `30m` |
| `--root PATH` | adds a root and an upload directory; repeatable |
| `--mode` | replaces the configured mode |
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
  "roots": ["/home/you/Downloads"]
}
```

`until` is a Unix time. `mode` may be `null`, meaning unchanged. `roots` must
be absolute.

- The file is written to a temporary name and renamed, so the server sees the
  old grant or the new one, never half of either.
- The tools cannot write the file: a screenshot is refused for the file and
  for its directory.
- A grant file that cannot be read or does not hold a valid grant makes every
  check fail with `GrantError` until it is fixed or removed with
  `scripts/grant.sh reset`.
- Without a state directory there are no grants, and refusals say so.
