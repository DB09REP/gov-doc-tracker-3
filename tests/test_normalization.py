from decimal import Decimal

from normalization import enrich_item, largest_mentioned_amount, parse_amount


def test_parse_amount_supports_commas_and_multipliers():
    assert parse_amount("$1,250,000") == Decimal("1250000")
    assert parse_amount("$2.5 billion") == Decimal("2500000000.0")


def test_explicit_award_fields_are_preserved():
    item = enrich_item(
        {
            "source_name": "USASpending — new awards",
            "title": "Acme Corp — Department of Energy ($12000000)",
            "published": "2026-08-20",
            "company_name": "Acme Corp",
            "department_name": "Department of Energy",
            "amount": 12000000,
            "amount_type": "award_total",
        }
    )
    assert item["company_name"] == "Acme Corp"
    assert item["amount"] == Decimal("12000000")
    assert item["event_date"] == "2026-08-20"


def test_historical_cfpb_row_gets_source_specific_fields():
    item = enrich_item(
        {
            "source_name": "CFPB — recent consumer complaints",
            "title": "Example Bank — Credit card",
            "published": "2026-08-19",
        }
    )
    assert item["company_name"] == "Example Bank"
    assert item["department_name"] == "Consumer Financial Protection Bureau"


def test_mentioned_money_is_separate_from_authoritative_amounts():
    item = enrich_item(
        {
            "source_name": "DOJ press releases",
            "title": "Contractor agrees to pay $4.2 million",
            "summary": "Settlement includes $500,000 in restitution.",
            "published": "2026-08-18",
        }
    )
    assert largest_mentioned_amount(item["title"], item["summary"]) == Decimal("4200000.0")
    assert item["amount"] == Decimal("4200000.0")
    assert item["amount_type"] == "mentioned_amount"
