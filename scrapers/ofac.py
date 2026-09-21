import re
import sys
"""Treasury OFAC — recent sanctions actions.

NO OFFICIAL API for this page. HTML-scraped, same caveats as
oversight.py / gao.py.
"""
from bs4 import BeautifulSoup
from .http import get

CATEGORY = "adjacent"
SOURCE_NAME = "OFAC — recent sanctions actions"
URL = "https://ofac.treasury.gov/recent-actions"


def fetch_items(limit=40):
    try:
        resp = get(URL)
    except Exception as exc:
        print(f"[detail] OFAC sanctions actions: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    for row in soup.select("table a, .views-row a, h3 a")[:limit * 2]:
        title = row.get_text(strip=True)
        href = row.get("href", "")
        if not title or not href or len(title) < 6:
            continue
        link = href if href.startswith("http") else f"https://ofac.treasury.gov{href}"
        date_match = re.search(r"/(20\d{6})(?:/|$)", link)
        event_date = date_match.group(1) if date_match else ""
        item_id = link
        if item_id in {i["id"] for i in items}:
            continue
        items.append({
            "id": f"ofac-{item_id}",
            "title": title,
            "link": link,
            "summary": "New or updated OFAC sanctions action.",
            "published": "",
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
            "department_name": "Department of the Treasury — OFAC",
            "event_date": event_date,
        })
        if len(items) >= limit:
            break
    return items
