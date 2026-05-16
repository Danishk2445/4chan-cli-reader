#!/usr/bin/env python3
"""4chan CLI reader — browse boards, catalogs, and threads in your terminal.

Read-only. No posting. Images are surfaced as URLs.
"""

import sys

import requests
from rich import box
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

import api
import utils


THEME = Theme(
    {
        "board.name": "bold #81a1c1",
        "board.title": "#d8dee9",
        "board.sfw": "bold #a3be8c",
        "board.nsfw": "bold #bf616a",
        "thread.no": "bold #88c0d0",
        "thread.subject": "bold #ebcb8b",
        "thread.name": "bold #a3be8c",
        "thread.stats": "#5e81ac",
        "thread.date": "dim #4c566a",
        "greentext": "#a3be8c",
        "quotelink": "#88c0d0 underline",
        "spoiler": "on #3b4252",
        "post.op": "bold #d08770",
        "post.id": "bold #88c0d0",
        "image.url": "#b48ead underline",
        "header": "bold #eceff4",
        "info": "italic #616e88",
        "prompt": "bold #81a1c1",
        "error": "bold #bf616a",
    }
)

console = Console(theme=THEME)


# ── small renderers ─────────────────────────────────────────────────────────


def _header():
    title = Text("  4chan CLI Reader  ", style="header")
    sub = Text("read-only · no posting", style="info")
    console.print(Panel(Group(title, sub), border_style="#5e81ac", box=box.DOUBLE, padding=(0, 2)))


def _format_comment(plain: str) -> Text:
    out = Text()
    for line in plain.split("\n"):
        if line.startswith(">>"):
            line_style: str | None = "quotelink"
        elif line.startswith(">"):
            line_style = "greentext"
        else:
            line_style = None

        i = 0
        while i < len(line):
            start = line.find("[spoiler]", i)
            if start == -1:
                out.append(line[i:], style=line_style)
                break
            end = line.find("[/spoiler]", start)
            if end == -1:
                out.append(line[i:], style=line_style)
                break
            out.append(line[i:start], style=line_style)
            out.append(line[start + len("[spoiler]") : end], style="spoiler")
            i = end + len("[/spoiler]")
        out.append("\n")

    if out.plain.endswith("\n"):
        out.right_crop(1)
    return out


def _post_panel(board: str, post: dict, is_op: bool) -> Panel:
    head = Text()
    head.append(f"No.{post['no']}", style="post.op" if is_op else "post.id")
    name = post.get("name", "Anonymous") or "Anonymous"
    head.append(f"  {name}", style="thread.name")
    if "now" in post:
        head.append(f"  {post['now']}", style="thread.date")
    elif "time" in post:
        head.append(f"  {utils.timestamp(post['time'])}", style="thread.date")

    parts: list = [head]

    if is_op:
        subject = post.get("sub")
        if subject:
            parts.append(Text(subject, style="thread.subject"))

    img = utils.image_url(board, post)
    if img:
        url_line = Text()
        filename = post.get("filename", "") + post.get("ext", "")
        if filename:
            url_line.append(f"📎 {filename}  ", style="info")
        url_line.append(img, style="image.url")
        parts.append(url_line)

    body = utils.clean_comment(post.get("com"))
    if body:
        parts.append(_format_comment(body))

    return Panel(
        Group(*parts),
        border_style="#d08770" if is_op else "#3b4252",
        box=box.ROUNDED,
        padding=(0, 1),
        title="[post.op]OP[/post.op]" if is_op else None,
        title_align="left",
    )


def _ask(prompt_text: str) -> str:
    try:
        return Prompt.ask(f"  [prompt]{prompt_text}[/prompt]").strip()
    except (EOFError, KeyboardInterrupt):
        return "q"


def _api_call(label: str, fn, *args):
    """Run an api call with a status spinner and standard error handling.

    Returns the result, or None on failure (with the error already printed).
    """
    try:
        with console.status(f"[info]{label}…[/info]", spinner="dots"):
            return fn(*args)
    except requests.HTTPError as e:
        console.print(f"  [error]HTTP {e.response.status_code}: {e.response.reason}[/error]")
    except requests.RequestException as e:
        console.print(f"  [error]Network error: {e}[/error]")
    return None


# ── screens ─────────────────────────────────────────────────────────────────


def show_boards():
    console.clear()
    _header()

    boards = _api_call("Loading boards", api.get_boards)
    if boards is None:
        _ask("Press Enter to retry, or q to quit")
        return ("boards", None)

    sfw = [b for b in boards if b.get("ws_board") == 1]
    nsfw = [b for b in boards if b.get("ws_board") == 0]

    def render_section(items: list[dict], rule_label: str, rule_style: str):
        console.print(Rule(f"[{rule_style}]  {rule_label}  [/{rule_style}]", style=rule_style.split()[-1]))
        console.print()
        cells = []
        for b in items:
            t = Text()
            t.append(f"/{b['board']}/", style="board.name")
            t.append(f" {b['title']}", style="board.title")
            cells.append(t)
        console.print(Columns(cells, padding=(0, 3), equal=True, expand=True, column_first=True))
        console.print()

    render_section(sfw, "Safe-For-Work boards", "board.sfw")
    render_section(nsfw, "NSFW boards", "board.nsfw")

    valid = {b["board"] for b in boards}
    while True:
        choice = _ask("board name (e.g. g) · q to quit")
        if choice.lower() in ("q", "quit", "exit"):
            return ("quit", None)
        choice = choice.strip().strip("/").lower()
        if choice in valid:
            return ("catalog", choice)
        console.print(f"  [error]board /{choice}/ not found.[/error]")


def show_catalog(board: str):
    page_idx = 0
    catalog = None
    threads: list[dict] = []

    while True:
        if catalog is None:
            console.clear()
            _header()
            catalog = _api_call(f"Loading /{board}/ catalog", api.get_catalog, board)
            if catalog is None:
                _ask("Press Enter to go back to boards")
                return ("boards", None)
            threads = [t for page in catalog for t in page.get("threads", [])]
            if not threads:
                console.print(f"  [error]/{board}/ has no threads.[/error]")
                _ask("Press Enter to go back")
                return ("boards", None)

        page_size = 20
        total_pages = (len(threads) + page_size - 1) // page_size
        page_idx = max(0, min(page_idx, total_pages - 1))
        start = page_idx * page_size
        page_threads = threads[start : start + page_size]

        console.clear()
        _header()

        title = Text()
        title.append(f"  /{board}/", style="board.name")
        title.append("  catalog  ", style="header")
        title.append(f"page {page_idx + 1}/{total_pages}", style="info")
        console.print(title)
        console.print()

        table = Table(
            box=box.ROUNDED,
            border_style="#3b4252",
            header_style="bold #81a1c1",
            row_styles=["", "on #2e3440"],
            pad_edge=False,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("No.", style="thread.no", width=11)
        table.add_column("Subject / comment", style="board.title", ratio=1, overflow="fold")
        table.add_column("R", style="thread.stats", width=5, justify="right")
        table.add_column("I", style="thread.stats", width=5, justify="right")
        table.add_column("Date", style="thread.date", width=16)

        for i, t in enumerate(page_threads, start=start + 1):
            sub = t.get("sub", "")
            com = utils.clean_comment(t.get("com", ""))
            display = sub if sub else com
            if not display:
                display = "(no text)"
            table.add_row(
                str(i),
                str(t["no"]),
                utils.truncate(display, 120),
                str(t.get("replies", 0)),
                str(t.get("images", 0)),
                utils.timestamp(t.get("time", 0)),
            )

        console.print(table)
        console.print()

        hints = []
        if page_idx > 0:
            hints.append("[prompt]p[/prompt]=prev")
        if page_idx < total_pages - 1:
            hints.append("[prompt]n[/prompt]=next")
        hints.append("[prompt]#[/prompt]=open row")
        hints.append("[prompt]t <id>[/prompt]=open by no.")
        hints.append("[prompt]b[/prompt]=boards")
        hints.append("[prompt]q[/prompt]=quit")
        console.print("  " + "  ·  ".join(hints), style="info")
        console.print()

        choice = _ask(">").lower()
        if choice in ("q", "quit", "exit"):
            return ("quit", None)
        if choice in ("b", "back"):
            return ("boards", None)
        if choice == "n" and page_idx < total_pages - 1:
            page_idx += 1
            continue
        if choice == "p" and page_idx > 0:
            page_idx -= 1
            continue
        if choice.startswith("t "):
            try:
                no = int(choice.split(maxsplit=1)[1])
            except (ValueError, IndexError):
                console.print("  [error]usage: t <thread-id>[/error]")
                _ask("Press Enter to continue")
                continue
            return ("thread", (board, no))
        if choice.isdigit():
            row = int(choice)
            if start + 1 <= row <= start + len(page_threads):
                return ("thread", (board, page_threads[row - start - 1]["no"]))
            console.print(f"  [error]row {row} is not on this page.[/error]")
            _ask("Press Enter to continue")
            continue
        console.print(f"  [error]unknown command: {choice!r}[/error]")
        _ask("Press Enter to continue")


def show_thread(board: str, thread_no: int):
    console.clear()
    _header()

    data = _api_call(f"Loading /{board}/{thread_no}", api.get_thread, board, thread_no)
    if data is None:
        _ask("Press Enter to go back")
        return ("catalog", board)

    posts = data.get("posts", [])
    if not posts:
        console.print("  [error]thread is empty.[/error]")
        _ask("Press Enter to go back")
        return ("catalog", board)

    page_size = 6
    pages = [posts[i : i + page_size] for i in range(0, len(posts), page_size)]
    page_idx = 0

    while True:
        console.clear()
        _header()

        title = Text()
        title.append(f"  /{board}/", style="board.name")
        title.append(f"  thread {thread_no}  ", style="header")
        title.append(
            f"{len(posts) - 1} repl{'y' if len(posts) == 2 else 'ies'}  ·  "
            f"page {page_idx + 1}/{len(pages)}",
            style="info",
        )
        console.print(title)
        console.print()

        for post in pages[page_idx]:
            is_op = post is posts[0]
            console.print(_post_panel(board, post, is_op))
            console.print()

        hints = []
        if page_idx > 0:
            hints.append("[prompt]p[/prompt]=prev")
        if page_idx < len(pages) - 1:
            hints.append("[prompt]n[/prompt]=next")
        hints.append("[prompt]b[/prompt]=catalog")
        hints.append("[prompt]q[/prompt]=quit")
        console.print("  " + "  ·  ".join(hints), style="info")
        console.print()

        choice = _ask(">").lower()
        if choice in ("q", "quit", "exit"):
            return ("quit", None)
        if choice in ("b", "back"):
            return ("catalog", board)
        if choice == "n" and page_idx < len(pages) - 1:
            page_idx += 1
            continue
        if choice == "p" and page_idx > 0:
            page_idx -= 1
            continue
        if choice == "":
            if page_idx < len(pages) - 1:
                page_idx += 1
            continue
        console.print(f"  [error]unknown command: {choice!r}[/error]")
        _ask("Press Enter to continue")


# ── main loop ───────────────────────────────────────────────────────────────


def main():
    state: tuple = ("boards", None)
    try:
        while state[0] != "quit":
            kind, arg = state
            if kind == "boards":
                state = show_boards()
            elif kind == "catalog":
                state = show_catalog(arg)
            elif kind == "thread":
                board, no = arg
                state = show_thread(board, no)
            else:
                break
    except KeyboardInterrupt:
        pass
    console.print("\n[info]bye.[/info]")


if __name__ == "__main__":
    sys.exit(main())
