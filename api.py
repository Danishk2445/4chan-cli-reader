"""
4chan read-only API client.
Wraps the JSON API at https://a.4cdn.org
"""

import time
import requests

BASE = "https://a.4cdn.org"
_last_request_time = 0.0


def _get(url: str) -> dict | list:
    """Rate-limited GET that honours the 1-request-per-second rule."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    resp = requests.get(url, timeout=15)
    _last_request_time = time.time()
    resp.raise_for_status()
    return resp.json()


def get_boards() -> list[dict]:
    """Return list of board dicts from boards.json."""
    data = _get(f"{BASE}/boards.json")
    return data["boards"]


def get_catalog(board: str) -> list[dict]:
    """Return catalog pages for a board (list of {page, threads})."""
    return _get(f"{BASE}/{board}/catalog.json")


def get_thread(board: str, thread_no: int) -> dict:
    """Return full thread JSON (contains 'posts' list)."""
    return _get(f"{BASE}/{board}/thread/{thread_no}.json")
