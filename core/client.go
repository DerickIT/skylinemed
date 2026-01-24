package core

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/PuerkitoBio/goquery"
	http "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

const defaultUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

type HealthClient struct {
	client         tls_client.HttpClient
	headers        http.Header
	configDir      string
	cookieFilePath string
	lastError      string
	lastStatusCode int
	stateMu        sync.RWMutex
	mu             sync.Mutex
	proxyMu        sync.Mutex
	proxyPool      []string
	proxyProtocol  string
	proxyCountry   string
}

func NewHealthClient() (*HealthClient, error) {
	configDir, err := resolveConfigDir()
	if err != nil {
		return nil, err
	}
	jar := tls_client.NewCookieJar()
	options := []tls_client.HttpClientOption{
		tls_client.WithClientProfile(profiles.Chrome_120),
		tls_client.WithRandomTLSExtensionOrder(),
		tls_client.WithCookieJar(jar),
		tls_client.WithDefaultHeaders(defaultHeaders()),
	}
	client, err := tls_client.NewHttpClient(tls_client.NewNoopLogger(), options...)
	if err != nil {
		return nil, err
	}
	client.SetFollowRedirect(true)

	return &HealthClient{
		client:         client,
		headers:        defaultHeaders(),
		configDir:      configDir,
		cookieFilePath: filepath.Join(configDir, "cookies.json"),
	}, nil
}

func (c *HealthClient) LastError() string {
	c.stateMu.RLock()
	defer c.stateMu.RUnlock()
	return c.lastError
}

func (c *HealthClient) LastStatusCode() int {
	c.stateMu.RLock()
	defer c.stateMu.RUnlock()
	return c.lastStatusCode
}

func (c *HealthClient) setLastError(message string) {
	c.stateMu.Lock()
	c.lastError = message
	c.stateMu.Unlock()
}

func (c *HealthClient) setLastStatusCode(code int) {
	c.stateMu.Lock()
	c.lastStatusCode = code
	c.stateMu.Unlock()
}

func (c *HealthClient) LoadCookies() bool {
	if _, err := os.Stat(c.cookieFilePath); err != nil {
		return false
	}
	records, err := loadCookieFile(c.cookieFilePath)
	if err != nil {
		return false
	}
	setCookiesOnClient(c.client, records)
	return true
}

func (c *HealthClient) EnsureCookiesLoaded() bool {
	if c == nil {
		return false
	}
	if c.HasAccessHash() {
		return true
	}
	return c.LoadCookies()
}

func (c *HealthClient) SaveCookiesFromRecords(records []CookieRecord) error {
	if len(records) == 0 {
		return errors.New("no cookies to save")
	}
	if err := saveCookieFile(c.cookieFilePath, records); err != nil {
		return err
	}
	setCookiesOnClient(c.client, records)
	return nil
}

func (c *HealthClient) CheckLogin() bool {
	if len(c.cookieValues("access_hash")) == 0 {
		return false
	}

	req, err := c.newRequest(http.MethodGet, "https://user.91160.com/user/index.html", nil, nil)
	if err != nil {
		return false
	}
	resp, err := c.doRequest(req, false)
	if err != nil {
		return false
	}
	status := resp.StatusCode
	_ = resp.Body.Close()
	if status == http.StatusOK {
		if records := cookiesFromJar(c.client.GetCookieJar()); len(records) > 0 {
			_ = saveCookieFile(c.cookieFilePath, records)
		}
		return true
	}

	members, err := c.GetMembers()
	if err != nil || len(members) == 0 {
		return false
	}
	if records := cookiesFromJar(c.client.GetCookieJar()); len(records) > 0 {
		_ = saveCookieFile(c.cookieFilePath, records)
	}
	return true
}

func (c *HealthClient) HasAccessHash() bool {
	return len(c.cookieValues("access_hash")) > 0
}

func (c *HealthClient) GetHospitalsByCity(cityID string) ([]map[string]any, error) {
	if cityID == "" {
		cityID = "5"
	}
	form := url.Values{}
	form.Set("c", cityID)
	req, err := c.newRequest(
		http.MethodPost,
		"https://www.91160.com/ajax/getunitbycity.html",
		strings.NewReader(form.Encode()),
		http.Header{"Content-Type": []string{"application/x-www-form-urlencoded"}},
	)
	if err != nil {
		return nil, err
	}
	resp, err := c.doRequest(req, true)
	if err != nil {
		return nil, err
	}
	body, err := readResponseBody(resp)
	if err != nil {
		return nil, err
	}
	var result []map[string]any
	if err := decodeJSON(body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

func (c *HealthClient) GetDepsByUnit(unitID string) ([]map[string]any, error) {
	form := url.Values{}
	form.Set("keyValue", unitID)
	req, err := c.newRequest(
		http.MethodPost,
		"https://www.91160.com/ajax/getdepbyunit.html",
		strings.NewReader(form.Encode()),
		http.Header{"Content-Type": []string{"application/x-www-form-urlencoded"}},
	)
	if err != nil {
		return nil, err
	}
	resp, err := c.doRequest(req, true)
	if err != nil {
		return nil, err
	}
	body, err := readResponseBody(resp)
	if err != nil {
		return nil, err
	}
	var result []map[string]any
	if err := decodeJSON(body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

func (c *HealthClient) GetMembers() ([]Member, error) {
	req, err := c.newRequest(http.MethodGet, "https://user.91160.com/member.html", nil, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.doRequest(req, true)
	if err != nil {
		return nil, err
	}
	body, err := readResponseBody(resp)
	if err != nil {
		return nil, err
	}
	respURL := ""
	if resp.Request != nil && resp.Request.URL != nil {
		respURL = resp.Request.URL.String()
	}
	if strings.Contains(strings.ToLower(respURL), "login") || strings.Contains(firstN(body, 500), "登录") {
		return nil, nil
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	members := make([]Member, 0)
	doc.Find("tbody#mem_list tr").Each(func(_ int, sel *goquery.Selection) {
		id, _ := sel.Attr("id")
		id = strings.TrimPrefix(id, "mem")
		tds := sel.Find("td")
		if tds.Length() == 0 {
			return
		}
		name := strings.TrimSpace(tds.Eq(0).Text())
		name = strings.ReplaceAll(name, "默认", "")
		certified := false
		tds.Each(func(_ int, td *goquery.Selection) {
			if strings.Contains(td.Text(), "认证") {
				certified = true
			}
		})
		if id == "" && name == "" {
			return
		}
		members = append(members, Member{
			ID:        id,
			Name:      name,
			Certified: certified,
		})
	})
	return members, nil
}

func (c *HealthClient) GetTicketDetail(unitID, depID, scheduleID, memberID string) (*TicketDetail, error) {
	targetURL := fmt.Sprintf("https://www.91160.com/guahao/ystep1/uid-%s/depid-%s/schid-%s.html", unitID, depID, scheduleID)
	req, err := c.newRequest(http.MethodGet, targetURL, nil, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.doRequest(req, true)
	if err != nil {
		return nil, err
	}
	body, err := readResponseBody(resp)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(body))
	if err != nil {
		return nil, err
	}

	timeSlots := make([]TimeSlot, 0)
	doc.Find("#delts li").Each(func(_ int, sel *goquery.Selection) {
		name := strings.TrimSpace(sel.Text())
		val, _ := sel.Attr("val")
		if val != "" {
			timeSlots = append(timeSlots, TimeSlot{Name: name, Value: val})
		}
	})

	valueOf := func(sel *goquery.Selection) string {
		if sel == nil {
			return ""
		}
		val, _ := sel.Attr("value")
		return strings.TrimSpace(val)
	}
	textOf := func(sel *goquery.Selection) string {
		if sel == nil {
			return ""
		}
		return strings.TrimSpace(sel.Text())
	}

	normalizeAddressID := func(value string) string {
		value = strings.TrimSpace(value)
		if value == "" || value == "0" || value == "-1" {
			return ""
		}
		return value
	}
	normalizeAddressText := func(value string) string {
		value = strings.TrimSpace(value)
		if value == "" {
			return ""
		}
		placeholders := []string{"请选择", "请填写", "请输入", "城市地址"}
		for _, p := range placeholders {
			if strings.Contains(value, p) {
				return ""
			}
		}
		return value
	}

	schData := valueOf(doc.Find("input[name='sch_data']").First())
	detlidRealtime := valueOf(doc.Find("#detlid_realtime").First())
	levelCode := valueOf(doc.Find("#level_code").First())
	schDate := valueOf(firstMatch(doc, "input[name='sch_date']", "#sch_date"))
	orderNo := valueOf(firstMatch(doc, "input[name='order_no']", "#order_no"))
	diseaseContent := valueOf(firstMatch(doc, "input[name='disease_content']", "#disease_content"))
	isHot := valueOf(firstMatch(doc, "input[name='is_hot']", "#is_hot"))
	hisMemID := valueOf(firstMatch(doc, "input[name='hisMemId']", "#hismemid"))
	diseaseInput := textOf(firstMatch(doc, "textarea[name='disease_input']", "#disease_input"))

	var addressID string
	var addressText string
	addressList := make([]AddressOption, 0)

	midValue := strings.TrimSpace(memberID)
	midInputs := doc.Find("input[name='mid']")
	var selectedMid *goquery.Selection
	if midValue != "" {
		midInputs.EachWithBreak(func(_ int, sel *goquery.Selection) bool {
			val, _ := sel.Attr("value")
			if strings.TrimSpace(val) == midValue {
				selectedMid = sel
				return false
			}
			return true
		})
	} else {
		midInputs.EachWithBreak(func(_ int, sel *goquery.Selection) bool {
			if _, ok := sel.Attr("checked"); ok {
				selectedMid = sel
				return false
			}
			return true
		})
		if selectedMid == nil && midInputs.Length() > 0 {
			selectedMid = midInputs.First()
		}
	}

	midAddressID := ""
	midAddressText := ""
	if selectedMid != nil {
		midAddressID = normalizeAddressID(attrFallback(selectedMid, "area_id", "areaId", "areaid"))
		midAddressText = normalizeAddressText(attrFallback(selectedMid, "address", "addr"))
	}

	addressID = normalizeAddressID(valueOf(firstMatch(doc, "input[name='addressId']", "#addressId")))
	addressText = normalizeAddressText(valueOf(firstMatch(doc, "input[name='address']", "#address")))

	addressSelect := firstMatch(doc, "select[name='addressId']", "#addressId", "#useraddress_area")
	var selectedAddress *AddressOption
	if addressSelect != nil && addressSelect.Length() > 0 {
		addressSelect.Find("option").Each(func(_ int, sel *goquery.Selection) {
			val := normalizeAddressID(attrFallback(sel, "value"))
			text := normalizeAddressText(strings.TrimSpace(sel.Text()))
			if val == "" || text == "" {
				return
			}
			item := AddressOption{ID: val, Text: text}
			addressList = append(addressList, item)
			if _, ok := sel.Attr("selected"); ok && selectedAddress == nil {
				selectedAddress = &item
			}
		})
	}

	if addressID != "" && addressText == "" {
		for _, item := range addressList {
			if item.ID == addressID {
				addressText = item.Text
				break
			}
		}
	}
	if addressID == "" || addressText == "" {
		if selectedAddress != nil {
			if addressID == "" {
				addressID = selectedAddress.ID
			}
			if addressText == "" {
				addressText = selectedAddress.Text
			}
		} else if len(addressList) > 0 {
			if addressID == "" {
				addressID = addressList[0].ID
			}
			if addressText == "" {
				addressText = addressList[0].Text
			}
		}
	}
	if midAddressID != "" {
		addressID = midAddressID
	}
	if midAddressText != "" {
		addressText = midAddressText
	}

	return &TicketDetail{
		Times:          timeSlots,
		TimeSlots:      timeSlots,
		SchData:        schData,
		DetlidRealtime: detlidRealtime,
		LevelCode:      levelCode,
		SchDate:        schDate,
		OrderNo:        orderNo,
		DiseaseContent: diseaseContent,
		DiseaseInput:   diseaseInput,
		IsHot:          isHot,
		HisMemID:       hisMemID,
		AddressID:      addressID,
		Address:        addressText,
		Addresses:      addressList,
	}, nil
}

func (c *HealthClient) SubmitOrder(params map[string]any) (*SubmitOrderResult, error) {
	data := map[string]string{
		"sch_data":        formValue(params["sch_data"]),
		"mid":             formValue(params["member_id"]),
		"addressId":       formValue(params["addressId"]),
		"address":         formValue(params["address"]),
		"hisMemId":        firstNonEmpty(params, "hisMemId", "his_mem_id"),
		"disease_input":   formValue(params["disease_input"]),
		"order_no":        formValue(params["order_no"]),
		"disease_content": formValue(params["disease_content"]),
		"accept":          "1",
		"unit_id":         formValue(params["unit_id"]),
		"schedule_id":     formValue(params["schedule_id"]),
		"dep_id":          formValue(params["dep_id"]),
		"his_dep_id":      formValue(params["his_dep_id"]),
		"sch_date":        formValue(params["sch_date"]),
		"time_type":       formValue(params["time_type"]),
		"doctor_id":       formValue(params["doctor_id"]),
		"his_doc_id":      formValue(params["his_doc_id"]),
		"detlid":          formValue(params["detlid"]),
		"detlid_realtime": formValue(params["detlid_realtime"]),
		"level_code":      formValue(params["level_code"]),
		"is_hot":          formValue(params["is_hot"]),
	}

	headers := c.buildSubmitHeaders(data["unit_id"], data["dep_id"], data["schedule_id"])

	addressID := strings.TrimSpace(data["addressId"])
	addressText := strings.TrimSpace(data["address"])
	if (addressID == "" || addressID == "0" || addressID == "-1") || addressText == "" {
		ticket, err := c.GetTicketDetail(
			data["unit_id"],
			data["dep_id"],
			data["schedule_id"],
			data["mid"],
		)
		if err == nil && ticket != nil {
			if data["addressId"] == "" {
				data["addressId"] = ticket.AddressID
			}
			if data["address"] == "" {
				data["address"] = ticket.Address
			}
			for _, key := range []string{"hisMemId", "sch_date", "order_no", "disease_input", "disease_content", "is_hot"} {
				if strings.TrimSpace(data[key]) != "" {
					continue
				}
				switch key {
				case "hisMemId":
					data[key] = ticket.HisMemID
				case "sch_date":
					data[key] = ticket.SchDate
				case "order_no":
					data[key] = ticket.OrderNo
				case "disease_input":
					data[key] = ticket.DiseaseInput
				case "disease_content":
					data[key] = ticket.DiseaseContent
				case "is_hot":
					data[key] = ticket.IsHot
				}
			}
		}
	}

	c.setSubmitCookies(data)

	if data["mid"] != "" {
		checkHeaders := cloneHeader(headers)
		checkHeaders.Set("X-Requested-With", "XMLHttpRequest")
		checkHeaders.Set("Accept", "application/json, text/javascript, */*; q=0.01")
		checkHeaders.Set("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
		form := url.Values{}
		form.Set("mid", data["mid"])
		checkReq, err := c.newRequest(
			http.MethodPost,
			"https://www.91160.com/guahao/checkidinfo.html",
			strings.NewReader(form.Encode()),
			checkHeaders,
		)
		if err == nil {
			_, _ = c.doRequest(checkReq, true)
		}
	}

	form := url.Values{}
	for key, value := range data {
		form.Set(key, value)
	}
	req, err := c.newRequest(
		http.MethodPost,
		"https://www.91160.com/guahao/ysubmit.html",
		strings.NewReader(form.Encode()),
		headers,
	)
	if err != nil {
		return nil, err
	}
	resp, err := c.doRequest(req, false)
	if err != nil {
		return nil, err
	}
	body, err := readResponseBody(resp)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode == http.StatusMovedPermanently || resp.StatusCode == http.StatusFound {
		location := resp.Header.Get("Location")
		if location != "" {
			redirectURL := resolveURL("https://www.91160.com/guahao/ysubmit.html", location)
			if strings.Contains(strings.ToLower(redirectURL), "success") {
				return &SubmitOrderResult{Success: true, Status: true, Message: "OK", URL: redirectURL}, nil
			}

			reason := ""
			debugPath := ""
			if redirectURL != "" {
				followReq, err := c.newRequest(http.MethodGet, redirectURL, nil, headers)
				if err == nil {
					followResp, err := c.doRequest(followReq, true)
					if err == nil && followResp != nil {
						followBody, _ := readResponseBody(followResp)
						if len(followBody) > 0 {
							debugPath = c.dumpSubmitResponse(followBody)
						}
						reason = c.extractSubmitMessage(string(followBody))
						if data["mid"] != "" && (reason == "" || isGenericSubmitMessage(reason)) {
							if msg := extractMemberError(string(followBody), data["mid"]); msg != "" {
								reason = msg
							}
						}
						if reason == "" {
							reason = snippet(string(followBody), 200)
						}
					}
				}
			}

			msg := fmt.Sprintf("submit redirect: %s", redirectURL)
			if reason != "" {
				msg = fmt.Sprintf("%s (%s)", msg, reason)
			}
			if debugPath != "" {
				msg = fmt.Sprintf("%s Debug=%s", msg, debugPath)
			}
			c.setLastError(msg)
			return &SubmitOrderResult{Success: false, Status: false, Message: msg}, nil
		}
	}

	msg := c.extractSubmitMessage(string(body))
	if msg != "" {
		c.setLastError(msg)
		return &SubmitOrderResult{Success: false, Status: false, Message: fmt.Sprintf("submit failed: %s", msg)}, nil
	}
	if snippetText := snippet(string(body), 200); snippetText != "" {
		msg = fmt.Sprintf("submit failed code=%d, resp=%s", resp.StatusCode, snippetText)
		c.setLastError(msg)
		return &SubmitOrderResult{Success: false, Status: false, Message: msg}, nil
	}
	debugPath := c.dumpSubmitResponse(body)
	msg = fmt.Sprintf("submit failed code=%d (no response). Debug=%s", resp.StatusCode, debugPath)
	c.setLastError(msg)
	return &SubmitOrderResult{Success: false, Status: false, Message: msg}, nil
}

func (c *HealthClient) GetServerDatetime() (*time.Time, error) {
	req, err := c.newRequest(http.MethodGet, "https://www.91160.com/favicon.ico", nil, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.doRequest(req, true)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	dateHeader := resp.Header.Get("Date")
	if dateHeader == "" {
		return nil, nil
	}
	parsed, err := http.ParseTime(dateHeader)
	if err != nil {
		return nil, err
	}
	local := parsed.Local()
	return &local, nil
}

func (c *HealthClient) GetSchedule(unitID, depID, date string) ([]map[string]any, error) {
	c.setLastError("")
	c.setLastStatusCode(0)
	if date == "" {
		date = time.Now().Format("2006-01-02")
	}
	userKeys := uniqueStrings(c.cookieValues("access_hash"))
	if len(userKeys) == 0 {
		c.setLastError("missing access_hash")
		return nil, fmt.Errorf("%w: missing access_hash", ErrLoginRequired)
	}

	targetURL := "https://gate.91160.com/guahao/v1/pc/sch/dep"
	loginExpired := false
	for _, key := range userKeys {
		params := url.Values{}
		params.Set("unit_id", unitID)
		params.Set("dep_id", depID)
		params.Set("date", date)
		params.Set("p", "0")
		params.Set("user_key", key)
		queryURL := targetURL + "?" + params.Encode()
		headers := cloneHeader(c.headers)
		headers.Set("Origin", "https://www.91160.com")
		headers.Set("Referer", "https://www.91160.com/")
		req, err := c.newRequest(http.MethodGet, queryURL, nil, headers)
		if err != nil {
			continue
		}
		resp, err := c.doRequest(req, true)
		if err != nil {
			c.setLastError(fmt.Sprintf("schedule request failed: %v", err))
			continue
		}
		body, err := readResponseBody(resp)
		if err != nil {
			c.setLastError(fmt.Sprintf("schedule read failed: %v", err))
			continue
		}
		c.setLastStatusCode(resp.StatusCode)
		if resp.StatusCode != http.StatusOK {
			c.setLastError(fmt.Sprintf("schedule http %d", resp.StatusCode))
			continue
		}

		var payload map[string]any
		if err := decodeJSON(body, &payload); err != nil {
			c.setLastError(fmt.Sprintf("schedule decode failed: %v", err))
			continue
		}

		if toString(payload["result_code"]) == "1" {
			resultData := asMap(payload["data"])
			docList := asSlice(resultData["doc"])
			schMap := asMap(resultData["sch"])

			validDocs := make([]map[string]any, 0)
			for _, rawDoc := range docList {
				doc := asMap(rawDoc)
				if doc == nil {
					continue
				}
				docID := toString(doc["doctor_id"])
				if docID == "" {
					continue
				}
				rawSchedule := schMap[docID]
				if rawSchedule == nil {
					continue
				}
				schedules := make([]map[string]any, 0)
				schData := asMap(rawSchedule)
				if schData != nil {
					for _, timeType := range []string{"am", "pm"} {
						typeData := schData[timeType]
						switch v := typeData.(type) {
						case map[string]any:
							for _, slot := range v {
								slotMap := asMap(slot)
								if slotMap == nil {
									continue
								}
								if toString(slotMap["schedule_id"]) != "" {
									schedules = append(schedules, slotMap)
								}
							}
						case []any:
							for _, slot := range v {
								slotMap := asMap(slot)
								if slotMap == nil {
									continue
								}
								if toString(slotMap["schedule_id"]) != "" {
									schedules = append(schedules, slotMap)
								}
							}
						}
					}
				}

				if len(schedules) == 0 {
					continue
				}

				doc["schedules"] = schedules
				doc["schedule_id"] = toString(schedules[0]["schedule_id"])
				doc["time_type_desc"] = toString(schedules[0]["time_type_desc"])
				totalLeft := 0
				for _, slot := range schedules {
					totalLeft += toInt(slot["left_num"])
				}
				doc["total_left_num"] = totalLeft
				validDocs = append(validDocs, doc)
			}

			if len(validDocs) > 0 {
				c.setLastError("")
				return validDocs, nil
			}
			if len(docList) > 0 {
				c.setLastError("")
				return nil, nil
			}
		} else if toString(payload["error_code"]) == "10022" {
			loginExpired = true
			continue
		} else {
			errCode := toString(payload["error_code"])
			if errCode == "" {
				errCode = toString(payload["result_code"])
			}
			errMsg := toString(payload["error_msg"])
			if errMsg == "" {
				errMsg = toString(payload["error_desc"])
			}
			if errMsg == "" {
				errMsg = toString(payload["msg"])
			}
			if errMsg == "" {
				errMsg = toString(payload["message"])
			}
			if errMsg == "" {
				errMsg = toString(payload["result_msg"])
			}
			c.setLastError(fmt.Sprintf("schedule api error: code=%s msg=%s", errCode, errMsg))
		}
	}

	if loginExpired {
		c.setLastError("login expired or insufficient permissions (error_code=10022)")
		return nil, fmt.Errorf("%w: error_code=10022", ErrLoginRequired)
	}
	if c.LastError() == "" {
		c.setLastError("schedule query failed")
	}
	return nil, errors.New(c.LastError())
}

func (c *HealthClient) withFollowRedirect(follow bool, fn func() (*http.Response, error)) (*http.Response, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	previous := c.client.GetFollowRedirect()
	if previous != follow {
		c.client.SetFollowRedirect(follow)
	}
	resp, err := fn()
	if previous != follow {
		c.client.SetFollowRedirect(previous)
	}
	return resp, err
}

func (c *HealthClient) doRequest(req *http.Request, follow bool) (*http.Response, error) {
	return c.withFollowRedirect(follow, func() (*http.Response, error) {
		return c.client.Do(req)
	})
}

func (c *HealthClient) newRequest(method, targetURL string, body io.Reader, extraHeaders http.Header) (*http.Request, error) {
	req, err := http.NewRequest(method, targetURL, body)
	if err != nil {
		return nil, err
	}
	req.Header = cloneHeader(c.headers)
	for key, values := range extraHeaders {
		copied := append([]string{}, values...)
		req.Header[key] = copied
	}
	return req, nil
}

func (c *HealthClient) cookieValues(name string) []string {
	records := cookiesFromJar(c.client.GetCookieJar())
	values := make([]string, 0)
	for _, record := range records {
		if record.Name == name && record.Value != "" {
			values = append(values, record.Value)
		}
	}
	return values
}

func (c *HealthClient) setSubmitCookies(data map[string]string) {
	uid := strings.TrimSpace(data["uid"])
	if uid == "" {
		uid = c.getUIDFromCookies()
	}
	depID := strings.TrimSpace(data["dep_id"])
	docID := strings.TrimSpace(data["doctor_id"])
	if uid == "" || depID == "" || docID == "" {
		return
	}
	memberID := strings.TrimSpace(data["mid"])
	detlid := strings.TrimSpace(data["detlid"])
	accept := strings.TrimSpace(data["accept"])
	if accept == "" {
		accept = "1"
	}
	cookies := map[string]string{
		fmt.Sprintf("member_id_%s_%s_%s", uid, depID, docID): memberID,
		fmt.Sprintf("detl_id_%s_%s_%s", uid, depID, docID):   detlid,
		fmt.Sprintf("accept_%s_%s_%s", uid, depID, docID):    accept,
	}
	records := make([]CookieRecord, 0)
	for name, value := range cookies {
		if value == "" {
			continue
		}
		records = append(records, CookieRecord{
			Name:   name,
			Value:  value,
			Domain: ".91160.com",
			Path:   "/",
		})
	}
	if len(records) > 0 {
		setCookiesOnClient(c.client, records)
	}
}

func (c *HealthClient) getUIDFromCookies() string {
	records := cookiesFromJar(c.client.GetCookieJar())
	for _, record := range records {
		if record.Name == "User_datas" || record.Name == "UserName_datas" {
			uid := extractUIDFromCookieValue(record.Value)
			if uid != "" {
				return uid
			}
		}
	}
	return ""
}

func (c *HealthClient) buildSubmitHeaders(unitID, depID, scheduleID string) http.Header {
	headers := cloneHeader(c.headers)
	if unitID != "" && depID != "" && scheduleID != "" {
		headers.Set("Referer", fmt.Sprintf("https://www.91160.com/guahao/ystep1/uid-%s/depid-%s/schid-%s.html", unitID, depID, scheduleID))
	}
	headers.Set("Origin", "https://www.91160.com")
	headers.Set("Connection", "keep-alive")
	headers.Set("Pragma", "no-cache")
	headers.Set("Cache-Control", "no-cache")
	headers.Set("Content-Type", "application/x-www-form-urlencoded")
	return headers
}

func (c *HealthClient) extractSubmitMessage(text string) string {
	patterns := []string{
		`alert\(["']([^"']+)["']\)`,
		`layer\.msg\(["']([^"']+)["']\)`,
		`layer\.alert\(["']([^"']+)["']\)`,
		`msg\(["']([^"']+)["']\)`,
		`toast\(["']([^"']+)["']\)`,
	}
	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		match := re.FindStringSubmatch(text)
		if len(match) > 1 {
			return strings.TrimSpace(match[1])
		}
	}
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(text))
	if err != nil {
		return ""
	}
	title := strings.TrimSpace(doc.Find("title").First().Text())
	return title
}

func (c *HealthClient) dumpSubmitResponse(content []byte) string {
	logsDir, err := resolveLogsDir()
	if err != nil {
		return ""
	}
	filename := fmt.Sprintf("submit_resp_%s.bin", time.Now().Format("20060102_150405"))
	path := filepath.Join(logsDir, filename)
	_ = os.WriteFile(path, content, 0o644)
	return path
}

func newTLSClient() (tls_client.HttpClient, error) {
	jar := tls_client.NewCookieJar()
	options := []tls_client.HttpClientOption{
		tls_client.WithClientProfile(profiles.Chrome_120),
		tls_client.WithRandomTLSExtensionOrder(),
		tls_client.WithCookieJar(jar),
		tls_client.WithDefaultHeaders(defaultHeaders()),
	}
	client, err := tls_client.NewHttpClient(tls_client.NewNoopLogger(), options...)
	if err != nil {
		return nil, err
	}
	client.SetFollowRedirect(true)
	return client, nil
}

func defaultHeaders() http.Header {
	headers := http.Header{}
	headers.Set("User-Agent", defaultUserAgent)
	headers.Set("Referer", "https://www.91160.com/")
	headers.Set("Origin", "https://www.91160.com")
	return headers
}

func cloneHeader(src http.Header) http.Header {
	dst := http.Header{}
	for key, values := range src {
		dst[key] = append([]string{}, values...)
	}
	return dst
}

func decodeJSON(data []byte, out any) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode(out)
}

func readResponseBody(resp *http.Response) ([]byte, error) {
	if resp == nil || resp.Body == nil {
		return nil, nil
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

func firstMatch(doc *goquery.Document, selectors ...string) *goquery.Selection {
	for _, selector := range selectors {
		selection := doc.Find(selector).First()
		if selection.Length() > 0 {
			return selection
		}
	}
	return nil
}

func attrFallback(sel *goquery.Selection, attrs ...string) string {
	for _, attr := range attrs {
		if value, ok := sel.Attr(attr); ok {
			return value
		}
	}
	return ""
}

func formValue(value any) string {
	if value == nil {
		return ""
	}
	switch v := value.(type) {
	case bool:
		if v {
			return "1"
		}
		return "0"
	case string:
		return v
	case json.Number:
		return v.String()
	default:
		return fmt.Sprintf("%v", value)
	}
}

func firstNonEmpty(params map[string]any, keys ...string) string {
	for _, key := range keys {
		if val, ok := params[key]; ok {
			str := strings.TrimSpace(formValue(val))
			if str != "" {
				return str
			}
		}
	}
	return ""
}

func extractUIDFromCookieValue(value string) string {
	if value == "" {
		return ""
	}
	decoded, err := url.QueryUnescape(value)
	if err != nil {
		decoded = value
	}
	var data map[string]any
	if err := json.Unmarshal([]byte(decoded), &data); err != nil {
		return ""
	}
	for _, key := range []string{"fid", "uid", "id"} {
		if v, ok := data[key]; ok {
			return toString(v)
		}
	}
	return ""
}

func toString(value any) string {
	switch v := value.(type) {
	case string:
		return v
	case []byte:
		return string(v)
	case json.Number:
		return v.String()
	case fmt.Stringer:
		return v.String()
	case float64:
		return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.6f", v), "0"), ".")
	case float32:
		return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.6f", v), "0"), ".")
	case int:
		return fmt.Sprintf("%d", v)
	case int64:
		return fmt.Sprintf("%d", v)
	case int32:
		return fmt.Sprintf("%d", v)
	case uint:
		return fmt.Sprintf("%d", v)
	case uint64:
		return fmt.Sprintf("%d", v)
	case uint32:
		return fmt.Sprintf("%d", v)
	default:
		return fmt.Sprintf("%v", v)
	}
}

func toInt(value any) int {
	switch v := value.(type) {
	case int:
		return v
	case int64:
		return int(v)
	case int32:
		return int(v)
	case uint:
		return int(v)
	case uint64:
		return int(v)
	case float64:
		return int(v)
	case float32:
		return int(v)
	case json.Number:
		if i, err := v.Int64(); err == nil {
			return int(i)
		}
	case string:
		if v == "" {
			return 0
		}
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return 0
}

func asMap(value any) map[string]any {
	if value == nil {
		return nil
	}
	if v, ok := value.(map[string]any); ok {
		return v
	}
	if v, ok := value.(map[string]interface{}); ok {
		return v
	}
	return nil
}

func asSlice(value any) []any {
	if value == nil {
		return nil
	}
	if v, ok := value.([]any); ok {
		return v
	}
	if v, ok := value.([]interface{}); ok {
		return v
	}
	if v, ok := value.([]map[string]any); ok {
		out := make([]any, 0, len(v))
		for _, item := range v {
			out = append(out, item)
		}
		return out
	}
	if v, ok := value.([]map[string]interface{}); ok {
		out := make([]any, 0, len(v))
		for _, item := range v {
			out = append(out, item)
		}
		return out
	}
	return nil
}

func uniqueStrings(values []string) []string {
	seen := make(map[string]struct{})
	out := make([]string, 0, len(values))
	for _, value := range values {
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		out = append(out, value)
	}
	return out
}

func resolveURL(baseURL, location string) string {
	if location == "" {
		return ""
	}
	parsedBase, err := url.Parse(baseURL)
	if err != nil {
		return location
	}
	parsedLocation, err := url.Parse(location)
	if err != nil {
		return location
	}
	return parsedBase.ResolveReference(parsedLocation).String()
}

func snippet(text string, maxLen int) string {
	clean := regexp.MustCompile(`[\x00-\x1f\x7f]+`).ReplaceAllString(text, " ")
	clean = strings.TrimSpace(regexp.MustCompile(`\s+`).ReplaceAllString(clean, " "))
	if maxLen <= 0 || len(clean) <= maxLen {
		return clean
	}
	return clean[:maxLen]
}

func extractMemberError(htmlText, mid string) string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlText))
	if err != nil {
		return ""
	}
	node := doc.Find(fmt.Sprintf("input[name='mid'][value='%s']", mid)).First()
	if node.Length() == 0 {
		return ""
	}
	if title, _ := node.Attr("data-title"); title != "" {
		return strings.TrimSpace(title)
	}
	needCheck, _ := node.Attr("need_check")
	isComplete, _ := node.Attr("is_info_complete")
	if needCheck == "1" {
		return "就诊人信息需审核/校验，暂不可预约"
	}
	if isComplete == "0" {
		return "就诊人信息未完善，无法预约"
	}
	return ""
}

func isGenericSubmitMessage(message string) bool {
	message = strings.TrimSpace(message)
	if message == "" {
		return true
	}
	if strings.Contains(message, "操作失败") {
		return true
	}
	if strings.Contains(message, "请求错误") {
		return true
	}
	if strings.Contains(message, "提交失败") {
		return true
	}
	return false
}

func firstN(data []byte, n int) string {
	if len(data) <= n {
		return string(data)
	}
	return string(data[:n])
}
