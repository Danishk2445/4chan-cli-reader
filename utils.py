"""
Utilities for cleaning 4chan HTML comments into readable plain text.
"""

import html
import re


def clean_comment(raw: str | None) -> str:
    """Convert a 4chan HTML comment into readable plain text."""
    if not raw:
        return ""

    text = raw

    # Decode HTML entities first
    text = html.unescape(text)

    # Greentext quotes:  <span class="quote">&gt;text</span>
    text = re.sub(r'<span class="quote">(.*?)</span>', r"\1", text)

    # Post references:  <a href="..." class="quotelink">>>12345</a>
    text = re.sub(r'<a[^>]*class="quotelink"[^>]*>(.*?)</a>', r"\1", text)

    # Cross-board links
    text = re.sub(r'<a[^>]*>(>>>.*?)</a>', r"\1", text)

    # Spoiler tags
    text = re.sub(r"<s>(.*?)</s>", r"[spoiler]\1[/spoiler]", text)

    # Bold / italic
    text = re.sub(r"<b>(.*?)</b>", r"\1", text)
    text = re.sub(r"<i>(.*?)</i>", r"\1", text)
    text = re.sub(r"<u>(.*?)</u>", r"\1", text)
    text = re.sub(r"<strong>(.*?)</strong>", r"\1", text)
    text = re.sub(r"<em>(.*?)</em>", r"\1", text)

    # Code tags
    text = re.sub(r'<pre class="prettyprint">(.*?)</pre>', r"\1", text, flags=re.DOTALL)

    # Line breaks
    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    text = text.replace("<br />", "\n")

    # Word break hints
    text = text.replace("<wbr>", "")

    # Strip any remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Final entity cleanup
    text = html.unescape(text)

    return text.strip()
