"""Conservative structured-field normalization for government events."""

import re
from decimal import Decimal, InvalidOperation

from dates import parse_date


_MONEY_RE = re.compile(
    r"(?<![\w])(?:US\s*)?\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)"
    r"\s*(thousand|million|billion|trillion|[kmbt])?\b",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "": Decimal("1"),
    "k": Decimal("1000"),
    "thousand": Decimal("1000"),
    "m": Decimal("1000000"),
    "million": Decimal("1000000"),
    "b": Decimal("1000000000"),
    "billion": Decimal("1000000000"),
    "t": Decimal("1000000000000"),
    "trillion": Decimal("1000000000000"),
}


def parse_amount(value):
    """Return a Decimal for a numeric or US-dollar value, otherwise None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip()
    try:
        return Decimal(text.replace("$", "").replace(",", ""))
    except InvalidOperation:
        match = _MONEY_RE.search(text)
        if not match:
            return None
        return Decimal(match.group(1).replace(",", "")) * _MULTIPLIERS[
            (match.group(2) or "").lower()
        ]


def largest_mentioned_amount(*values):
    """Find the largest explicitly dollar-prefixed amount in text."""
    amounts = []
    for value in values:
        for number, suffix in _MONEY_RE.findall(str(value or "")):
            amounts.append(
                Decimal(number.replace(",", ""))
                * _MULTIPLIERS[(suffix or "").lower()]
            )
    return max(amounts) if amounts else None


def _clean(value):
    value = str(value or "").strip()
    return value or None


def enrich_item(item):
    """Add canonical fields while retaining the original source payload.

    Explicit scraper fields win. Source-specific fallbacks make historical
    rows useful, but inferred text amounts are clearly labelled so they are
    not confused with authoritative transaction values.
    """
    enriched = dict(item)
    source = str(item.get("source_name") or "")
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or "")

    company = _clean(item.get("company_name"))
    entity = _clean(item.get("entity_name"))
    department = _clean(item.get("department_name"))
    amount = parse_amount(item.get("amount"))
    amount_type = _clean(item.get("amount_type"))

    if "USASpending" in source:
        if " — " in title:
            company = company or _clean(title.split(" — ", 1)[0])
            agency_part = title.split(" — ", 1)[1]
            department = department or _clean(agency_part.split(" ($", 1)[0])
        if amount is None:
            amount = largest_mentioned_amount(title)
        amount_type = amount_type or ("award_total" if amount is not None else None)
    elif "CFPB" in source:
        company = company or _clean(title.split(" — ", 1)[0])
        department = department or "Consumer Financial Protection Bureau"
    elif "SEC EDGAR" in source:
        if " — " in title:
            company = company or _clean(title.split(" — ", 1)[1].split(" (CIK", 1)[0])
        department = department or "Securities and Exchange Commission"
    elif source.startswith("SEC "):
        department = department or "Securities and Exchange Commission"
    elif source.startswith("FEC"):
        entity = entity or _clean(title.split(" — ", 1)[-1])
        department = department or "Federal Election Commission"
    elif "Lobbying" in source:
        department = department or "Congress — Lobbying Disclosure Act"
        match = re.search(r" — (.+?) for (.+)$", title)
        if match:
            entity = entity or _clean(match.group(2))
    elif "CourtListener" in source:
        entity = entity or _clean(title.rsplit(" (", 1)[0])
        department = department or "Federal Judiciary"
    elif source.startswith("DOJ"):
        department = department or "Department of Justice"
    elif source.startswith("Congress.gov"):
        department = department or "United States Congress"
    elif source.startswith("Federal Register"):
        department = department or _clean(summary.removeprefix("Agencies: "))
    elif source.startswith("OFAC"):
        department = department or "Department of the Treasury — OFAC"

    if amount is None and (
        source.startswith("DOJ")
        or source.startswith("SEC litigation")
        or source.startswith("SEC administrative")
    ):
        amount = largest_mentioned_amount(title, summary)
        if amount is not None:
            amount_type = "mentioned_amount"

    event_dt = parse_date(item.get("event_date") or item.get("published"))
    enriched.update(
        {
            "company_name": company,
            "entity_name": entity or company,
            "department_name": department,
            "amount": amount,
            "amount_currency": _clean(item.get("amount_currency")) or ("USD" if amount is not None else None),
            "amount_type": amount_type,
            "event_date": event_dt.date().isoformat() if event_dt else None,
        }
    )
    return enriched
