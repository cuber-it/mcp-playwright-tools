# Changes

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
