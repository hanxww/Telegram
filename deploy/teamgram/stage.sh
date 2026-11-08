#!/usr/bin/env bash
set -euo pipefail
# Stage a separate, pinned, bot-auth-patched Teamgram tree. DOES NOT START IT.
readonly UPSTREAM="https://github.com/teamgram/teamgram-server.git"
readonly UPSTREAM_COMMIT="8adf26bc071159c12a62c22ad49625a73e922e79"
readonly HERE="$(cd "$(dirname "$0")" && pwd)"
readonly TARGET="$(realpath -m "$1")"
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "Usage: bash deploy/teamgram/stage.sh /opt/haslgram/teamgram-server" >&2
  exit 2
fi
if [ -e "$TARGET" ]; then
  echo "Refusing to replace existing path: $TARGET" >&2
  exit 1
fi
mkdir -p "$(dirname "$TARGET")"
umask 077
git clone --no-checkout "$UPSTREAM" "$TARGET"
git -C "$TARGET" checkout --detach "$UPSTREAM_COMMIT"
python3 "$HERE/patch-auth.py" "$TARGET" "$HERE/overlays"
if command -v gofmt >/dev/null 2>&1; then
  gofmt -w "$TARGET/pkg/code/none/none_verify_code.go" \
           "$TARGET/pkg/code/send_sms_helper.go" \
           "$TARGET/pkg/code/haslgram/haslgram_verify_code.go" \
           "$TARGET/app/bff/authorization/internal/core/auth.sendCode_handler.go"
fi
echo "STAGED: $TARGET"
echo "IMPORTANT: DO NOT run upstream docker compose: default passwords,"
echo "exposed internal ports and upstream RSA key are unsafe."
echo "NEXT: configure isolated dependencies and private RSA keys before deployment."
