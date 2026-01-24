# 91160 重构契约（Python -> Go/Wails）

> 本文为迁移期“接口与数据契约”，以现有 Python 逻辑为唯一事实来源。
> 所有字段、日志与文件内容均使用 UTF-8 编码。

## 1. 范围与来源
- 业务来源：`core/client.py`、`core/grab.py`、`core/qr_login.py`
- UI 依赖：`gui/windows/main_window.py`
- 配置文件：`config/cities.json`、`config/user_state.json`、`config/cookies.json`

## 2. 统一原则
- **联系观点**：接口与配置必须保持一致，否则 GUI 与核心逻辑将发生断裂。
- **发展观点**：允许逐步替换实现，但契约不随意破坏。
- **实践原则**：以可运行、可回滚为标准，前端依赖的数据结构必须先落地。

## 3. 数据模型（字段与类型）
> 约定：除非明确说明，所有 ID 均按 **字符串** 处理，避免 JSON/前端数值精度问题。

### 3.1 City（城市）
- `cityId`: string
- `name`: string

### 3.2 Hospital（医院）
- `unit_id`: string
- `unit_name`: string

### 3.3 Department（科室）
- `dep_id`: string
- `dep_name`: string
- 可能出现嵌套结构：`childs: []`

### 3.4 Member（就诊人）
- `id`: string
- `name`: string
- `certified`: boolean

### 3.5 Doctor（医生）
- `doctor_id`: string
- `doctor_name`: string
- `reg_fee`: string | number
- `total_left_num`: number
- `his_doc_id`: string (可选)
- `his_dep_id`: string (可选)
- `schedules`: ScheduleSlot[]

### 3.6 ScheduleSlot（排班时段）
- `schedule_id`: string
- `time_type`: string (`am`/`pm`)
- `time_type_desc`: string
- `left_num`: number
- `sch_date`: string (yyyy-MM-dd)

### 3.7 TicketDetail（号源详情）
- `times` / `time_slots`: Array<{ name: string, value: string }>
- `sch_data`: string
- `detlid_realtime`: string
- `level_code`: string
- `sch_date`: string
- `order_no`: string
- `disease_content`: string
- `disease_input`: string
- `is_hot`: string
- `hisMemId`: string
- `addressId`: string
- `address`: string
- `addresses`: Array<{ id: string, text: string }>

### 3.8 SubmitOrderResult（提交结果）
- `success`: boolean
- `status`: boolean
- `msg`: string
- `url`: string (可选)

### 3.9 GrabConfig（抢号配置）
- `unit_id`: string
- `unit_name`: string
- `dep_id`: string
- `dep_name`: string
- `doctor_ids`: string[]
- `member_id`: string
- `member_name`: string
- `target_dates`: string[]
- `time_types`: string[] (`am`/`pm`)
- `preferred_hours`: string[]
- `addressId`: string (可选)
- `address`: string (可选)
- `start_time`: string (HH:MM:SS，可选)
- `use_server_time`: boolean (可选)
- `retry_interval`: number (秒，可选)
- `max_retries`: number (0 表示无限，可选)

### 3.10 UserState（UI 状态）
- `city_id`: string
- `unit_id`: string | null
- `dep_id`: string | null
- `doctor_id`: string | null
- `member_id`: string | null
- `target_date`: string (yyyy-MM-dd)
- `target_dates`: string[] (可选，多日期抢号时的追加日期列表，与 `target_date` 合并使用)
- `time_slots`: string[] (`am`/`pm`)

### 3.11 Cookies（登录 Cookie）
- 列表模式：`[{ name, value, domain, path }]`
- 兼容字典模式：`{ name: value }`（旧格式）

## 4. 接口映射（Python -> Go/Wails）
> Go/Wails 层需保持字段一致，仅改变实现方式。

- `GetCities()`
  - 来源：读取 `config/cities.json`
- `GetUserState()` / `SaveUserState(state)`
  - 来源：读取/写入 `config/user_state.json`
- `ExportLogs(entries)`
  - 来源：前端运行日志导出（弹出保存对话框并写入文件）
- `GetHospitalsByCity(cityId)`
  - 来源：`HealthClient.get_hospitals_by_city`
- `GetDepsByUnit(unitId)`
  - 来源：`HealthClient.get_deps_by_unit`
- `GetMembers()`
  - 来源：`HealthClient.get_members`
- `GetSchedule(unitId, depId, date)`
  - 来源：`HealthClient.get_schedule`
  - 说明：登录失效时返回错误（提示重新扫码）
- `GetTicketDetail(unitId, depId, scheduleId, memberId)`
  - 来源：`HealthClient.get_ticket_detail`
- `SubmitOrder(params)`
  - 来源：`HealthClient.submit_order`
- `StartGrab(config)` / `StopGrab()`
  - 来源：`core.grab.grab` + 循环重试逻辑
  - 说明：启动前校验登录状态，未登录将直接返回错误
- `LoginWithQR()` / `PollQR()`
  - 来源：`core.qr_login.FastQRLogin`

## 5. 事件与日志（Wails 事件名建议）
- `log-message`: { level, message }
- `qr-image`: { bytesBase64 }
- `qr-status`: { message }
- `login-status`: { loggedIn: boolean }
- `grab-finished`: { success: boolean, message: string, detail?: GrabSuccess }

GrabSuccess 字段：
- `unit_name`, `dep_name`, `doctor_name`, `date`, `time_slot`, `member_name`, `url`

> 日志等级与颜色映射：
- info: `#AAAAAA`
- success: `#00D26A`
- warn: `#FF9500`
- error: `#FF3B30`

## 6. 兼容性约束
- **字段名保持一致**，尤其是 `unit_id/dep_id/doctor_id` 与 `schedule_id`。
- **时间格式严格**：`yyyy-MM-dd` 与 `HH:MM:SS`。
- **地址字段**：`addressId` 与 `address` 必须成对存在；缺失时允许从号源详情回填。
- **错误回传**：`last_error` 在 Python 中作为 UI 提示来源，Go 侧需提供等价信息。

## 7. 回滚策略
- Go/Wails 任一模块未达标时，直接回退到 Python UI 与核心逻辑；契约文档不影响运行。

## 8. 变更记录
- 2026-01-24：首次落地契约与样例数据。
