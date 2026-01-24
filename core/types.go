package core

type AddressOption struct {
	ID   string `json:"id"`
	Text string `json:"text"`
}

type TimeSlot struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

type TicketDetail struct {
	Times           []TimeSlot     `json:"times"`
	TimeSlots       []TimeSlot     `json:"time_slots"`
	SchData         string         `json:"sch_data"`
	DetlidRealtime  string         `json:"detlid_realtime"`
	LevelCode       string         `json:"level_code"`
	SchDate         string         `json:"sch_date"`
	OrderNo         string         `json:"order_no"`
	DiseaseContent  string         `json:"disease_content"`
	DiseaseInput    string         `json:"disease_input"`
	IsHot           string         `json:"is_hot"`
	HisMemID        string         `json:"hisMemId"`
	AddressID       string         `json:"addressId"`
	Address         string         `json:"address"`
	Addresses       []AddressOption `json:"addresses"`
}

type Member struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	Certified bool   `json:"certified"`
}

type SubmitOrderResult struct {
	Success bool   `json:"success"`
	Status  bool   `json:"status"`
	Message string `json:"msg"`
	URL     string `json:"url,omitempty"`
}

type QRLoginResult struct {
	Success    bool   `json:"success"`
	Message    string `json:"message"`
	CookiePath string `json:"cookie_path,omitempty"`
}

type GrabConfig struct {
	UnitID         string   `json:"unit_id"`
	UnitName       string   `json:"unit_name,omitempty"`
	DepID          string   `json:"dep_id"`
	DepName        string   `json:"dep_name,omitempty"`
	DoctorIDs      []string `json:"doctor_ids,omitempty"`
	MemberID       string   `json:"member_id"`
	MemberName     string   `json:"member_name,omitempty"`
	TargetDates    []string `json:"target_dates"`
	TimeTypes      []string `json:"time_types,omitempty"`
	PreferredHours []string `json:"preferred_hours,omitempty"`
	AddressID      string   `json:"addressId,omitempty"`
	Address        string   `json:"address,omitempty"`
	StartTime      string   `json:"start_time,omitempty"`
	UseServerTime  bool     `json:"use_server_time,omitempty"`
	RetryInterval  float64  `json:"retry_interval,omitempty"`
	MaxRetries     int      `json:"max_retries,omitempty"`
	UseProxySubmit bool     `json:"use_proxy_submit,omitempty"`
}

type GrabSuccess struct {
	UnitName   string `json:"unit_name"`
	DepName    string `json:"dep_name"`
	DoctorName string `json:"doctor_name"`
	Date       string `json:"date"`
	TimeSlot   string `json:"time_slot"`
	MemberName string `json:"member_name"`
	URL        string `json:"url,omitempty"`
}
