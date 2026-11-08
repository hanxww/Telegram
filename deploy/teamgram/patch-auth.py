#!/usr/bin/env python3
"""Apply fail-closed HaslGram bot OTP and app-credential checks to pinned Teamgram."""
from pathlib import Path
import re
import shutil
import sys

if len(sys.argv) != 3:
    sys.exit("Usage: patch-auth.py TEAMGRAM_SERVER_DIR OVERLAYS_DIR")
root, overlays = (Path(p).resolve() for p in sys.argv[1:3])

paths = {
    "helper": root / "pkg/code/send_sms_helper.go",
    "none": root / "pkg/code/none/none_verify_code.go",
    "auth_send": root / "app/bff/authorization/internal/core/auth.sendCode_handler.go",
    "auth_resend": root / "app/bff/authorization/internal/core/auth.resendCode_handler.go",
    "auth_signup": root / "app/bff/authorization/internal/core/auth.signUp_handler.go",
    "api": root / "app/bff/authorization/internal/dao/api.go",
    "phone_code": root / "app/bff/authorization/internal/dao/phone_code.go",
    "runall": root / "teamgramd/bin/runall-docker.sh",
    "bff_config": root / "teamgramd/etc2/bff.yaml",
}
for name, path in paths.items():
    if not path.is_file():
        sys.exit(f"FAIL CLOSED: missing expected upstream file {name}: {path}")
provider_source = overlays / "haslgram_verify_code.go"
if not provider_source.is_file():
    sys.exit("FAIL CLOSED: missing HaslGram Go provider")

def replace_once(src: str, before: str, after: str, desc: str) -> str:
    count = src.count(before)
    if count != 1:
        sys.exit(f"FAIL CLOSED: {desc} expected exactly one match, got {count}")
    return src.replace(before, after, 1)

helper = paths["helper"].read_text()
helper = replace_once(
    helper,
    '"github.com/teamgram/teamgram-server/pkg/code/conf"',
    '"github.com/teamgram/teamgram-server/pkg/code/conf"\n\t"github.com/teamgram/teamgram-server/pkg/code/haslgram"',
    "register HaslGram provider import",
)
helper = replace_once(
    helper, '\tcase "none":',
    '\tcase "haslgram":\n\t\treturn haslgram.New(c)\n\tcase "none":',
    "register HaslGram provider factory",
)

none = paths["none"].read_text()
none, count = re.subn(
    r'func \(m \*noneVerifyCode\) VerifySmsCode\(ctx context.Context, codeHash, code, extraData string\) error \{.*?\n\}',
    '''func (m *noneVerifyCode) VerifySmsCode(ctx context.Context, codeHash, code, extraData string) error {
    // Unsafe upstream test provider is disabled in HaslGram.
    return mtproto.ErrPhoneCodeInvalid
}''',
    none, count=1, flags=re.S,
)
if count != 1:
    sys.exit(f"FAIL CLOSED: could not disable upstream test-code verifier ({count})")

phone_code = paths["phone_code"].read_text()
phone_code = replace_once(
    phone_code, "PhoneCode:             random2.RandomNumeric(5),",
    "PhoneCode:             random2.RandomNumeric(6),",
    "set six-digit challenge UI length",
)

send_code = paths["auth_send"].read_text()
anchor = send_code.find("DoAuthSendCode(c.ctx,")
if anchor < 0:
    sys.exit("FAIL CLOSED: DoAuthSendCode call not found")
start = send_code.find("\n\t\tfunc(codeData2 *model.PhoneCodeTransaction) error {", anchor)
end = send_code.find("\n\t\t})", start)
if start < 0 or end < 0:
    sys.exit("FAIL CLOSED: auth.sendCode callback boundaries not found")
callback = """
\t\tfunc(codeData2 *model.PhoneCodeTransaction) error {
\t\t\tphoneData, sendErr := c.svcCtx.AuthLogic.VerifyCodeInterface.SendSmsVerifyCode(
\t\t\t\tc.ctx, phoneNumber, codeData2.PhoneCode, codeData2.PhoneCodeHash)
\t\t\tif sendErr != nil {
\t\t\t\treturn sendErr
\t\t\t}
\t\t\tcodeData2.SentCodeType = model.SentCodeTypeSms
\t\t\tcodeData2.PhoneCodeExtraData = phoneData
\t\t\tcodeData2.NextCodeType = model.CodeTypeNone
\t\t\tcodeData2.State = model.CodeStateSent
\t\t\tcodeData2.PhoneNumberRegistered = phoneRegistered
\t\t\treturn nil
\t\t}"""
send_code = send_code[:start] + callback + send_code[end + len("\n\t\t}"):]
send_code = replace_once(
    send_code,
    'c.Logger.Errorf("invalid api: {api_id: %d, api_hash: %s}", request.ApiId, request.ApiHash)',
    'c.Logger.Errorf("invalid HaslGram application credentials for api_id: %d", request.ApiId)',
    "redact API hash from auth logs",
)
for import_line, symbol in [
    ('"github.com/teamgram/marmota/pkg/threading2"', "threading2."),
    ('statuspb "github.com/teamgram/teamgram-server/app/service/status/status"', "statuspb."),
    ('"context"', "context."),
]:
    if symbol not in send_code:
        send_code = send_code.replace("\n\t" + import_line, "")
if 'PhoneCode = "12345"' in send_code or 'PhoneCodeExtraData = "12345"' in send_code:
    sys.exit("FAIL CLOSED: fixed test login code remains in auth.sendCode")

resend = paths["auth_resend"].read_text()
resend_start = resend.find("func (c *AuthorizationCore) AuthResendCode(")
if resend_start < 0:
    sys.exit("FAIL CLOSED: AuthResendCode function not found")
resend = resend[:resend_start] + """func (c *AuthorizationCore) AuthResendCode(in *mtproto.TLAuthResendCode) (*mtproto.Auth_SentCode, error) {
    return nil, mtproto.ErrPhoneCodeExpired
}
"""
resend = replace_once(
    resend,
    '\t"github.com/teamgram/teamgram-server/app/bff/authorization/internal/logic"\n\t"github.com/teamgram/teamgram-server/app/bff/authorization/model"\n',
    "",
    "remove unused resend imports",
)

signup = paths["auth_signup"].read_text()
signup = replace_once(
    signup,
    '\t\t\tc.pushSignInMessage(ctx, user.Id(), codeData.PhoneCode)',
    '\t\t\t// HaslGram OTP was verified by the registration bot; never expose the internal placeholder.',
    "remove placeholder login-code notification",
)

api = paths["api"].read_text()
api = replace_once(
    api,
    '''import (
\t"net"

\t"github.com/zeromicro/go-zero/core/logx"
)''',
    '''import (
\t"crypto/subtle"
\t"encoding/hex"
\t"net"
\t"os"
\t"strconv"
\t"strings"

\t"github.com/teamgram/proto/mtproto"
\t"github.com/zeromicro/go-zero/core/logx"
)''',
    "add strict API credential validation imports",
)
api, count = re.subn(
    r'func \(d \*Dao\) CheckApiIdAndHash\(apiId int32, apiHash string\) error \{.*?\n\}',
    '''func (d *Dao) CheckApiIdAndHash(apiId int32, apiHash string) error {
    expectedID, err := strconv.ParseInt(strings.TrimSpace(os.Getenv("HASLGRAM_API_ID")), 10, 32)
    expectedHash := strings.ToLower(strings.TrimSpace(os.Getenv("HASLGRAM_API_HASH")))
    providedHash := strings.ToLower(strings.TrimSpace(apiHash))
    if err != nil || expectedID <= 0 || len(expectedHash) != 32 ||
        len(providedHash) != 32 || apiId != int32(expectedID) {
        return mtproto.ErrApiIdInvalid
    }
    if _, err := hex.DecodeString(expectedHash); err != nil {
        return mtproto.ErrApiIdInvalid
    }
    if subtle.ConstantTimeCompare([]byte(providedHash), []byte(expectedHash)) != 1 {
        return mtproto.ErrApiIdInvalid
    }
    return nil
}''',
    api, count=1, flags=re.S,
)
if count != 1:
    sys.exit(f"FAIL CLOSED: strict API ID/hash function replacement failed ({count})")

runall = paths["runall"].read_text()
dollar = chr(36)
guard = '''#!/usr/bin/env bash
set -euo pipefail

: "''' + dollar + '''{HASLGRAM_API_ID:?Set HASLGRAM_API_ID in the private BFF container environment}"
: "''' + dollar + '''{HASLGRAM_API_HASH:?Set HASLGRAM_API_HASH in the private BFF container environment}"
: "''' + dollar + '''{HASLGRAM_REGISTRATION_VERIFY_URL:?Set HASLGRAM_REGISTRATION_VERIFY_URL to the private NestJS verification endpoint}"
[[ "$HASLGRAM_API_ID" =~ ^[1-9][0-9]*$ ]] || { echo "Invalid HASLGRAM_API_ID" >&2; exit 1; }
[[ "$HASLGRAM_API_HASH" =~ ^[A-Fa-f0-9]{32}$ ]] || { echo "Invalid HASLGRAM_API_HASH" >&2; exit 1; }

'''
runall = replace_once(runall, "#!/usr/bin/env bash\n", guard, "add startup credential guard")
config = paths["bff_config"].read_text()
config = replace_once(config, 'Name: "none"', 'Name: "haslgram"', "select HaslGram provider")

# Write only after every upstream source pattern has been validated.
paths["helper"].write_text(helper)
paths["none"].write_text(none)
paths["phone_code"].write_text(phone_code)
paths["auth_send"].write_text(send_code)
paths["auth_resend"].write_text(resend)
paths["auth_signup"].write_text(signup)
paths["api"].write_text(api)
paths["runall"].write_text(runall)
paths["bff_config"].write_text(config)
destination = root / "pkg/code/haslgram/haslgram_verify_code.go"
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(provider_source, destination)
print("HaslGram auth, six-digit OTP, API credential checks staged. No services started.")
