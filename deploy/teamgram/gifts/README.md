# Read-only Telegram gift catalog importer

This tool uses your own Telegram API ID/hash to fetch public gift-catalog metadata for review. It does not buy gifts, send gifts, spend Telegram Stars, access a user's profile, or download media files.

## Credentials

Get an application api_id and api_hash from https://my.telegram.org. They identify the MTProto application; they do not by themselves authenticate a Telegram account.

For payments.getStarGifts, Telegram documents support for both users and bots. Provide one of:

- HASLGRAM_CATALOG_BOT_TOKEN: preferably a dedicated bot token, used only for the read-only catalog request.
- HASLGRAM_CATALOG_USER_SESSION: a dedicated Telegram user StringSession, if you also want to call payments.getStarGiftUpgradeAttributes. That session is a full account credential, not a limited read-only token; use a dedicated account and store it securely. Telegram documents that upgrade-attribute method as users only.

Never commit API credentials, bot tokens, or StringSessions. Supply them through the VPS secret store.

## Run

~~~bash
cd /opt/haslgram/haslgram-platform
python3 -m venv .venv-gifts
. .venv-gifts/bin/activate
pip install -r deploy/teamgram/gifts/requirements.txt

export HASLGRAM_API_ID='your_api_id'
export HASLGRAM_API_HASH='your_32_character_api_hash'
export HASLGRAM_CATALOG_BOT_TOKEN='your_dedicated_catalog_bot_token'
# Optional; only if you have deliberately provisioned a dedicated user session:
# export HASLGRAM_CATALOG_USER_SESSION='your_existing_string_session'

python deploy/teamgram/gifts/catalog_import.py \
  --output /opt/haslgram/catalog/telegram-gifts.snapshot.json
~~~

## Data contract and important limits

- currentPriceStars is the price observed when the snapshot is taken.
- initialPriceStars is always null and initialPriceStatus is unverified. The live catalog does not prove the original launch price for every gift. HaslGram must verify each historic price from dated evidence before selling it.
- Upgrade attributes are fetched only when a user StringSession is supplied; the bot-only catalog run records requires_user_session.
- Sticker document IDs are metadata only. No media is copied. Obtain and document the rights/permissions for any media that HaslGram stores or redistributes.
- Telegram Stars are source-catalog metadata, not Hasl Stars. The HaslGram backend must set its own prices, debit its own ledger atomically, and generate its own collectible attributes on the server.

Official references: https://core.telegram.org/method/payments.getStarGifts, https://core.telegram.org/method/payments.getStarGiftUpgradeAttributes, https://core.telegram.org/api/gifts.
