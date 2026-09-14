"""Driving a browser from a shell, in one run.

    pw-browse example.org --text h1
    pw-browse example.org --click "Learn more" --by text --url
    pw-browse example.org --shot page.png

The steps run in a fixed order: open, fill, click, wait, then whatever was
asked to be shown, in the order one works by hand. The browser lives in this
process and goes with it; a person at the shell is not confined to any roots.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from mcp_playwright_tools import act, navigate, read
from mcp_playwright_tools.errors import ToolError
from mcp_playwright_tools.pool import BROWSERS, DEFAULT_TIMEOUT, BrowserPool, Settings
from mcp_playwright_tools.workspace import Workspace

FAILED = 1


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        prog="pw-browse",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="the page to open; without a scheme, https")
    parser.add_argument("--context", default="cli", help="name of the context")
    parser.add_argument("--browser", choices=BROWSERS, default="chromium")
    parser.add_argument(
        "--channel", default="", help="an installed browser to use, such as chrome"
    )
    parser.add_argument("--headed", action="store_true", help="show the browser")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="seconds one step may take (default: %(default)s)",
    )
    parser.add_argument(
        "--fill",
        action="append",
        default=[],
        metavar="LABEL:VALUE",
        help="fill a field found by its form label; may be repeated",
    )
    parser.add_argument("--click", metavar="TARGET", help="click one element")
    parser.add_argument("--by", default="css", help="how --click is meant")
    parser.add_argument(
        "--wait", metavar="WHAT:VALUE", help="visible, hidden, url, load or response"
    )
    parser.add_argument("--title", action="store_true", help="print the page title")
    # Its own dest: the flag would otherwise overwrite the address to open.
    parser.add_argument(
        "--url", dest="show_url", action="store_true", help="print the address reached"
    )
    parser.add_argument("--links", action="store_true", help="print the links")
    parser.add_argument(
        "--text", nargs="?", const="body", metavar="TARGET", help="print visible text"
    )
    parser.add_argument("--shot", metavar="PATH", help="write a screenshot there")
    return parser.parse_args(argv)


def split(pair: str, option: str) -> tuple[str, str]:
    """Split ``left:right`` at the first colon, so the right half may hold colons.

    Raises:
        ToolError: There is no colon in it.
    """
    left, found, right = pair.partition(":")
    if not found:
        raise ToolError(f"{option} wants LEFT:RIGHT, got {pair!r}")
    return left, right


async def carry_out(args: argparse.Namespace, space: Workspace) -> list[str]:
    """Carry out what was asked and return the lines to print.

    Raises:
        ToolError: A step could not be carried out.
    """
    here = space.browsing(args.context)
    await navigate.open_url(here, args.url)
    for pair in args.fill:
        label, value = split(pair, "--fill")
        await act.fill(here, label, value)
    if args.click:
        await act.click(here, args.click, args.by)
    if args.wait:
        what, value = split(args.wait, "--wait")
        await read.wait_until(here, what, value, seconds=args.timeout)

    said = []
    if args.title:
        said.append((await navigate.where_am_i(here))["title"])
    if args.show_url:
        said.append((await navigate.where_am_i(here))["url"])
    if args.text:
        said.append(await read.read(here, args.text))
    if args.links:
        said.append(await read.read(here, what="links"))
    if args.shot:
        said.append(str(await read.screenshot(here, save_to=args.shot)))
    return said


async def once(args: argparse.Namespace) -> list[str]:
    """Start a browser, do the run, and close it again whatever happened.

    Raises:
        ToolError: The settings are unusable, or a step could not be carried out.
    """
    settings = Settings(
        browser=args.browser,
        channel=args.channel,
        headless=not args.headed,
        timeout=args.timeout,
        idle=0,
    )
    space = Workspace(working_dir=Path.cwd(), pool=BrowserPool(settings))
    try:
        return await carry_out(args, space)
    finally:
        await space.pool.close_all()


def main(argv: list[str] | None = None) -> int:
    """Drive a browser once and print what was asked for.

    Returns:
        0 when every step worked, 1 when one did not.
    """
    args = parse(argv)
    try:
        lines = asyncio.run(once(args))
    except ToolError as err:
        print(f"pw-browse: {err}", file=sys.stderr)
        return FAILED
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
