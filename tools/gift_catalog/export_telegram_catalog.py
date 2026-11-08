#!/usr/bin/env python3
"""Export CURRENT public Telegram Star Gifts metadata for review.

Requirements: pip install "telethon>=1.40"
Credentials: TG_API_ID and TG_API_HASH in environment. Interactive sign-in
uses the user's Telegram account with consent (not the HaslGram bot).
This script does not purchase, upgrade, scrape private accounts, or download
documents; it exports only metadata/IDs and CURRENT prices from the API.
"""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path


def document_ref(document):
    if document is None:
        return None
    return {
        "id": str(getattr(document, "id", "")),
        "access_hash_present": getattr(document, "access_hash", None) is not None,
        "mime_type": getattr(document, "mime_type", None),
    }


def serialize_attribute(attribute):
    kind = type(attribute).__name__
    return {
        "kind": kind,
        "name": getattr(attribute, "name", None),
        "backdrop_id": getattr(attribute, "backdrop_id", None),
        "center_color": getattr(attribute, "center_color", None),
        "edge_color": getattr(attribute, "edge_color", None),
        "pattern_color": getattr(attribute, "pattern_color", None),
        "text_color": getattr(attribute, "text_color", None),
        "document": document_ref(getattr(attribute, "document", None)),
        "rarity": type(getattr(attribute, "rarity", None)).__name__
          if getattr(attribute, "rarity", None) is not None else None,
        "crafted_only": bool(getattr(attribute, "crafted", False)),
    }


def serialize_gift(gift):
    """Current value is NOT a verified historical launch price."""
    return {
        "telegram_gift_id": str(gift.id),
        "current_telegram_stars": getattr(gift, "stars", None),
        "launch_stars": None,
        "launch_stars_verified": False,
        "launch_price_source": None,
        "upgrade_stars": getattr(gift, "upgrade_stars", None),
        "sold_out": bool(getattr(gift, "sold_out", False)),
        "limited": bool(getattr(gift, "limited", False)),
        "availability_total": getattr(gift, "availability_total", None),
        "availability_remains": getattr(gift, "availability_remains", None),
        "upgrade_variants": getattr(gift, "upgrade_variants", None),
        "sticker": document_ref(getattr(gift, "sticker", None)),
        "attributes": [],
        "metadata_source": "Telegram payments.getStarGifts",
        "ownership": "Telegram catalog reference; NOT an owned HaslGram asset",
    }


async def export_catalog(output: Path, session: Path, include_attributes: bool):
    from telethon import TelegramClient, functions
    api_id_text = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    if not api_id_text.isdecimal() or not api_hash:
        raise SystemExit("Set TG_API_ID and TG_API_HASH privately (never commit them).")

    # Telethon may ask interactively for a Telegram login code / 2FA password.
    # This is NOT a HaslGram MTProto account and cannot authorize purchases there.
    async with TelegramClient(str(session), int(api_id_text), api_hash) as client:
        result = await client(functions.payments.GetStarGiftsRequest(hash=0))
        gift_list = getattr(result, "gifts", None)
        if gift_list is None:
            raise RuntimeError("Telegram returned no catalog (not-modified/error).")

        gifts = []
        for gift in gift_list:
            item = serialize_gift(gift)
            if include_attributes:
                method = getattr(functions.payments, "GetStarGiftUpgradeAttributesRequest", None)
                if method is None:
                    raise RuntimeError("Installed Telethon schema has no GetStarGiftUpgradeAttributesRequest")
                try:
                    attributes_result = await client(method(gift_id=gift.id))
                    item["attributes"] = [
                        serialize_attribute(a)
                        for a in getattr(attributes_result, "attributes", [])
                    ]
                except Exception as exc:
                    item["attributes_error"] = type(exc).__name__
            gifts.append(item)

    payload = {
        "schema": "haslgram.telegram.gift-metadata.v1",
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "notes": [
            "CURRENT official Telegram prices are not verified LAUNCH prices.",
            "This export includes Telegram document IDs, not downloadable assets or rights.",
            "Buying or upgrading on HaslGram requires an independent server economy.",
        ],
        "gifts": gifts,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        output.chmod(0o600)
    except OSError:
        pass
    print(f"Exported {len(gifts)} gift metadata entries to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--session", type=Path, default=Path.home() / ".haslgram-gift-export")
    parser.add_argument("--attributes", action="store_true", help="Query collectible attribute metadata (slower).")
    args = parser.parse_args()
    asyncio.run(export_catalog(args.output, args.session, args.attributes))


if __name__ == "__main__":
    main()
