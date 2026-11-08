import unittest
from types import SimpleNamespace

from catalog_import import build_gift_record, build_snapshot


class CatalogImportTests(unittest.TestCase):
    def test_initial_price_is_never_guessed_from_current_price(self):
        gift = SimpleNamespace(
            id=42, title="Test gift", slug="test-gift", stars=75,
            first_sale_date=1700000000, last_sale_date=1700001000,
            limited=True, sold_out=False, birthday=False, require_premium=False,
            limited_per_user=False, availability_total=100, availability_remains=25,
            upgrade_stars=100, upgrade_variants=12, can_upgrade=True,
            sticker=SimpleNamespace(id=99, mime_type="application/x-tgsticker", size=4096),
        )
        record = build_gift_record(gift)
        self.assertEqual(record["currentPriceStars"], 75)
        self.assertIsNone(record["initialPriceStars"])
        self.assertEqual(record["initialPriceStatus"], "unverified")
        self.assertEqual(record["giftId"], "42")
        self.assertEqual(record["sticker"]["documentId"], "99")

    def test_snapshot_marks_source_currency_and_asset_limits(self):
        snapshot = build_snapshot([], captured_at="2026-11-08T00:00:00+00:00")
        self.assertEqual(snapshot["currency"], "Telegram Stars (source metadata only; not Hasl Stars)")
        self.assertTrue(any("original launch price" in warning for warning in snapshot["warnings"]))
        self.assertEqual(snapshot["gifts"], [])


if __name__ == "__main__":
    unittest.main()
