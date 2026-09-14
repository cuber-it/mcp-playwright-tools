# Changes

## 8.0.2 (c783ad1)

- `what_can_i_do`, `read` with `links` and `read` with `html` and no target work
  in the frame chosen with `use_frame`, like the other tools, instead of the
  page around it
- `what_can_i_do` lists controls fixed on the screen, such as cookie banners;
  it asks for rendered boxes instead of `offsetParent`
- More than 100 cookies say how many were left out; the local storage is cut
  like other long output and says so

## 8.0.1 (3df41d7)

- When the browser went away, closing a context, closing all of them and the
  idle sweep forget its contexts instead of failing to close them

## 09b170b

- Grants only for what is dangerous on the machine: `run_javascript` runs
  without one, `--exec` and the grant's `execute` are gone
- Uploads come from the working directory and `/tmp`; anything else, `~/.ssh`
  or `~/.config` included, needs a grant, and the refusal names it
- `/tmp` is always within reach for reading, writing and uploading, in every
  mode; screenshots are written there or inside the allowed roots
- A grant's `--root` widens both the roots and the upload directories
- The tests keep their temporary directories in `.pytest-tmp` instead of
  `/tmp`, so the refusals they expect are still refusals

## 91b4e64

- Version 8.0.0: browser tools as a library without the MCP SDK, the command
  `pw-browse`, and an MCP server over stdio or streamable HTTP with OAuth token
  introspection
- Twenty-four tools: pages, history, tabs, frames, finding, describing,
  clicking, filling, keys, dropdowns, dragging, scrolling, files, scripts,
  reading, screenshots, waiting, cookies, local storage, intercepted requests
  and contexts
- The way of pointing at an element is a parameter, `by`; a value that is not
  allowed is refused with the allowed ones named
- Each context name is a browser context of its own in one browser, closed
  after a while unused; the browser stops with the last one and starts again
  when it went away
- A screenshot arrives as an image content block
- Boundary and grants as in mcp-shell-tools: files handed to a page are read
  anywhere unless strict, screenshots are written inside the allowed roots,
  `run_javascript` is off until `--exec` or a grant; `javascript:` addresses
  are refused
- `--channel` starts an installed browser such as Chrome

## ebdef57

- Complete restart with a new history, rebuilt on the scaffold of
  mcp-shell-tools and mcp-image-tools for the MCP SDK 2.x (protocol revision
  2026-07-28).
