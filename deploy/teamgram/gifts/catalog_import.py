#!/usr/bin/env python3
"""Read-only Telegram Star Gift catalog snapshot for HaslGram.

No purchases, profile access, media downloads, or Telegram Stars spending occur.
API credentials and sessions are read only from environment variables.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _int_or_none(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _safe_tl_dict(value: Any) -> Any:
    """Serialize TL metadata while excluding expiring auth/file references."""
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        return {
            str(k): _safe_tl_dict(v)
            for k, v in value.items()
            if str(k).lower() not in {"file_reference", "access_hash", "phone", "phone_number", "token"}
        }
    if isinstance(value, (list, tuple)):
        return [_safe_tl_dict(v) for v in value]
    if isinstance(value, bytes):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_gift_record(gift: Any) -> dict[str, Any]:
    sticker = getattr(gift, "sticker", None)
    sticker_id = getattr(sticker, "id", None) if sticker is not None else None
    return {
        "giftId": str(getattr(gift, "id")),
        "title": getattr(gift, "title", None),
        "slug": getattr(gift, "slug", None),
        "currentPriceStars": _int_or_none(getattr(gift, "stars", None)),
        # Telegram's current catalog response is not a verified historical price ledger.
        "initialPriceStars": None,
        "initialPriceStatus": "unverified",
        "firstSaleDate": _int_or_none(getattr(gift, "first_sale_date", None)),
        "lastSaleDate": _int_or_none(getattr(gift, "last_sale_date", None)),
        "limited": bool(getattr(gift, "limited", False)),
        "soldOut": bool(getattr(gift, "sold_out", False)),
        "birthday": bool(getattr(gift, "birthday", False)),
        "requirePremium": bool(getattr(gift, "require_premium", False)),
        "limitedPerUser": bool(getattr(gift, "limited_per_user", False)),
        "availabilityTotal": _int_or_none(getattr(gift, "availability_total", None)),
        "availabilityRemains": _int_or_none(getattr(gift, "availability_remains", None)),
        "upgradeStars": _int_or_none(getattr(gift, "upgrade_stars", None)),
        "upgradeVariants": _int_or_none(getattr(gift, "upgrade_variants", None)),
        "canUpgrade": bool(getattr(gift, "can_upgrade", False)),
        "sticker": {
            "documentId": str(sticker_id) if sticker_id is not None else None,
            "mimeType": getattr(sticker, "mime_type", None) if sticker is not None else None,
            "size": _int_or_none(getattr(sticker, "size", None)) if sticker is not None else None,
        },
        "upgradeAttributes": None,
        "upgradeAttributesStatus": "requires_user_session",
    }


def build_snapshot(gifts: list[Any], captured_at: str | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "source": "Telegram MTProto payments.getStarGifts",
        "capturedAt": captured_at or datetime.now(timezone.utc).isoformat(),
        "currency": "Telegram Stars (source metadata only; not Hasl Stars)",
        "warnings": [
            "currentPriceStars is the price observed at capture time, not a verified original launch price",
            "initialPriceStars remains null until independently verified from dated evidence",
            "document IDs are metadata only; no Telegram media is downloaded or mirrored",
            "this snapshot is not a purchase API and must not be used to charge Telegram Stars",
        ],
        "gifts": [build_gift_record(gift) for gift in gifts],
    }


def validate_environment() -> tuple[int, str, str | None, str | None]:
    api_id_raw = os.environ.get("HASLGRAM_API_ID", "").strip()
    api_hash = os.environ.get("HASLGRAM_API_HASH", "").strip()
    bot_token = os.environ.get("HASLGRAM_CATALOG_BOT_TOKEN", "").strip() or None
    user_session = os.environ.get("HASLGRAM_CATALOG_USER_SESSION", "").strip() or None
    if not api_id_raw.isdigit() or int(api_id_raw) <= 0:
        raise ValueError("HASLGRAM_API_ID must be a positive integer")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise ValueError("HASLGRAM_API_HASH must be a 32-character hexadecimal value")
    if not bot_token and not user_session:
        raise ValueError("Set a dedicated HASLGRAM_CATALOG_BOT_TOKEN or a dedicated user StringSession")
    return int(api_id_raw), api_hash, bot_token, user_session


async def run_import(output: Path) -> int:
    try:
        api_id, api_hash, bot_token, user_session = validate_environment()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.tl.functions.payments import GetStarGiftsRequest
    except ImportError:
        print("Install deploy/teamgram/gifts/requirements.txt first", file=sys.stderr)
        return 2

    catalog_client = None
    user_client = None
    try:
        if bot_token:
            catalog_client = TelegramClient(StringSession(), api_id, api_hash)
            await catalog_client.start(bot_token=bot_token)
        else:
            catalog_client = TelegramClient(StringSession(user_session), api_id, api_hash)
            await catalog_client.connect()
            if not await catalog_client.is_user_authorized():
                print("The configured user StringSession is not authorized", file=sys.stderr)
                return 2

        result = await catalog_client(GetStarGiftsRequest(hash=0))
        gifts = list(getattr(result, "gifts", []) or [])
        snapshot = build_snapshot(gifts)

        if user_session:
            if bot_token:
                user_client = TelegramClient(StringSession(user_session), api_id, api_hash)
                await user_client.connect()
            else:
                # Reuse the catalog client when it is already the user session.
                user_client = catalog_client
            if not await user_client.is_user_authorized():
                print("The configured user StringSession is not authorized", file=sys.stderr)
                return 2
            try:
                from telethon.tl.functions.payments import GetStarGiftUpgradeAttributesRequest
            except ImportError:
                GetStarGiftUpgradeAttributesRequest = None
            if GetStarGiftUpgradeAttributesRequest is not None:
                for record, gift in zip(snapshot["gifts"], gifts):
                    if not record["canUpgrade"] and not (record["upgradeVariants"] or 0):
                        record["upgradeAttributesStatus"] = "not_available"
                        continue
                    try:
                        attrs = await user_client(
                            GetStarGiftUpgradeAttributesRequest(gift_id=int(gift.id))
                        )
                        record["upgradeAttributes"] = _safe_tl_dict(
                            getattr(attrs, "attributes", []) or []
                        )
                        record["upgradeAttributesStatus"] = "fetched"
                    except Exception as exc:
                        record["upgradeAttributesStatus"] = "fetch_failed"
                        record["upgradeAttributesError"] = type(exc).__name__
            else:
                for record in snapshot["gifts"]:
                    record["upgradeAttributesStatus"] = "unsupported_by_installed_telethon"
        else:
            for record in snapshot["gifts"]:
                record["upgradeAttributesStatus"] = "requires_user_session"

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(gifts)} gift metadata records to {output}")
        return 0
    except Exception as exc:
        print(f"Catalog import failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        if user_client is not None and user_client is not catalog_client:
            await user_client.disconnect()
        if catalog_client is not None:
            await catalog_client.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="destination JSON snapshot path")
    args = parser.parse_args()
    return asyncio.run(run_import(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
