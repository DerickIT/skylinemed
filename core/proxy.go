package core

import (
	"encoding/json"
	"errors"
	"fmt"
	"math/rand"
	nethttp "net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

const (
	proxyAPIURL               = "https://proxy.scdn.io/api/get_proxy.php"
	proxyProbeURL             = "https://www.91160.com/favicon.ico"
	defaultProxyProtocol      = "https"
	defaultProxyCountry       = "CN"
	defaultProxyFetchCount    = 6
	proxyAPITimeout           = 12 * time.Second
	proxyProbeTimeout         = 6 * time.Second
	proxyAPIRetryMax          = 3
	proxyAPIRetryBackoffMinMs = 400
	proxyAPIRetryBackoffMaxMs = 900
)

type proxyAPIResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    struct {
		Proxies []string `json:"proxies"`
		Count   int      `json:"count"`
	} `json:"data"`
}

func (c *HealthClient) RotateProxy(protocol, country string) (string, error) {
	if c == nil {
		return "", errors.New("client is nil")
	}
	protocols, err := resolveProxyProtocols(protocol)
	if err != nil {
		return "", err
	}
	normalizedCountry := normalizeProxyCountry(country)

	c.proxyMu.Lock()
	defer c.proxyMu.Unlock()

	errorNotes := make([]string, 0, len(protocols))

	for _, normalizedProtocol := range protocols {
		if normalizedProtocol != c.proxyProtocol || normalizedCountry != c.proxyCountry || len(c.proxyPool) == 0 {
			list, err := fetchProxyList(normalizedProtocol, normalizedCountry, defaultProxyFetchCount)
			if err != nil {
				errorNotes = append(errorNotes, fmt.Sprintf("%s: %v", normalizedProtocol, err))
				continue
			}
			c.proxyPool = list
			c.proxyProtocol = normalizedProtocol
			c.proxyCountry = normalizedCountry
		}

		var lastErr error
		for len(c.proxyPool) > 0 {
			proxyHost := strings.TrimSpace(c.proxyPool[0])
			c.proxyPool = c.proxyPool[1:]
			if proxyHost == "" {
				continue
			}
			proxyURL := buildProxyURL(normalizedProtocol, proxyHost)
			if proxyURL == "" {
				continue
			}
			if err := testProxyConnectivity(proxyURL); err != nil {
				lastErr = err
				continue
			}
			if err := c.client.SetProxy(proxyURL); err != nil {
				lastErr = err
				continue
			}
			return proxyURL, nil
		}
		if lastErr == nil {
			lastErr = errors.New("no proxy available")
		}
		errorNotes = append(errorNotes, fmt.Sprintf("%s: %v", normalizedProtocol, lastErr))
	}

	if len(errorNotes) == 0 {
		return "", errors.New("no proxy available")
	}
	return "", errors.New(strings.Join(errorNotes, "; "))
}

func (c *HealthClient) ClearProxy() error {
	if c == nil {
		return errors.New("client is nil")
	}
	c.mu.Lock()
	defer c.mu.Unlock()

	newClient, err := newTLSClient()
	if err != nil {
		return err
	}
	if c.client != nil {
		records := cookiesFromJar(c.client.GetCookieJar())
		if len(records) > 0 {
			setCookiesOnClient(newClient, records)
		}
	}
	c.client = newClient
	return nil
}

func fetchProxyList(protocol, country string, count int) ([]string, error) {
	if count <= 0 {
		count = defaultProxyFetchCount
	}
	protocol = strings.ToLower(strings.TrimSpace(protocol))
	if protocol == "" {
		protocol = defaultProxyProtocol
	}
	country = normalizeProxyCountry(country)

	var lastErr error
	maxRetry := proxyAPIRetryMax
	if maxRetry <= 0 {
		maxRetry = 1
	}

	for attempt := 1; attempt <= maxRetry; attempt++ {
		list, err := fetchProxyListOnce(protocol, country, count)
		if err == nil && len(list) > 0 {
			return list, nil
		}
		if err == nil {
			err = errors.New("proxy list is empty")
		}
		lastErr = err
		if attempt < maxRetry {
			backoff := time.Duration(randomBackoffMsProxy(proxyAPIRetryBackoffMinMs, proxyAPIRetryBackoffMaxMs)) * time.Millisecond
			time.Sleep(backoff)
		}
	}
	return nil, lastErr
}

func fetchProxyListOnce(protocol, country string, count int) ([]string, error) {
	params := url.Values{}
	params.Set("protocol", protocol)
	params.Set("count", strconv.Itoa(count))
	if country != "" {
		params.Set("country_code", strings.ToUpper(strings.TrimSpace(country)))
	}
	targetURL := proxyAPIURL + "?" + params.Encode()

	client := &nethttp.Client{Timeout: proxyAPITimeout}
	req, err := nethttp.NewRequest(nethttp.MethodGet, targetURL, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != nethttp.StatusOK {
		return nil, fmt.Errorf("proxy api http %d", resp.StatusCode)
	}

	var payload proxyAPIResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	if payload.Code != 200 {
		msg := strings.TrimSpace(payload.Message)
		if msg == "" {
			msg = "proxy api error"
		}
		return nil, errors.New(msg)
	}

	unique := make(map[string]struct{})
	out := make([]string, 0, len(payload.Data.Proxies))
	for _, item := range payload.Data.Proxies {
		host := strings.TrimSpace(item)
		if host == "" {
			continue
		}
		if _, ok := unique[host]; ok {
			continue
		}
		unique[host] = struct{}{}
		out = append(out, host)
	}
	if len(out) == 0 {
		return nil, errors.New("proxy list is empty")
	}
	return out, nil
}

func resolveProxyProtocols(protocol string) ([]string, error) {
	normalized := strings.ToLower(strings.TrimSpace(protocol))
	if normalized == "" || normalized == "all" {
		return []string{"https", "http", "socks5"}, nil
	}
	switch normalized {
	case "http", "https", "socks5":
		return []string{normalized}, nil
	case "socks4":
		return nil, errors.New("socks4 is not supported")
	default:
		return nil, fmt.Errorf("unsupported proxy protocol: %s", normalized)
	}
}

func normalizeProxyCountry(country string) string {
	normalized := strings.ToUpper(strings.TrimSpace(country))
	if normalized == "CN" {
		return normalized
	}
	return defaultProxyCountry
}

func buildProxyURL(protocol, host string) string {
	host = strings.TrimSpace(host)
	if host == "" {
		return ""
	}
	if strings.Contains(host, "://") {
		return host
	}
	return fmt.Sprintf("%s://%s", protocol, host)
}

func testProxyConnectivity(proxyURL string) error {
	client, err := newProxyTestClient()
	if err != nil {
		return err
	}
	defer client.CloseIdleConnections()

	if err := client.SetProxy(proxyURL); err != nil {
		return err
	}
	resp, err := client.Get(proxyProbeURL)
	if resp != nil && resp.Body != nil {
		_ = resp.Body.Close()
	}
	if err != nil {
		return err
	}
	if resp == nil {
		return errors.New("proxy probe empty response")
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 400 {
		return fmt.Errorf("proxy probe http %d", resp.StatusCode)
	}
	return nil
}

func newProxyTestClient() (tls_client.HttpClient, error) {
	jar := tls_client.NewCookieJar()
	options := []tls_client.HttpClientOption{
		tls_client.WithClientProfile(profiles.Chrome_120),
		tls_client.WithRandomTLSExtensionOrder(),
		tls_client.WithCookieJar(jar),
		tls_client.WithDefaultHeaders(defaultHeaders()),
		tls_client.WithTimeoutSeconds(int(proxyProbeTimeout.Seconds())),
	}
	client, err := tls_client.NewHttpClient(tls_client.NewNoopLogger(), options...)
	if err != nil {
		return nil, err
	}
	client.SetFollowRedirect(true)
	return client, nil
}

func randomBackoffMsProxy(minMs, maxMs int) int {
	if minMs <= 0 && maxMs <= 0 {
		return 0
	}
	if maxMs < minMs {
		maxMs = minMs
	}
	if maxMs == minMs {
		return maxMs
	}
	return minMs + rand.Intn(maxMs-minMs+1)
}
