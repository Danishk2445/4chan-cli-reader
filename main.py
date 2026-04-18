#!/usr/bin/env python3
"""
4chan CLI Browser — read-only, no images.
Uses the public 4chan JSON API: https://github.com/4chan/4chan-API
"""

import sys
import json
import html
import textwrap
import urllib.request
import urllib.error
import shutil

# ─── helpers ────────────────────────────────────────────────────────────────

BASE = "https://a.4cdn.org"
TERM_WIDTH = shutil.get_terminal_size((100, 40)).columns


def fetch(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "4chan-cli/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def clean(text: str | None) -> str:
    """Strip HTML tags and decode entities."""
    if not text:
        return ""
    import re
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def rule(char="─"):
    print(char * TERM_WIDTH)


def paginate(lines: list[str], page_size: int = 30):
    """Simple pager: press Enter to continue, q to quit."""
    for i, line in enumerate(lines, 1):
        print(line)
        if i % page_size == 0:
            try:
                key = input("\n  ── more (Enter) / q+Enter to stop ── ").strip().lower()
            except EOFError:
                break
            if key == "q":
                break
            # clear the "more" prompt line
            print()


# ─── screens ────────────────────────────────────────────────────────────────

def show_boards():
    print("\nFetching board list …")
    data = fetch(f"{BASE}/boards.json")
    boards = data["boards"]

    lines = []
    lines.append(f"\n{'BOARD':<10} {'TITLE':<35} DESCRIPTION")
    lines.append("─" * TERM_WIDTH)
    for b in boards:
        board  = f"/{b['board']}/"
        title  = b.get("title", "")[:34]
        desc   = clean(b.get("meta_description", ""))
        first  = desc.split("\n")[0][:TERM_WIDTH - 47]
        lines.append(f"{board:<10} {title:<35} {first}")

    paginate(lines)
    return boards


def show_catalog(board: str):
    print(f"\nFetching catalog for /{board}/ …")
    try:
        pages = fetch(f"{BASE}/{board}/catalog.json")
    except urllib.error.HTTPError as e:
        print(f"  Error {e.code}: board /{board}/ not found.")
        return []

    threads = []
    for page in pages:
        threads.extend(page.get("threads", []))

    lines = []
    lines.append(f"\n  /{board}/ — {len(threads)} threads\n")
    lines.append(f"  {'#':<6} {'REPLIES':<8} {'SUBJECT / COMMENT'}")
    lines.append("  " + "─" * (TERM_WIDTH - 2))

    for t in threads:
        num     = t["no"]
        replies = t.get("replies", 0)
        sub     = clean(t.get("sub", "")) or clean(t.get("com", ""))
        sub     = sub.replace("\n", " ")[:TERM_WIDTH - 20]
        lines.append(f"  {num:<6} {replies:<8} {sub}")

    paginate(lines)
    return threads


def show_thread(board: str, thread_no: int):
    print(f"\nFetching /{board}/thread/{thread_no} …")
    try:
        data = fetch(f"{BASE}/{board}/thread/{thread_no}.json")
    except urllib.error.HTTPError as e:
        print(f"  Error {e.code}: thread not found.")
        return

    posts = data.get("posts", [])
    op    = posts[0] if posts else {}

    lines = []
    # ─ OP ─
    lines.append("")
    rule_str = "═" * TERM_WIDTH
    lines.append(rule_str)
    subject = clean(op.get("sub", "")) or "(no subject)"
    lines.append(f"  /{board}/ — Thread No.{op['no']}  ·  {subject}")
    lines.append(f"  {op.get('now','')}")
    lines.append(rule_str)
    op_body = clean(op.get("com", "(no text)"))
    for ln in textwrap.wrap(op_body, width=TERM_WIDTH - 4) or [op_body]:
        lines.append("  " + ln)
    lines.append("")

    # ─ replies ─
    for post in posts[1:]:
        lines.append("  " + "─" * (TERM_WIDTH - 2))
        lines.append(f"  No.{post['no']}  {post.get('now','')}  {clean(post.get('name','Anonymous'))}")
        body = clean(post.get("com", ""))
        if body:
            for ln in body.split("\n"):
                wrapped = textwrap.wrap(ln, width=TERM_WIDTH - 6) or [""]
                for wl in wrapped:
                    lines.append("    " + wl)
        lines.append("")

    lines.append("═" * TERM_WIDTH)
    lines.append(f"  {len(posts)-1} repl{'y' if len(posts)==2 else 'ies'} — end of thread")
    lines.append("═" * TERM_WIDTH)

    paginate(lines, page_size=40)


# ─── main loop ──────────────────────────────────────────────────────────────

HELP = """
  Commands:
    boards              — list all boards
    board <name>        — browse catalog of a board  (e.g.  board g)
    thread <no>         — open a thread by number    (requires board context)
    open <board> <no>   — open a thread directly     (e.g.  open g 12345678)
    q / quit / exit     — exit
    ? / help            — show this help
"""


def main():
    print("┌─────────────────────────────────┐")
    print("│   4chan CLI Browser  (read-only) │")
    print("└─────────────────────────────────┘")
    print(HELP)

    current_board: str | None = None

    while True:
        try:
            prompt = f"[/{current_board}/] > " if current_board else "> "
            raw    = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd   = parts[0].lower()

        if cmd in ("q", "quit", "exit"):
            print("Bye.")
            break

        elif cmd in ("?", "help"):
            print(HELP)

        elif cmd == "boards":
            show_boards()

        elif cmd == "board" and len(parts) >= 2:
            board = parts[1].strip("/").lower()
            show_catalog(board)
            current_board = board

        elif cmd == "thread" and len(parts) >= 2:
            if not current_board:
                print("  No board selected. Use 'board <name>' first, or 'open <board> <no>'.")
                continue
            try:
                no = int(parts[1])
            except ValueError:
                print("  Thread number must be an integer.")
                continue
            show_thread(current_board, no)

        elif cmd == "open" and len(parts) >= 3:
            board = parts[1].strip("/").lower()
            try:
                no = int(parts[2])
            except ValueError:
                print("  Thread number must be an integer.")
                continue
            current_board = board
            show_thread(board, no)

        else:
            print(f"  Unknown command: '{raw}'.  Type ? for help.")


if __name__ == "__main__":
    main()