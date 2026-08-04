"""Congress.gov — recently updated bills.

Free key (5,000 req/hr): https://api.congress.gov/sign-up/
Set as CONGRESS_API_KEY GitHub Actions secret.
"""
import os
import sys
from .http import get

CATEGORY = "congress"
SOURCE_NAME = "Congress.gov — recent bill activity"
BASE = "https://api.congress.gov/v3"


def fetch_items(limit=40):
    api_key = (os.environ.get("CONGRESS_API_KEY") or "").strip()
    if not api_key:
        print("[detail] Congress.gov bills: CONGRESS_API_KEY is not set (env var empty) — check the GitHub secret name matches exactly", file=sys.stderr)
        return []

    url = f"{BASE}/bill"
    params = {
        "api_key": api_key,
        "sort": "updateDate+desc",
        "limit": limit,
        "format": "json",
    }
    try:
        resp = get(url, params=params)
    except Exception as exc:
        print(f"[detail] Congress.gov bills: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    data = resp.json()
    items = []
    for b in data.get("bills", []):
        title = b.get("title", "Untitled bill")
        congress = b.get("congress", "")
        btype = b.get("type", "")
        number = b.get("number", "")
        updated = b.get("updateDate", "")
        latest_action = (b.get("latestAction") or {}).get("text", "")
        link = f"https://www.congress.gov/bill/{congress}th-congress/{btype.lower()}/{number}"
        items.append({
            "id": f"congress-{congress}-{btype}-{number}",
            "title": f"{btype} {number}: {title}",
            "link": link,
            "summary": latest_action,
            "published": updated,
            "category": CATEGORY,
            "source_name": SOURCE_NAME,
        })
    return items
