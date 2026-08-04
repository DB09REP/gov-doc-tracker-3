"""SEC enforcement — litigation releases + administrative proceedings.

Both pages publish their own RSS feeds (linked from the human-readable
pages, not under /cgi-bin, so robots.txt-clean). We just parse and
re-normalize them.

Uses feedparser instead of raw XML parsing: SEC's feeds have occasionally
included unescaped characters (e.g. bare & in party names) that make
strict XML parsers (ElementTree) throw "not well-formed" errors.
feedparser is built to tolerate exactly this kind of real-world mess.
"""
import sys
import feedparser
from .http import get, polite_sleep

CATEGORY = "sec"

FEEDS = [
    ("SEC litigation releases", "https://www.sec.gov/enforcement-litigation/litigation-releases/rss"),
    ("SEC administrative proceedings", "https://www.sec.gov/enforcement-litigation/administrative-proceedings/rss"),
]


def _parse_rss(xml_text, source_name):
    items = []
    parsed = feedparser.parse(xml_text)
    if parsed.bozo and not parsed.entries:
        # bozo=True just means "not strictly well-formed"; feedparser still
        # usually recovers entries anyway. Only log if it recovered nothing.
        print(f"[detail] SEC litigation/admin proceedings: feedparser found 0 entries for {source_name}: {parsed.bozo_exception}", file=sys.stderr)
    for entry in parsed.entries:
        link = getattr(entry, "link", "").strip()
        title = getattr(entry, "title", "").strip()
        pub = getattr(entry, "published", "")
        desc = getattr(entry, "summary", "")
        if not link:
            continue
        items.append({
            "id": f"sec-lit-{link}",
            "title": title or source_name,
            "link": link,
            "summary": desc,
            "published": pub,
            "category": CATEGORY,
            "source_name": source_name,
        })
    return items


def fetch_items():
    all_items = []
    for name, url in FEEDS:
        try:
            resp = get(url)
            all_items.extend(_parse_rss(resp.text, name))
        except Exception as exc:
            print(f"[detail] SEC litigation/admin proceedings: {type(exc).__name__}: {exc} (url={url})", file=sys.stderr)
            continue
        polite_sleep(0.3)
    return all_items
