import unittest
from types import SimpleNamespace

from export_telegram_catalog import serialize_gift, serialize_attribute


class GiftMetadataTests(unittest.TestCase):
    def test_launch_price_not_invented_from_current(self):
        gift = SimpleNamespace(id=123, stars=500, sold_out=False, limited=False)
        data = serialize_gift(gift)
        self.assertEqual(data["current_telegram_stars"], 500)
        self.assertIsNone(data["launch_stars"])
        self.assertFalse(data["launch_stars_verified"])
        self.assertEqual(data["telegram_gift_id"], "123")

    def test_attribute_fields_no_access_hash_leak(self):
        document = SimpleNamespace(id=111, access_hash=999999, mime_type="application/x-tgsticker")
        attr = SimpleNamespace(name="Pattern", document=document, rarity=SimpleNamespace())
        data = serialize_attribute(attr)
        self.assertEqual(data["document"]["id"], "111")
        self.assertNotIn("access_hash", data["document"])
        self.assertTrue(data["document"]["access_hash_present"])

    def test_missing_optional_fields(self):
        data = serialize_gift(SimpleNamespace(id=11))
        self.assertIsNone(data["upgrade_stars"])
        self.assertEqual(data["attributes"], [])


if __name__ == "__main__":
    unittest.main()
