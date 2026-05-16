"""HTML cleaning and small formatting helpers for the 4chan CLI reader."""

import datetime
import html
import re


def clean_comment(raw: str | None) -> str:
    if not raw:
        return ""

    text = raw
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("<wbr>", "")

    text = re.sub(r'<span class="quote">(.*?)</span>', r"\1", text, flags=re.DOTALL)
    text = re.sub(r'<a[^>]*class="quotelink"[^>]*>(.*?)</a>', r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<a[^>]*>(>>>.*?)</a>", r"\1", text, flags=re.DOTALL)

    text = re.sub(r"<s>(.*?)</s>", r"[spoiler]\1[/spoiler]", text, flags=re.DOTALL)

    for tag in ("b", "i", "u", "strong", "em"):
        text = re.sub(fr"<{tag}>(.*?)</{tag}>", r"\1", text, flags=re.DOTALL)
    text = re.sub(r'<pre[^>]*>(.*?)</pre>', r"\1", text, flags=re.DOTALL)

    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    return text.strip()


def timestamp(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def truncate(text: str, n: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def image_url(board: str, post: dict) -> str | None:
    tim = post.get("tim")
    ext = post.get("ext")
    if not tim or not ext:
        return None
    return f"https://i.4cdn.org/{board}/{tim}{ext}"
