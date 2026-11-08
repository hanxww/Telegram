// HaslGram bot-only MTProto login bridge. Apache-2.0 licensed code.
package haslgram

import (
    "bytes"
    "context"
    "encoding/json"
    "io"
    "net/http"
    "net/url"
    "os"
    "strings"
    "time"

    "github.com/teamgram/proto/mtproto"
    "github.com/teamgram/teamgram-server/pkg/code/conf"
)

type verifyCode struct {
    httpClient *http.Client
}

// New creates the verification provider used by Teamgram auth.sendCode/auth.signIn.
func New(_ *conf.SmsVerifyCodeConfig) *verifyCode {
    return &verifyCode{httpClient: &http.Client{Timeout: 8 * time.Second}}
}

// The code is sent ONLY by @HaslGramRegBot after the user shares their own contact.
// Returning the phone attaches it to this MTProto challenge; never disclose the
// random Teamgram-generated code as a fallback.
func (v *verifyCode) SendSmsVerifyCode(_ context.Context, phoneNumber, _, _ string) (string, error) {
    if strings.TrimSpace(phoneNumber) == "" {
        return "", mtproto.ErrPhoneNumberInvalid
    }
    return phoneNumber, nil
}

func (v *verifyCode) VerifySmsCode(ctx context.Context, _, code, phoneNumber string) error {
    if len(code) != 6 || strings.Trim(code, "0123456789") != "" || strings.TrimSpace(phoneNumber) == "" {
        return mtproto.ErrPhoneCodeInvalid
    }
    rawURL := os.Getenv("HASLGRAM_REGISTRATION_VERIFY_URL")
    target, err := url.Parse(rawURL)
    if err != nil || target == nil || target.Host == "" {
        return mtproto.ErrPhoneCodeInvalid
    }
    // Only allow plain HTTP to the API inside our isolated Docker network.
    if target.Scheme != "https" && !(target.Scheme == "http" && (target.Hostname() == "api" || target.Hostname() == "127.0.0.1" || target.Hostname() == "localhost")) {
        return mtproto.ErrPhoneCodeInvalid
    }
    payload, err := json.Marshal(struct {
        PhoneE164 string `json:"phoneE164"`
        Code      string `json:"code"`
    }{PhoneE164: phoneNumber, Code: code})
    if err != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    req, err := http.NewRequestWithContext(ctx, http.MethodPost, rawURL, bytes.NewReader(payload))
    if err != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    req.Header.Set("Content-Type", "application/json")
    res, err := v.httpClient.Do(req)
    if err != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    defer res.Body.Close()
    _, _ = io.Copy(io.Discard, io.LimitReader(res.Body, 4096))
    if res.StatusCode != http.StatusCreated && res.StatusCode != http.StatusOK {
        return mtproto.ErrPhoneCodeInvalid
    }
    // Successful verification consumes the one-time HaslGram code, granting
    // initial Stars only once in the existing NestJS registration transaction.
    // We intentionally do not log or persist the code, JWT or response body.
    return nil
}
