#!/usr/bin/env python3
"""Apply fail-closed HaslGram bot-code authentication to a pinned Teamgram checkout.

This modifies a STAGED checkout, not the live NestJS server.
Upstream source patterns are asserted so a change fails instead of silently
reintroducing Teamgram's insecure '12345' login.
"""
from pathlib import Path
import re
import shutil
import sys

if len(sys.argv) != 3:
    sys.exit("Usage: patch-auth.py TEAMGRAM_SERVER_DIR OVERLAYS_DIR")

root, overlays = (Path(p).resolve() for p in sys.argv[1:3])
files = [
    root / "pkg/code/send_sms_helper.go",
    root / "pkg/code/none/none_verify_code.go",
    root / "app/bff/authorization/internal/core/auth.sendCode_handler.go",
    root / "teamgramd/etc2/bff.yaml",
]
for file in files:
    if not file.is_file():
        sys.exit(f"Missing expected upstream file: {file}")
if not (overlays / "haslgram_verify_code.go").is_file():
    sys.exit("Missing HaslGram Go provider")

def replace_once(src: str, before: str, after: str, desc: str) -> str:
    occurrences = src.count(before)
    if occurrences != 1:
        sys.exit(f"FAIL CLOSED: {desc} expected 1 match, got {occurrences}")
    return src.replace(before, after, 1)

helper = files[0].read_text()
helper = replace_once(
    helper,
    '"github.com/teamgram/teamgram-server/pkg/code/conf"',
    '"github.com/teamgram/teamgram-server/pkg/code/conf"\n\t"github.com/teamgram/teamgram-server/pkg/code/haslgram"',
    "register provider import",
)
helper = replace_once(
    helper, '\tcase "none":',
    '\tcase "haslgram":\n\t\treturn haslgram.New(c)\n\tcase "none":',
    "register provider name",
)

none = files[1].read_text()
pattern = (r'func \(m \*noneVerifyCode\) VerifySmsCode\(ctx context.Context, '
           r'codeHash, code, extraData string\) error \{\s*'
           r'if code != "12345" \{\s*return mtproto.ErrPhoneCodeInvalid\s*\}'
           r'\s*return nil\s*\}')
none, number = re.subn(pattern, """func (m *noneVerifyCode) VerifySmsCode(ctx context.Context, codeHash, code, extraData string) error {
    // Unsafe test provider deliberately disabled in HaslGram.
    return mtproto.ErrPhoneCodeInvalid
}""", none)
if number != 1:
    sys.exit(f"FAIL CLOSED: test code verifier expected 1 match, got {number}")

send_code = files[2].read_text()
anchor = send_code.find("DoAuthSendCode(c.ctx,")
if anchor < 0:
    sys.exit("FAIL CLOSED: DoAuthSendCode call not found")
start = send_code.find("\n\t\tfunc(codeData2 *model.PhoneCodeTransaction) error {", anchor)
end = send_code.find("\n\t\t})", start)
if start < 0 or end < 0:
    sys.exit("FAIL CLOSED: send-code callback boundaries not found")
callback = """
        func(codeData2 *model.PhoneCodeTransaction) error {
            // All registrations and new sessions require the bot code.
            // Never send an alternate fixed SMS, in-app or test-user code.
            phoneData, sendErr := c.svcCtx.AuthLogic.VerifyCodeInterface.SendSmsVerifyCode(
                c.ctx, phoneNumber, codeData2.PhoneCode, codeData2.PhoneCodeHash)
            if sendErr != nil {
                return sendErr
            }
            codeData2.SentCodeType = model.SentCodeTypeSms
            codeData2.PhoneCodeExtraData = phoneData
            codeData2.NextCodeType = model.CodeTypeSms
            codeData2.State = model.CodeStateSent
            codeData2.PhoneNumberRegistered = phoneRegistered
            return nil
        }"""
send_code = send_code[:start] + "\n\t" + callback.strip("\n").replace("\n", "\n\t") + send_code[end + len("\n\t\t}"):]
# The closing parenthesis of the DoAuthSendCode call is preserved by the splice.
for imported in ["github.com/teamgram/marmota/pkg/threading2", "statuspb \"github.com/teamgram/teamgram-server/app/service/status/status\"", '"context"']:
    symbol = "threading2." if "threading2" in imported else ("statuspb." if "statuspb" in imported else "context.")
    if symbol not in send_code:
        send_code = send_code.replace("\n\t" + imported, "")
if 'PhoneCode = "12345"' in send_code:
    sys.exit("FAIL CLOSED: fixed test code still present in auth.sendCode")
config = files[3].read_text()
config = replace_once(config, 'Name: "none"', 'Name: "haslgram"', "select bot-only provider")

# Write only after all source structure checks pass.
files[0].write_text(helper)
files[1].write_text(none)
files[2].write_text(send_code)
files[3].write_text(config)
destination = root / "pkg/code/haslgram/haslgram_verify_code.go"
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(overlays / "haslgram_verify_code.go", destination)
print("HaslGram bot-only verifier staged. No services started or ports exposed.")
