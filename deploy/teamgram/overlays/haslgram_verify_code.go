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

// HaslGram sends its OTP only through @HaslGramRegBot. Teamgram's own random
// phone code is never disclosed and is used only to describe the six-digit UI.
func (v *verifyCode) SendSmsVerifyCode(_ context.Context, phoneNumber, _, _ string) (string, error) {
    if !strings.HasPrefix(phoneNumber, "+") || len(phoneNumber) < 8 || len(phoneNumber) > 16 {
        return "", mtproto.ErrPhoneNumberInvalid
    }
    return phoneNumber, nil
}

func (v *verifyCode) VerifySmsCode(ctx context.Context, _, code, phoneNumber string) error {
    if len(code) != 6 || strings.Trim(code, "0123456789") != "" || !strings.HasPrefix(phoneNumber, "+") {
        return mtproto.ErrPhoneCodeInvalid
    }

    rawURL := strings.TrimSpace(os.Getenv("HASLGRAM_REGISTRATION_VERIFY_URL"))
    target, err := url.Parse(rawURL)
    if err != nil || target == nil || target.Host == "" {
        return mtproto.ErrPhoneCodeInvalid
    }
    // Permit HTTPS for a public endpoint. Plain HTTP is restricted to known
    // private Docker/local service names; never send OTPs over public HTTP.
    if target.Scheme != "https" && !(target.Scheme == "http" &&
        (target.Hostname() == "api" || target.Hostname() == "haslgram-gift-engine" ||
            target.Hostname() == "localhost" || target.Hostname() == "127.0.0.1")) {
        return mtproto.ErrPhoneCodeInvalid
    }

    phoneField := strings.TrimSpace(os.Getenv("HASLGRAM_REGISTRATION_PHONE_FIELD"))
    if phoneField == "" {
        phoneField = "phoneE164"
    }
    if phoneField != "phoneE164" && phoneField != "phoneNumber" {
        return mtproto.ErrPhoneCodeInvalid
    }

    payload := map[string]string{phoneField: phoneNumber, "code": code}
    body, err := json.Marshal(payload)
    if err != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    req, err := http.NewRequestWithContext(ctx, http.MethodPost, rawURL, bytes.NewReader(body))
    if err != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    req.Header.Set("Content-Type", "application/json")
    if token := strings.TrimSpace(os.Getenv("HASLGRAM_REGISTRATION_VERIFY_TOKEN")); token != "" {
        req.Header.Set("Authorization", "Bearer "+token)
    }

    res, err := v.httpClient.Do(req)
    if err != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    defer res.Body.Close()
    if res.StatusCode != http.StatusOK && res.StatusCode != http.StatusCreated {
        return mtproto.ErrPhoneCodeInvalid
    }
    successField := strings.TrimSpace(os.Getenv("HASLGRAM_REGISTRATION_SUCCESS_FIELD"))
    if successField == "" {
        successField = "success"
    }
    if successField != "success" && successField != "valid" &&
        successField != "verified" && successField != "ok" {
        return mtproto.ErrPhoneCodeInvalid
    }
    var result map[string]any
    if json.NewDecoder(io.LimitReader(res.Body, 4096)).Decode(&result) != nil {
        return mtproto.ErrPhoneCodeInvalid
    }
    verified, ok := result[successField].(bool)
    if !ok || !verified {
        return mtproto.ErrPhoneCodeInvalid
    }
    // The NestJS endpoint must atomically consume the one-time code and grant
    // the first-registration bonus once. Never log the OTP or response body.
    return nil
}
