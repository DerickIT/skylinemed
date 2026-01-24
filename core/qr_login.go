package core

import (
	"bytes"
	"context"
	"fmt"
	"net/url"
	"path/filepath"
	"regexp"
	"time"

	http "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
)

type FastQRLogin struct {
	uuid   string
	state  string
	client tls_client.HttpClient
}

const (
	wechatAppID     = "wxdfec0615563d691d"
	wechatRedirect  = "http://user.91160.com/supplier-wechat.html"
	qrConnectOrigin = "https://open.weixin.qq.com/"
)

func NewFastQRLogin() (*FastQRLogin, error) {
	client, err := newTLSClient()
	if err != nil {
		return nil, err
	}
	return &FastQRLogin{client: client}, nil
}

func (l *FastQRLogin) GetQRImage() ([]byte, string, error) {
	l.state = fmt.Sprintf("login_%d", time.Now().Unix())
	encodedRedirect := url.QueryEscape(wechatRedirect)
	targetURL := fmt.Sprintf(
		"https://open.weixin.qq.com/connect/qrconnect?appid=%s&redirect_uri=%s&response_type=code&scope=snsapi_login&state=%s#wechat_redirect",
		wechatAppID,
		encodedRedirect,
		l.state,
	)

	req, err := http.NewRequest(http.MethodGet, targetURL, nil)
	if err != nil {
		return nil, "", err
	}
	setWeChatHeaders(req)
	resp, err := l.client.Do(req)
	if err != nil {
		return nil, "", err
	}
	body, err := readResponseBody(resp)
	if err != nil {
		return nil, "", err
	}

	re := regexp.MustCompile(`/connect/qrcode/([a-zA-Z0-9_-]+)`)
	match := re.FindSubmatch(body)
	if len(match) < 2 {
		return nil, "", fmt.Errorf("qr uuid not found")
	}
	l.uuid = string(match[1])

	qrURL := fmt.Sprintf("https://open.weixin.qq.com/connect/qrcode/%s", l.uuid)
	qrReq, err := http.NewRequest(http.MethodGet, qrURL, nil)
	if err != nil {
		return nil, "", err
	}
	setWeChatHeaders(qrReq)
	qrResp, err := l.client.Do(qrReq)
	if err != nil {
		return nil, "", err
	}
	qrBytes, err := readResponseBody(qrResp)
	if err != nil {
		return nil, "", err
	}
	if len(qrBytes) < 4 || (!bytes.HasPrefix(qrBytes, []byte{0xFF, 0xD8}) && !bytes.HasPrefix(qrBytes, []byte{0x89, 0x50, 0x4E, 0x47})) {
		return nil, "", fmt.Errorf("qr image invalid")
	}
	return qrBytes, l.uuid, nil
}

func (l *FastQRLogin) PollStatus(ctx context.Context, timeout time.Duration, onStatus func(string)) QRLoginResult {
	if l.uuid == "" {
		return QRLoginResult{Success: false, Message: "uuid not initialized"}
	}
	if ctx == nil {
		ctx = context.Background()
	}
	if timeout <= 0 {
		timeout = 5 * time.Minute
	}

	start := time.Now()
	lastStatus := ""
	lastParam := "404"
	retry404 := 0

	reErrcode := regexp.MustCompile(`wx_errcode\s*=\s*(\d+)`)
	reCode := regexp.MustCompile(`wx_code\s*=\s*['"]([^'"]*)['"]`)
	reRedirect := regexp.MustCompile(`window\.location(?:\.href|\.replace)?\s*\(?['"]([^'"]+)['"]\)?`)

	for {
		if ctx.Err() != nil {
			return QRLoginResult{Success: false, Message: "canceled"}
		}
		if time.Since(start) > timeout {
			return QRLoginResult{Success: false, Message: "qr expired"}
		}

		ts := time.Now().UnixMilli()
		pollURL := fmt.Sprintf("https://lp.open.weixin.qq.com/connect/l/qrconnect?uuid=%s&last=%s&_=%d", l.uuid, lastParam, ts)
		req, err := http.NewRequest(http.MethodGet, pollURL, nil)
		if err != nil {
			time.Sleep(1 * time.Second)
			continue
		}
		setWeChatHeaders(req)
		resp, err := l.client.Do(req)
		if err != nil {
			time.Sleep(2 * time.Second)
			continue
		}
		body, err := readResponseBody(resp)
		if err != nil {
			time.Sleep(1 * time.Second)
			continue
		}

		text := string(body)
		status := "0"
		if match := reErrcode.FindStringSubmatch(text); len(match) > 1 {
			status = match[1]
		}
		code := ""
		if match := reCode.FindStringSubmatch(text); len(match) > 1 {
			code = match[1]
		}
		redirectURL := ""
		if match := reRedirect.FindStringSubmatch(text); len(match) > 1 {
			redirectURL = match[1]
		}
		if status == "0" && (code != "" || redirectURL != "") {
			status = "405"
		}
		if status == "408" || status == "201" || status == "405" || status == "402" || status == "404" {
			lastParam = status
		}

		switch status {
		case "408":
			if lastStatus != "408" && onStatus != nil {
				onStatus("waiting for scan")
			}
			lastStatus = "408"
			retry404 = 0
		case "404", "402":
			retry404++
			lastStatus = "404"
			if retry404 > 60 {
				return QRLoginResult{Success: false, Message: "qr expired"}
			}
			time.Sleep(1 * time.Second)
			continue
		case "201":
			if lastStatus != "201" && onStatus != nil {
				onStatus("scanned, confirm on phone")
			}
			lastStatus = "201"
			retry404 = 0
		case "405":
			if code == "" && redirectURL != "" {
				parsed, err := url.Parse(redirectURL)
				if err == nil {
					if state := parsed.Query().Get("state"); state != "" {
						l.state = state
					}
					code = parsed.Query().Get("code")
				}
			}
			if code == "" {
				if onStatus != nil {
					onStatus("confirmed but no code, retrying")
				}
				time.Sleep(1 * time.Second)
				continue
			}
			if onStatus != nil {
				onStatus("logging in")
			}
			return l.exchangeCookie(code)
		}

		time.Sleep(1 * time.Second)
	}
}

func (l *FastQRLogin) exchangeCookie(code string) QRLoginResult {
	client, err := newTLSClient()
	if err != nil {
		return QRLoginResult{Success: false, Message: err.Error()}
	}
	client.SetCookieJar(tls_client.NewCookieJar())

	callbackURL := fmt.Sprintf("%s?code=%s", wechatRedirect, code)
	if l.state != "" {
		callbackURL = fmt.Sprintf("%s?code=%s&state=%s", wechatRedirect, code, url.QueryEscape(l.state))
	}

	req, err := http.NewRequest(http.MethodGet, callbackURL, nil)
	if err != nil {
		return QRLoginResult{Success: false, Message: err.Error()}
	}
	req.Header.Set("User-Agent", defaultUserAgent)
	req.Header.Set("Referer", qrConnectOrigin)
	if _, err := client.Do(req); err != nil {
		return QRLoginResult{Success: false, Message: err.Error()}
	}

	homeReq, _ := http.NewRequest(http.MethodGet, "https://www.91160.com/", nil)
	homeReq.Header.Set("User-Agent", defaultUserAgent)
	_, _ = client.Do(homeReq)

	indexReq, _ := http.NewRequest(http.MethodGet, "https://user.91160.com/user/index.html", nil)
	indexReq.Header.Set("User-Agent", defaultUserAgent)
	_, _ = client.Do(indexReq)

	records := cookiesFromJar(client.GetCookieJar())
	if len(records) == 0 {
		return QRLoginResult{Success: false, Message: "no cookies received"}
	}
	hasAccess := false
	for _, record := range records {
		if record.Name == "access_hash" {
			hasAccess = true
			break
		}
	}
	if !hasAccess {
		return QRLoginResult{Success: false, Message: "missing access_hash"}
	}

	configDir, err := resolveConfigDir()
	if err != nil {
		return QRLoginResult{Success: false, Message: err.Error()}
	}
	cookiePath := filepath.Join(configDir, "cookies.json")
	if err := saveCookieFile(cookiePath, records); err != nil {
		return QRLoginResult{Success: false, Message: err.Error()}
	}
	return QRLoginResult{Success: true, Message: "login ok", CookiePath: cookiePath}
}

func setWeChatHeaders(req *http.Request) {
	req.Header.Set("User-Agent", defaultUserAgent)
	req.Header.Set("Referer", qrConnectOrigin)
	req.Header.Set("Origin", "https://open.weixin.qq.com")
	req.Header.Set("Accept", "*/*")
	req.Header.Set("Connection", "keep-alive")
}
