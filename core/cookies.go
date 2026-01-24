package core

import (
	"encoding/json"
	"errors"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	http "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
)

type CookieRecord struct {
	Name   string `json:"name"`
	Value  string `json:"value"`
	Domain string `json:"domain,omitempty"`
	Path   string `json:"path,omitempty"`
}

func loadCookieFile(path string) ([]CookieRecord, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var list []CookieRecord
	if err := json.Unmarshal(data, &list); err == nil {
		return normalizeCookieRecords(list), nil
	}

	var dict map[string]string
	if err := json.Unmarshal(data, &dict); err != nil {
		return nil, err
	}
	list = make([]CookieRecord, 0, len(dict))
	for k, v := range dict {
		list = append(list, CookieRecord{
			Name:   k,
			Value:  v,
			Domain: ".91160.com",
			Path:   "/",
		})
	}
	return normalizeCookieRecords(list), nil
}

func saveCookieFile(path string, records []CookieRecord) error {
	records = normalizeCookieRecords(records)
	if len(records) == 0 {
		return errors.New("no cookies to save")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()

	encoder := json.NewEncoder(f)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	return encoder.Encode(records)
}

func normalizeCookieRecords(records []CookieRecord) []CookieRecord {
	unique := make(map[string]CookieRecord)
	for _, record := range records {
		if record.Name == "" {
			continue
		}
		if record.Domain == "" {
			record.Domain = ".91160.com"
		}
		if record.Path == "" {
			record.Path = "/"
		}
		key := strings.ToLower(record.Domain) + "|" + record.Path + "|" + record.Name
		unique[key] = record
	}
	out := make([]CookieRecord, 0, len(unique))
	for _, record := range unique {
		out = append(out, record)
	}
	return out
}

func setCookiesOnClient(client tls_client.HttpClient, records []CookieRecord) {
	grouped := make(map[string][]*http.Cookie)
	for _, record := range normalizeCookieRecords(records) {
		host := strings.TrimPrefix(record.Domain, ".")
		if host == "" {
			continue
		}
		grouped[host] = append(grouped[host], &http.Cookie{
			Name:   record.Name,
			Value:  record.Value,
			Domain: record.Domain,
			Path:   record.Path,
		})
	}
	for host, cookies := range grouped {
		u := &url.URL{Scheme: "https", Host: host}
		client.SetCookies(u, cookies)
	}
}

func cookiesFromJar(jar http.CookieJar) []CookieRecord {
	if jar == nil {
		return nil
	}
	if typed, ok := jar.(tls_client.CookieJar); ok {
		all := typed.GetAllCookies()
		records := make([]CookieRecord, 0)
		for _, cookies := range all {
			for _, c := range cookies {
				records = append(records, CookieRecord{
					Name:   c.Name,
					Value:  c.Value,
					Domain: c.Domain,
					Path:   c.Path,
				})
			}
		}
		return normalizeCookieRecords(records)
	}

	records := make([]CookieRecord, 0)
	for _, host := range []string{
		"https://www.91160.com",
		"https://user.91160.com",
		"https://open.weixin.qq.com",
		"https://lp.open.weixin.qq.com",
	} {
		u, err := url.Parse(host)
		if err != nil {
			continue
		}
		for _, c := range jar.Cookies(u) {
			records = append(records, CookieRecord{
				Name:   c.Name,
				Value:  c.Value,
				Domain: c.Domain,
				Path:   c.Path,
			})
		}
	}
	return normalizeCookieRecords(records)
}
