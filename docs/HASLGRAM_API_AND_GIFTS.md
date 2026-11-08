# HaslGram API credentials, isolated MTProto routing, and gifts

## Application credentials

Use a dedicated API ID/hash from https://my.telegram.org. The same pair must be configured in:

- Android build inputs: HASLGRAM_API_ID, HASLGRAM_API_HASH
- Teamgram BFF runtime environment: the same two values

The client sends these values in auth.sendCode; the Teamgram fork now checks them against the BFF environment and redacts the hash from logs. API ID/hash identify the application; they are not the user's authentication factor. User access is still protected by the one-time code from @HaslGramRegBot.

Do not commit local.properties, bot tokens, user sessions, Firebase configuration, or signing keys. The Android API hash is embedded in the APK at build time and can be extracted from it; do not treat it as a password.

## Android local build

Add to ignored local.properties (or export the same environment variables):

~~~properties
HASLGRAM_API_ID=123456
HASLGRAM_API_HASH=0123456789abcdef0123456789abcdef
HASLGRAM_MTPROTO_HOST=mtproto.your-domain.example
HASLGRAM_MTPROTO_PORT=10443
~~~

The values are examples only. Use your real ID/hash and the public DNS name or IPv4 address of the HaslGram gateway. The C++ MTProto client now creates only DC 1 and routes it to this host/port. It no longer includes Telegram production or test DC fallback addresses. With no host configured it defaults to loopback, so an unconfigured build cannot silently log into official Telegram.

The package ID is com.haslgram.messenger; the debug APK uses com.haslgram.messenger.debug. Official Telegram Firebase/Google OAuth/SafetyNet credentials and update/cloud-string paths are disabled. Push notifications need a new HaslGram Firebase project; the official Telegram google-services.json and Huawei configuration files have been removed. Until your own Firebase config is supplied, FCM push is not available.

## Bot-only registration

The Teamgram BFF now requires HASLGRAM_API_ID, HASLGRAM_API_HASH, and HASLGRAM_REGISTRATION_VERIFY_URL at startup. The bot OTP is six digits. Teamgram's internal random placeholder is never accepted; the client must pass the phone and code to the private NestJS verification endpoint. Resend through Teamgram is disabled; the user requests a fresh code from the bot.

The Go provider supports these runtime settings:

- HASLGRAM_REGISTRATION_VERIFY_URL — actual private NestJS endpoint.
- HASLGRAM_REGISTRATION_PHONE_FIELD — phoneE164 (default) or phoneNumber, according to the existing DTO.
- HASLGRAM_REGISTRATION_SUCCESS_FIELD — boolean response field to require (default success; allowed values success, valid, verified, ok).
- HASLGRAM_REGISTRATION_VERIFY_TOKEN — optional service-to-service Bearer token.

The default URL/DTO in the staging README is only a placeholder. The existing haslgram-gift-engine source was not accessible in this GitHub repository, so the exact controller route, DTO field, token requirement, and response status must be verified against that backend before starting the BFF. The endpoint must atomically consume the code and grant the 2,000 Hasl Stars welcome bonus exactly once.

## Gift catalog and Hasl Stars

The Android source already contains Telegram's gift UI and MTProto gift TL types. The independent Teamgram Community server does not implement the full Telegram gift API, so simply adding API ID/hash does not make those methods work against HaslGram.

A separate read-only importer is provided in deploy/teamgram/gifts:

- payments.getStarGifts supports both users and bots and can fetch the available catalog.
- payments.getStarGiftUpgradeAttributes is user-only and requires an existing user session; a bot token alone cannot fetch all upgrade attribute distributions. A user StringSession is a full account credential, so only use a dedicated account and keep the session out of Git and logs.
- Current observed prices are not guaranteed to equal original launch prices. The importer leaves initialPriceStars null until verified from dated evidence.
- Sticker document IDs are metadata only. No media is copied. Confirm rights before mirroring any media.

The real HaslGram gift system must still use the HaslGram ledger, not Telegram Stars: server-authoritative catalog pricing, atomic debits, idempotent gift issuance, upgrade fees, server-side random collectible attributes/probabilities, ownership, transfer, and profile display. The NestJS gift-engine repository was not available through the connected GitHub account in this session, so that backend cannot be safely changed here yet.

## Build and deployment status

- Teamgram staging and auth patches are in the GitHub branch.
- Android API credentials and the gateway host are injected at build time; no real values are committed.
- Debug build workflow is manual and requires GitHub secrets/variables.
- VPS staging workflow is manual and requires SSH host/user/key/known-hosts secrets. It only stages a separate Teamgram checkout; it does not start containers, open firewall ports, or touch the running gift engine.
- Production still needs a real VPS run, verified NestJS contract, fresh Firebase project for push, own release signing key, and full functional tests.

## GitHub settings required before running workflows

In the repository Settings → Secrets and variables → Actions:

Repository secrets:
- HASLGRAM_API_ID
- HASLGRAM_API_HASH
- HASLGRAM_VPS_HOST
- HASLGRAM_VPS_USER
- HASLGRAM_VPS_SSH_PRIVATE_KEY
- HASLGRAM_VPS_KNOWN_HOSTS

Repository variables:
- HASLGRAM_MTPROTO_HOST
- HASLGRAM_MTPROTO_PORT (optional; defaults to 10443)

The VPS workflow only stages a new Teamgram checkout under /opt/haslgram; it does not start services or edit the existing gift backend. The API credentials must be the same values in the Android build and the Teamgram BFF environment.
