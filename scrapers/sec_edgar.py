"""SEC EDGAR — new filings.

IMPORTANT: sec.gov/robots.txt disallows /cgi-bin, which rules out the
"getcurrent" atom feed for automated use. Instead this uses the daily
index files under /Archives/edgar/daily-index/, which sit under the
explicitly-allowed /Archives/edgar/ path and are the SEC-sanctioned
machine-readable way to get "everything filed today."

We filter the daily index to a watchlist of form types that tend to
carry news (8-K, SC 13D/13D-A, NT filings, 25-NSE) — edit FORM_TYPES
below to widen or narrow it.
"""
import sys
from datetime import date, timedelta
from .http import get, polite_sleep

FORM_TYPES = {"8-K", "SC 13D", "SC 13D/A", "NT 10-K", "NT 10-Q", "25-NSE"}

CATEGORY = "sec"
SOURCE_NAME = "SEC EDGAR — new filings"


def _quarter(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _index_url_for(d: date) -> str:
    q = _quarter(d)
    datestr = d.strftime("%Y%m%d")
    return f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/master.{datestr}.idx"


def fetch_items(days_back=5):
    """Pull the last few days' daily index files and filter to FORM_TYPES.

    Defaults to 5 days back (not just today) because: (a) today's index
    file may not be posted yet depending on when in the day this runs,
    and (b) weekends/holidays have no file at all, so checking only
    "today" can come up completely empty even though nothing is wrong.
    """
    items = []
    today = date.today()
    for offset in range(days_back):
        d = today - timedelta(days=offset)
        url = _index_url_for(d)
        try:
            resp = get(url)
        except Exception as exc:
            print(f"[detail] SEC EDGAR new filings: {type(exc).__name__}: {exc} (url={url})", file=sys.stderr)
            continue  # weekends/holidays have no index file — expected, not an error
        polite_sleep(0.3)

        text = resp.text
        lines = text.splitlines()
        # The .idx format is pipe-delimited with a fixed header ending in a
        # "-----" separator row before the data starts.
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("---"):
                start = i + 1
                break
        for line in lines[start:]:
            parts = line.split("|")
            if len(parts) != 5:
                continue
            cik, company, form_type, date_filed, filename = parts
            if form_type not in FORM_TYPES:
                continue
            doc_url = f"https://www.sec.gov/Archives/{filename.strip()}"
            items.append({
                "id": f"sec-edgar-{filename.strip()}",
                "title": f"{form_type} — {company.strip()} (CIK {cik.strip()})",
                "link": doc_url,
                "summary": f"Form {form_type} filed {date_filed} by {company.strip()}.",
                "published": date_filed,
                "category": CATEGORY,
                "source_name": SOURCE_NAME,
                "company_name": company.strip(),
                "entity_name": company.strip(),
                "department_name": "Securities and Exchange Commission",
                "event_date": date_filed,
            })
    return items
