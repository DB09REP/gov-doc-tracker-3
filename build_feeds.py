"""Run every scraper, then write one combined RSS feed and one feed per
dashboard category into docs/feeds/ (served via GitHub Pages).

Each run persists normalized, versioned source records in Neon before
building feeds from durable history. Repeated overlapping polls are safe:
the event store de-duplicates by source id and payload hash while retaining
upstream revisions as distinct events.
"""
import html
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from dates import parse_date
from event_store import EventStore, load_local_env
from feed_extensions import GovEntryExtension, GovExtension

from scrapers import (
    sec_edgar,
    sec_litigation,
    fec,
    lobbying,
    courts,
    doj,
    congress_gov,
    federal_register,
    usaspending,
    cfpb,
    ofac,
)

OUT_DIR = Path(__file__).parent / "docs" / "feeds"
OUT_DIR.mkdir(parents=True, exist_ok=True)
load_local_env()
FEED_ITEM_LIMIT = int(os.environ.get("FEED_ITEM_LIMIT", "500"))

CATEGORY_LABELS = {
    "sec": "SEC",
    "fec": "FEC",
    "lobbying": "Lobbying",
    "courts": "Courts / DOJ",
    "congress": "Congress / Oversight",
    "adjacent": "Adjacent (Federal Register, USASpending, OFAC, CFPB)",
}

SCRAPERS = [
    ("SEC EDGAR new filings", sec_edgar.fetch_items),
    ("SEC litigation/admin proceedings", sec_litigation.fetch_items),
    ("FEC filings", fec.fetch_items),
    ("Lobbying disclosures", lobbying.fetch_items),
    ("CourtListener/RECAP", courts.fetch_items),
    ("DOJ press releases", doj.fetch_items),
    ("Congress.gov bills", congress_gov.fetch_items),
    ("Federal Register", federal_register.fetch_items),
    ("USASpending awards", usaspending.fetch_items),
    ("CFPB complaints", cfpb.fetch_items),
    ("OFAC sanctions actions", ofac.fetch_items),
]


def run_all_scrapers():
    all_items = []
    for label, fn in SCRAPERS:
        try:
            items = fn()
            print(f"[ok]   {label}: {len(items)} items")
            all_items.extend(items)
        except Exception as exc:
            print(f"[FAIL] {label}: {exc}", file=sys.stderr)
            traceback.print_exc()
    return all_items


_MOJIBAKE_CTRL = re.compile("[\x80-\x9f]")  # stray Windows-1252 bytes mis-decoded as raw control chars


def _clean_text(value):
    """Fix double-escaped HTML entities (some source APIs, e.g. DOJ, already
    return HTML-entity-encoded text like 'AT&amp;T'; feedgen escapes again
    on write, producing 'AT&amp;amp;T') and strip stray mojibake control
    bytes (e.g. a smart quote that got mis-decoded into \\x92).
    """
    if not value:
        return ""
    value = html.unescape(value)
    value = _MOJIBAKE_CTRL.sub("", value)
    return " ".join(value.split())


def _pages_base_url():
    """Best-effort guess at this repo's GitHub Pages base URL, used only
    for the feed's self-referencing <atom:link>. Falls back to a generic
    placeholder when run outside GitHub Actions (e.g. local testing).
    """
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo", set automatically in Actions
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"
    return "https://example.invalid/gov-doc-tracker"


def build_feed(title, description, link, items, out_path):
    fg = FeedGenerator()
    fg.register_extension("gov", GovExtension, GovEntryExtension, atom=False, rss=True)
    fg.title(title)
    fg.link(href=link, rel="alternate")
    fg.link(href=f"{_pages_base_url()}/feeds/{out_path.name}", rel="self")
    fg.description(description)
    fg.language("en")

    # De-duplicate by id — RSS requires unique guids per feed, and at least
    # one source (FEC) can legitimately return the same underlying filing
    # more than once (e.g. joint filings tied to multiple committees).
    # Keep first occurrence (already sorted newest-first at this point... 
    # actually dedupe before sort so "first seen" order doesn't matter).
    seen_ids = set()
    deduped = []
    for item in items:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        deduped.append(item)

    oldest = datetime.min.replace(tzinfo=timezone.utc)
    items_sorted = sorted(deduped, key=lambda i: parse_date(i.get("published")) or oldest, reverse=True)
    for item in items_sorted[:FEED_ITEM_LIMIT]:
        fe = fg.add_entry()
        fe.id(item["id"])
        fe.title(_clean_text(item["title"])[:300])
        fe.link(href=item["link"])
        fe.description(_clean_text(item.get("summary", "")))
        fe.pubDate(parse_date(item.get("published")) or oldest)
        if item.get("source_name"):
            fe.category(term=item["source_name"])
        for category in (item.get("department_name"), item.get("company_name")):
            if category:
                fe.category(term=str(category))
        fe.gov.fields(
            {
                "company_name": item.get("company_name"),
                "entity_name": item.get("entity_name"),
                "department_name": item.get("department_name"),
                "amount": item.get("amount"),
                "amount_currency": item.get("amount_currency"),
                "amount_type": item.get("amount_type"),
                "event_date": item.get("event_date"),
            }
        )

    fg.rss_file(str(out_path))
    print(f"wrote {out_path} ({len(items_sorted[:FEED_ITEM_LIMIT])} items, {len(items) - len(deduped)} duplicate ids dropped)")


def build_outputs(store):
    """Build all public files from durable Neon history."""
    all_items = store.fetch_items(limit=FEED_ITEM_LIMIT)

    # Combined feed, everything
    build_feed(
        title="Federal Document Tracker — All Sources",
        description="Combined feed across SEC, FEC, lobbying, courts/DOJ, Congress/oversight, and adjacent federal sources.",
        link="https://www.sec.gov/",
        items=all_items,
        out_path=OUT_DIR / "all.xml",
    )

    # One feed per dashboard category
    for cat, label in CATEGORY_LABELS.items():
        cat_items = store.fetch_items(category=cat, limit=FEED_ITEM_LIMIT)
        build_feed(
            title=f"Federal Document Tracker — {label}",
            description=f"{label} filings and documents.",
            link="https://www.sec.gov/",
            items=cat_items,
            out_path=OUT_DIR / f"{cat}.xml",
        )

    # Simple index page linking to all feeds
    index_html = ["<html><head><title>Federal Document Tracker Feeds</title></head><body>",
                  "<h1>Federal Document Tracker — RSS Feeds</h1>",
                  f"<p>Last built: {datetime.now(timezone.utc).isoformat()}</p>",
                  "<ul>",
                  '<li><a href="feeds/all.xml">All sources (combined)</a></li>']
    for cat, label in CATEGORY_LABELS.items():
        index_html.append(f'<li><a href="feeds/{cat}.xml">{label}</a></li>')
    index_html.append("</ul></body></html>")
    (OUT_DIR.parent / "index.html").write_text("\n".join(index_html))


def main():
    scraped_items = run_all_scrapers()
    store = EventStore.from_env()
    result = store.store_items(scraped_items)
    print(
        "retention: "
        f"received={result.received} accepted={result.accepted} "
        f"rejected_expired={result.rejected_expired} "
        f"rejected_future={result.rejected_future}"
    )
    pruned_count = store.prune_expired()
    print(f"retention: physically_pruned={pruned_count}")
    build_outputs(store)


if __name__ == "__main__":
    main()
