"""Run every scraper, then write one combined RSS feed and one feed per
dashboard category into docs/feeds/ (served via GitHub Pages).

Design choice: each run fetches "recent" items fresh (last N per source,
or last few days for date-filtered sources) rather than tracking
per-source state. RSS readers dedupe by <guid> on their end, so a feed
that always contains the latest ~200 items per category works fine and
keeps this script simple and stateless.
"""
import sys
import traceback
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from feedgen.feed import FeedGenerator

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


def _parse_date(value):
    """Best-effort parse of whatever date string a scraper handed back.
    Falls back to "now" so items without a usable date still sort/appear
    rather than crashing feed generation.
    """
    if not value:
        return datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return datetime.now(timezone.utc)


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


def build_feed(title, description, link, items, out_path):
    fg = FeedGenerator()
    fg.title(title)
    fg.link(href=link, rel="alternate")
    fg.description(description)
    fg.language("en")

    # newest first
    items_sorted = sorted(items, key=lambda i: _parse_date(i.get("published")), reverse=True)
    for item in items_sorted[:200]:
        fe = fg.add_entry()
        fe.id(item["id"])
        fe.title(item["title"][:300])
        fe.link(href=item["link"])
        fe.description(item.get("summary", ""))
        fe.pubDate(_parse_date(item.get("published")))
        fe.source(item.get("source_name", ""))

    fg.rss_file(str(out_path))
    print(f"wrote {out_path} ({len(items_sorted[:200])} items)")


def main():
    all_items = run_all_scrapers()

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
        cat_items = [i for i in all_items if i.get("category") == cat]
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


if __name__ == "__main__":
    main()
