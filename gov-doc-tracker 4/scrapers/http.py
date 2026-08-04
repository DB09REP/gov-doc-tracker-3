"""Shared HTTP session used by every scraper.

Government sites (especially SEC) require a descriptive User-Agent and
ask that automated clients moderate their request rate. This module
centralizes that so every scraper behaves.
"""
import os
import time
import requests

CONTACT = os.environ.get("SCRAPER_CONTACT_EMAIL", "set-SCRAPER_CONTACT_EMAIL-secret@example.com")
USER_AGENT = f"gov-doc-tracker/1.0 ({CONTACT})"

_session = requests.Session()
_session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json, application/xml, text/html, */*",
})


def get(url, params=None, timeout=30, retries=3, backoff=2.0, headers=None):
    """GET with retries and a small delay, used by all scrapers."""
    last_exc = None
    for attempt in range(retries):
        try:
            resp = _session.get(url, params=params, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(backoff * (attempt + 1))
    raise last_exc


def polite_sleep(seconds=0.5):
    """Call between requests to a single host in a loop (e.g. SEC's 10 req/sec cap)."""
    time.sleep(seconds)
