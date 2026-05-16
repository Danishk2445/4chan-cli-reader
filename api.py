"""Read-only client for the 4chan JSON API (https://a.4cdn.org).

Honours 4chan's "max one request per second" guideline via a module-level
throttle.
"""

import time

import requests

BASE = "https://a.4cdn.org"
HEADERS = {"User-Agent": "4chan-cli-reader/1.0"}
_last_request_time = 0.0


def _get(url: str):
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    _last_request_time = time.time()
    resp.raise_for_status()
    return resp.json()


def get_boards() -> list[dict]:
    return _get(f"{BASE}/boards.json")["boards"]


def get_catalog(board: str) -> list[dict]:
    return _get(f"{BASE}/{board}/catalog.json")


def get_thread(board: str, thread_no: int) -> dict:
    return _get(f"{BASE}/{board}/thread/{thread_no}.json")
