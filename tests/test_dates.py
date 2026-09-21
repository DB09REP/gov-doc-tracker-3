import unittest
from datetime import timezone

from dates import parse_date


class ParseDateTests(unittest.TestCase):
    def test_sec_compact_date(self):
        parsed = parse_date("20260825")
        self.assertEqual(parsed.isoformat(), "2026-08-25T00:00:00+00:00")

    def test_iso_z_timestamp(self):
        parsed = parse_date("2026-08-25T14:30:15.123Z")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.microsecond, 123000)

    def test_rfc_timestamp(self):
        parsed = parse_date("Tue, 25 Aug 2026 14:30:15 +0000")
        self.assertEqual(parsed.isoformat(), "2026-08-25T14:30:15+00:00")

    def test_invalid_date_is_not_now(self):
        self.assertIsNone(parse_date("not-a-date"))
        self.assertIsNone(parse_date(""))


if __name__ == "__main__":
    unittest.main()
