#!/usr/bin/env python3
"""
4chan CLI Reader — browse boards, catalogs, and threads from the terminal.
Read-only. No images. No posting.

Usage:
    python chan.py
"""

import sys
import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.columns import Columns
from rich.rule import Rule
from rich.theme import Theme
from rich import box

import api
import utils

# ── Theme ────────────────────────────────────────────────────────────────────
CUSTOM_THEME = Theme(
    {
        "board.name": "bold #81a1c1",
        "board.title": "#d8dee9",
        "board.nsfw": "bold #bf616a",
        "board.sfw": "bold #a3be8c",
        "thread.no": "bold #88c0d0",
        "thread.subject": "bold #ebcb8b",
        "thread.name": "bold #a3be8c",
        "thread.date": "dim #4c566a",
        "thread.stats": "#5e81ac",
        "greentext": "#a3be8c",
        "quotelink": "#88c0d0 underline",
        "spoiler": "on #3b4252",
        "post.op": "bold #d08770",
        "post.id": "bold #88c0d0",
        "info": "italic #616e88",
        "prompt": "bold #81a1c1",
        "error": "bold #bf616a",
        "header": "bold #eceff4",
    }
)

console = Console(theme=CUSTOM_THEME)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _timestamp_to_str(ts: int) -> str:
    """Unix timestamp → readable date string."""
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _truncate(text: str, length: int = 120) -> str:
    """Truncate text to *length* characters, adding ellipsis if needed."""
    text = text.replace("\n", " ")
    if len(text) <= length:
        return text
    return text[: length - 1] + "…"


def _format_comment(raw_comment: str) -> Text:
    """Convert raw HTML comment to a Rich Text with greentext styling."""
    plain = utils.clean_comment(raw_comment)
    rich_text = Text()
    for line in plain.split("\n"):
        if line.startswith(">") and not line.startswith(">>"):
            rich_text.append(line + "\n", style="greentext")
        elif line.startswith(">>"):
            rich_text.append(line + "\n", style="quotelink")
        else:
            rich_text.append(line + "\n")
    # strip trailing newline
    if rich_text.plain.endswith("\n"):
        rich_text.right_crop(1)
    return rich_text


def _print_header():
    """Print the application header."""
    header = Text()
    header.append("  ╔═══════════════════════════════════════╗\n", style="bold #5e81ac")
    header.append("  ║", style="bold #5e81ac")
    header.append("   4chan CLI Reader", style="bold #88c0d0")
    header.append("                    ", style="bold #5e81ac")
    header.append("║\n", style="bold #5e81ac")
    header.append("  ║", style="bold #5e81ac")
    header.append("   Read-only · No images · No posting", style="dim #4c566a")
    header.append("  ║\n", style="bold #5e81ac")
    header.append("  ╚═══════════════════════════════════════╝", style="bold #5e81ac")
    console.print(header)
    console.print()


# ── Screens ──────────────────────────────────────────────────────────────────


def show_boards():
    """Display all boards grouped by category and let user pick one."""
    console.clear()
    _print_header()

    console.print("  [info]Loading boards…[/info]")
    try:
        boards = api.get_boards()
    except Exception as e:
        console.print(f"  [error]Failed to load boards: {e}[/error]")
        return

    sfw = [b for b in boards if b.get("ws_board") == 1]
    nsfw = [b for b in boards if b.get("ws_board") == 0]

    console.clear()
    _print_header()

    # ── SFW boards ──
    console.print(Rule("[board.sfw]  Safe-For-Work Boards  [/board.sfw]", style="#a3be8c"))
    console.print()

    sfw_items = []
    for b in sfw:
        txt = Text()
        txt.append(f"/{b['board']}/", style="board.name")
        txt.append(f" {b['title']}", style="board.title")
        sfw_items.append(txt)

    console.print(Columns(sfw_items, column_first=True, padding=(0, 3), equal=True, width=32))
    console.print()

    # ── NSFW boards ──
    console.print(Rule("[board.nsfw]  NSFW Boards  [/board.nsfw]", style="#bf616a"))
    console.print()

    nsfw_items = []
    for b in nsfw:
        txt = Text()
        txt.append(f"/{b['board']}/", style="board.name")
        txt.append(f" {b['title']}", style="board.title")
        nsfw_items.append(txt)

    console.print(Columns(nsfw_items, column_first=True, padding=(0, 3), equal=True, width=32))
    console.print()

    # ── Prompt ──
    console.print(Rule(style="dim"))
    board_name = Prompt.ask(
        "  [prompt]Enter board name (e.g. g, a, pol) or 'q' to quit[/prompt]"
    )
    if board_name.lower() in ("q", "quit", "exit"):
        return
    board_name = board_name.strip().strip("/")

    valid = {b["board"] for b in boards}
    if board_name not in valid:
        console.print(f"  [error]Board /{board_name}/ not found.[/error]")
        Prompt.ask("  [info]Press Enter to continue[/info]")
        show_boards()
        return

    show_catalog(board_name)


def show_catalog(board: str, page_idx: int = 0):
    """Display the catalog for a board and let user pick a thread."""
    console.clear()
    _print_header()

    console.print(f"  [info]Loading /{board}/ catalog…[/info]")
    try:
        catalog = api.get_catalog(board)
    except Exception as e:
        console.print(f"  [error]Failed to load catalog: {e}[/error]")
        Prompt.ask("  [info]Press Enter to go back[/info]")
        show_boards()
        return

    # Flatten all threads across pages, keeping page info
    all_threads = []
    for page in catalog:
        for thread in page.get("threads", []):
            thread["_page"] = page.get("page", 0)
            all_threads.append(thread)

    if not all_threads:
        console.print(f"  [error]No threads found on /{board}/.[/error]")
        Prompt.ask("  [info]Press Enter to go back[/info]")
        show_boards()
        return

    # Paginate display: 20 threads per screen
    page_size = 20
    total_pages = (len(all_threads) + page_size - 1) // page_size
    page_idx = max(0, min(page_idx, total_pages - 1))

    start = page_idx * page_size
    end = min(start + page_size, len(all_threads))
    page_threads = all_threads[start:end]

    console.clear()
    _print_header()

    title_text = Text()
    title_text.append(f"  /{board}/ ", style="board.name")
    title_text.append(f"— Catalog", style="header")
    title_text.append(f"  (page {page_idx + 1}/{total_pages})", style="info")
    console.print(title_text)
    console.print()

    # Thread table
    table = Table(
        box=box.ROUNDED,
        border_style="#3b4252",
        header_style="bold #81a1c1",
        row_styles=["", "on #2e3440"],
        pad_edge=True,
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("No.", style="thread.no", width=12)
    table.add_column("Subject / Comment", style="board.title", ratio=1)
    table.add_column("R", style="thread.stats", width=5, justify="right")
    table.add_column("Date", style="thread.date", width=20)

    for i, t in enumerate(page_threads, start=start + 1):
        subject = t.get("sub", "")
        comment = utils.clean_comment(t.get("com", ""))
        display = subject if subject else _truncate(comment, 80)
        if not display:
            display = "(no text)"

        replies = str(t.get("replies", 0))
        date = _timestamp_to_str(t.get("time", 0))

        table.add_row(str(i), str(t["no"]), _truncate(display, 80), replies, date)

    console.print(table)
    console.print()

    # Navigation
    nav_parts = []
    if page_idx > 0:
        nav_parts.append("[prompt]p[/prompt]=prev page")
    if page_idx < total_pages - 1:
        nav_parts.append("[prompt]n[/prompt]=next page")
    nav_parts.append("[prompt]#[/prompt]=open thread by row number")
    nav_parts.append("[prompt]t <id>[/prompt]=open by thread ID")
    nav_parts.append("[prompt]b[/prompt]=back to boards")
    nav_parts.append("[prompt]q[/prompt]=quit")
    console.print("  " + "  │  ".join(nav_parts), style="info")
    console.print()

    choice = Prompt.ask("  [prompt]>[/prompt]").strip().lower()

    if choice == "q":
        return
    elif choice == "b":
        show_boards()
        return
    elif choice == "n" and page_idx < total_pages - 1:
        show_catalog(board, page_idx + 1)
        return
    elif choice == "p" and page_idx > 0:
        show_catalog(board, page_idx - 1)
        return
    elif choice.startswith("t "):
        try:
            thread_no = int(choice.split()[1])
            show_thread(board, thread_no)
            show_catalog(board, page_idx)
            return
        except (ValueError, IndexError):
            console.print("  [error]Invalid thread ID.[/error]")
            Prompt.ask("  [info]Press Enter[/info]")
            show_catalog(board, page_idx)
            return
    else:
        try:
            row = int(choice)
            idx = row - 1
            if 0 <= idx < len(all_threads):
                show_thread(board, all_threads[idx]["no"])
                show_catalog(board, page_idx)
                return
            else:
                console.print("  [error]Row number out of range.[/error]")
                Prompt.ask("  [info]Press Enter[/info]")
                show_catalog(board, page_idx)
                return
        except ValueError:
            console.print("  [error]Unrecognized command.[/error]")
            Prompt.ask("  [info]Press Enter[/info]")
            show_catalog(board, page_idx)
            return


def show_thread(board: str, thread_no: int):
    """Display all posts in a thread with pagination."""
    console.clear()
    _print_header()

    console.print(f"  [info]Loading thread /{board}/{thread_no}…[/info]")
    try:
        data = api.get_thread(board, thread_no)
    except Exception as e:
        console.print(f"  [error]Failed to load thread: {e}[/error]")
        Prompt.ask("  [info]Press Enter to go back[/info]")
        return

    posts = data.get("posts", [])
    if not posts:
        console.print("  [error]Thread is empty.[/error]")
        Prompt.ask("  [info]Press Enter to go back[/info]")
        return

    # Display with paging
    page_size = 10
    total_pages = (len(posts) + page_size - 1) // page_size
    current_page = 0

    while True:
        console.clear()
        _print_header()

        op = posts[0]
        op_subject = op.get("sub", "")
        title_text = Text()
        title_text.append(f"  /{board}/ ", style="board.name")
        title_text.append(f"Thread No.{thread_no}", style="thread.no")
        if op_subject:
            title_text.append(f"  —  {op_subject}", style="thread.subject")
        title_text.append(
            f"  ({len(posts)} posts, page {current_page + 1}/{total_pages})", style="info"
        )
        console.print(title_text)
        console.print()

        start = current_page * page_size
        end = min(start + page_size, len(posts))

        for post in posts[start:end]:
            _render_post(post, board, is_op=(post.get("resto", 0) == 0))

        console.print()
        # Navigation
        nav_parts = []
        if current_page > 0:
            nav_parts.append("[prompt]p[/prompt]=prev")
        if current_page < total_pages - 1:
            nav_parts.append("[prompt]n[/prompt]=next")
        nav_parts.append("[prompt]t[/prompt]=top")
        nav_parts.append("[prompt]e[/prompt]=end")
        nav_parts.append("[prompt]b[/prompt]=back to catalog")
        nav_parts.append("[prompt]q[/prompt]=quit")
        console.print("  " + "  │  ".join(nav_parts), style="info")
        console.print()

        choice = Prompt.ask("  [prompt]>[/prompt]").strip().lower()

        if choice == "q":
            sys.exit(0)
        elif choice == "b":
            return
        elif choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "p" and current_page > 0:
            current_page -= 1
        elif choice == "t":
            current_page = 0
        elif choice == "e":
            current_page = total_pages - 1
        else:
            pass  # stay on same page for unrecognized input


def _render_post(post: dict, board: str, is_op: bool = False):
    """Render a single post as a Rich Panel."""
    post_no = post.get("no", 0)
    name = post.get("name", "Anonymous")
    trip = post.get("trip", "")
    capcode = post.get("capcode", "")
    date_str = post.get("now", "")
    comment = post.get("com", "")
    subject = post.get("sub", "")
    country_name = post.get("country_name", "")
    poster_id = post.get("id", "")

    # Build header line
    header = Text()
    if is_op:
        header.append("OP ", style="post.op")
    header.append(f"No.{post_no}", style="post.id")
    header.append("  ")
    header.append(name, style="thread.name")
    if trip:
        header.append(f" {trip}", style="dim #b48ead")
    if capcode:
        header.append(f" ## {capcode}", style="bold #bf616a")
    if poster_id:
        header.append(f"  ID:{poster_id}", style="dim #d08770")
    if country_name:
        header.append(f"  [{country_name}]", style="dim #ebcb8b")
    header.append(f"  {date_str}", style="thread.date")

    # File info (just metadata, no actual image)
    file_info = ""
    if post.get("filename"):
        fname = post["filename"] + post.get("ext", "")
        fsize_kb = post.get("fsize", 0) // 1024
        dims = f"{post.get('w', '?')}x{post.get('h', '?')}"
        file_info = f"📎 {fname} ({fsize_kb}KB, {dims})"

    # Build body
    body = Text()
    if subject and not is_op:
        body.append(subject + "\n", style="thread.subject")
    if file_info:
        body.append(file_info + "\n", style="dim #5e81ac")
        body.append("\n")
    if comment:
        body.append_text(_format_comment(comment))

    border_style = "#5e81ac" if is_op else "#3b4252"
    panel_box = box.HEAVY if is_op else box.ROUNDED

    console.print(
        Panel(
            body,
            title=header,
            title_align="left",
            border_style=border_style,
            box=panel_box,
            padding=(0, 2),
            width=min(console.width - 4, 110),
        )
    )


# ── Entry ────────────────────────────────────────────────────────────────────


def main():
    try:
        show_boards()
    except KeyboardInterrupt:
        console.print("\n  [info]Goodbye.[/info]")
        sys.exit(0)


if __name__ == "__main__":
    main()
