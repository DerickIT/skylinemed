import requests
import json
import time
import os
import re
import hashlib
import random
import string
import datetime
import threading
from email.utils import parsedate_to_datetime
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

class HealthClient:
    def __init__(self):
        self.session = requests.Session()
        try:
            self.ua = UserAgent()
            ua_value = self.ua.random
        except Exception:
            self.ua = None
            ua_value = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            'User-Agent': ua_value,
            'Referer': 'https://www.91160.com/',
            'Origin': 'https://www.91160.com'
        }
        self.session.headers.update(self.headers)
        # 使用脚本所在目录的绝对路径，避免工作目录问题
        self.script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cookie_file = os.path.join(self.script_dir, 'cookies.json')
        self.last_error = None
        self.last_status_code = None
        
        if self.load_cookies():
            print(f"[+] 本地 Cookie 加载成功: {self.cookie_file}")

    def load_cookies(self):
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookies_list = json.load(f)
                    # 兼容 List 和 Dict 格式
                    if isinstance(cookies_list, list):
                        for cookie in cookies_list:
                            self.session.cookies.set(
                                cookie['name'], 
                                cookie['value'], 
                                domain=cookie.get('domain', '.91160.com'),
                                path=cookie.get('path', '/')
                            )
                    else:
                        self.session.cookies.update(cookies_list)
                return True
            except Exception as e:
                print(f"[-] 加载 Cookie 异常: {e}")
                return False
        return False

    def save_cookies_from_browser(self, browser_cookies):
        """保存浏览器 Cookie 到本地（保留完整信息）"""
        with open(self.cookie_file, 'w', encoding='utf-8') as f:
            json.dump(browser_cookies, f)
        
        # 同时更新当前 Session
        for cookie in browser_cookies:
            self.session.cookies.set(
                cookie['name'], 
                cookie['value'], 
                domain=cookie.get('domain', '.91160.com'),
                path=cookie.get('path', '/')
            )
        print(f"[+] 完整 Cookie ({len(browser_cookies)}个) 已保存")

    def check_login(self):
        """检查登录状态"""
        # 1. 检查是否存在 access_hash
        has_hash = False
        for c in self.session.cookies:
            if c.name == 'access_hash':
                has_hash = True
                break
        if not has_hash:
            return False
        
        # 2. 实测接口: 获取用户信息 (需要登录)
        # 用 user/index.html 检查，如果不登录会跳回登录页
        try:
            # allow_redirects=False, 如果返回 302 说明未登录
            r = self.session.get("https://user.91160.com/user/index.html", allow_redirects=False, timeout=5)
            if r.status_code == 200:
                return True
            return False
        except:
            return False

    def login_with_browser(self):
        """Playwright 扫码登录"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[-] 未安装 playwright")
            return False

        print("[*] 启动浏览器...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                
                # 1. 构造微信扫码 URL
                state = hashlib.md5(''.join(random.choices(string.ascii_letters + string.digits, k=16)).encode()).hexdigest()
                url = f"https://open.weixin.qq.com/connect/qrconnect?appid=wxdfec0615563d691d&redirect_uri=http%3A%2F%2Fuser.91160.com%2Fsupplier-wechat.html&response_type=code&scope=snsapi_login&state={state}"
                
                page.goto(url)
                print("[*] 请扫码登录...")
                
                # 2. 等待登录成功 (回到 91160)
                try:
                    page.wait_for_url(lambda u: "91160.com" in u and "weixin" not in u, timeout=300000)
                except:
                    print("[-] 扫码超时")
                    browser.close()
                    return False
                
                print("[+] 扫码成功，正在获取Cookie...")
                
                # 3. 快速访问子域获取 Cookie（不等待完全加载）
                page.goto("https://www.91160.com/", wait_until="domcontentloaded")
                page.goto("https://user.91160.com/user/index.html", wait_until="domcontentloaded")
                
                # 4. 立即提取 Cookie
                cookies = context.cookies()
                print(f"[*] 提取到 {len(cookies)} 个 Cookie")
                
                self.save_cookies_from_browser(cookies)
                browser.close()
                return True

        except Exception as e:
            error_msg = str(e)
            if "executable doesn't exist" in error_msg or "Executable doesn't exist" in error_msg:
                print("[-] Playwright 浏览器未安装！请运行: playwright install chromium")
            else:
                print(f"[-] 浏览器登录失败: {e}")
            return False

    def login(self):
        # 先尝试加载本地 Cookie
        self.load_cookies()
        
        if self.check_login():
            print("[+] Cookie 验证成功")
            return True
        
        print("[*] Cookie 已失效或未登录，启动浏览器扫码...")
        return self.login_with_browser()

    # ============ API 接口 ============
    
    def get_hospitals_by_city(self, city_id="5"):
        url = "https://www.91160.com/ajax/getunitbycity.html"
        data = {"c": city_id}
        try:
            r = self.session.post(url, data=data)
            return r.json()
        except: return []

    def get_deps_by_unit(self, unit_id):
        url = "https://www.91160.com/ajax/getdepbyunit.html"
        data = {"keyValue": unit_id}
        try:
            r = self.session.post(url, data=data)
            return r.json()
        except: return []

    def get_members(self):
        """获取就诊人列表"""
        url = "https://user.91160.com/member.html"
        try:
            r = self.session.get(url)
            r.encoding = 'utf-8'  # 强制 UTF-8
            
            # 调试：检查是否需要登录
            if 'login' in r.url.lower() or '登录' in r.text[:500]:
                print("[-] 获取就诊人失败: 需要重新登录")
                return []
            
            soup = BeautifulSoup(r.text, 'html.parser')
            tbody = soup.find('tbody', {'id': 'mem_list'})
            members = []
            if tbody:
                for tr in tbody.find_all('tr'):
                    mid = tr.get('id', '').replace('mem', '')
                    tds = tr.find_all('td')
                    if not tds:
                        continue
                    name = tds[0].get_text(strip=True).replace('默认', '')
                    # 检查是否认证
                    is_certified = any("认证" in td.text for td in tds)
                    members.append({
                        'id': mid,
                        'name': name,
                        'certified': is_certified
                    })
            else:
                print("[-] 未找到就诊人列表 (mem_list)")
            return members
        except Exception as e:
            print(f"[-] 获取就诊人失败: {e}")
            return []

    def get_ticket_detail(self, unit_id, dep_id, sch_id):
        """获取具体的号源时间段和下单所需的隐藏参数"""
        url = f"https://www.91160.com/guahao/ystep1/uid-{unit_id}/depid-{dep_id}/schid-{sch_id}.html"
        try:
            r = self.session.get(url)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # 1. 提取时间段
            delts_div = soup.find(id='delts')
            time_slots = []
            if delts_div:
                for li in delts_div.find_all('li'):
                    text = li.get_text(strip=True)
                    val = li.get('val')
                    if val:
                        time_slots.append({'name': text, 'value': val})
            
            # 2. 提取隐藏参数
            sch_data = soup.find('input', {'name': 'sch_data'})
            detlid_realtime = soup.find(id='detlid_realtime')
            level_code = soup.find(id='level_code')
            address_id = ""
            address_text = ""
            address_list = []
            address_input = soup.find('input', {'name': 'addressId'}) or soup.find(id='addressId')
            if address_input:
                address_id = address_input.get('value', '').strip()
            address_text_input = soup.find('input', {'name': 'address'}) or soup.find(id='address')
            if address_text_input:
                address_text = address_text_input.get('value', '').strip()
            address_select = soup.find('select', {'name': 'addressId'}) or soup.find(id='addressId')
            if address_select and not address_id:
                for option in address_select.find_all('option'):
                    value = option.get('value', '').strip()
                    text = option.get_text(strip=True)
                    if value and text:
                        address_list.append({'id': value, 'text': text})
                if address_list:
                    address_id = address_list[0]['id']
                    if not address_text:
                        address_text = address_list[0]['text']
            
            result = {
                'times': time_slots,
                'time_slots': time_slots,
                'sch_data': sch_data.get('value') if sch_data else '',
                'detlid_realtime': detlid_realtime.get('value') if detlid_realtime else '',
                'level_code': level_code.get('value') if level_code else '',
                'addressId': address_id,
                'address': address_text,
                'addresses': address_list
            }
            return result
        except Exception as e:
            print(f"[-] 获取号源详情失败: {e}")
            return None

    def submit_order(self, order_params=None, **kwargs):
        """提交订单"""
        url = "https://www.91160.com/guahao/ysubmit.html"
        # 兼容旧的单参数传入方式
        if order_params is None:
            params = kwargs.get('order_params', kwargs)
        else:
            params = order_params
        
        data = {
            'sch_data': params.get('sch_data'),
            'mid': params.get('member_id'),
            'addressId': params.get('addressId', ''),
            'address': params.get('address', ''),
            'disease_input': params.get('disease_input', '自动抢号'),
            'order_no': '',
            'disease_content': params.get('disease_content', '自动抢号'),
            'accept': '1',
            'unit_id': params.get('unit_id'),
            'schedule_id': params.get('schedule_id'),
            'dep_id': params.get('dep_id'),
            'his_dep_id': params.get('his_dep_id', ''),
            'sch_date': params.get('sch_date', params.get('to_date', '')),
            'time_type': params.get('time_type', ''),
            'doctor_id': params.get('doctor_id', ''),
            'his_doc_id': params.get('his_doc_id', ''),
            'detlid': params.get('detlid'),
            'detlid_realtime': params.get('detlid_realtime'),
            'level_code': params.get('level_code'),
            'is_hot': '',
            'pay_online': '0',
            'detl_name': params.get('detl_name', ''),
            'to_date': params.get('to_date', params.get('sch_date', '')),
            'his_mem_id': ''
        }
        
        try:
            headers = self._build_submit_headers(
                data.get("unit_id"),
                data.get("dep_id"),
                data.get("schedule_id"),
            )
            r = self.session.post(url, data=data, headers=headers, allow_redirects=False)
            if r.status_code in [301, 302] and 'Location' in r.headers:
                redirect_url = r.headers['Location']
                # 如果跳转到 success 页面，说明成功
                if "success" in redirect_url:
                    return {'success': True, 'status': True, 'msg': 'OK', 'url': redirect_url}
                else:
                    return {'success': False, 'status': False, 'msg': f'提交异常跳转: {redirect_url}'}

            content_type = r.headers.get('Content-Type', '')
            content_encoding = r.headers.get('Content-Encoding', '')
            content_length = len(r.content or b'')
            text = r.text or ""
            if not text.strip() and r.content:
                try:
                    text = r.content.decode(r.encoding or "utf-8", errors="ignore")
                except Exception:
                    text = ""
            msg = self._extract_submit_message(text)
            if msg:
                self.last_error = msg
                return {'success': False, 'status': False, 'msg': f'提交失败: {msg}'}
            snippet = re.sub(r'[\x00-\x1f\x7f]+', ' ', text)
            snippet = re.sub(r'\s+', ' ', snippet).strip()[:200]
            if snippet:
                self.last_error = f"提交失败 Code={r.status_code}, Resp={snippet}"
                return {'success': False, 'status': False, 'msg': f'提交失败 Code={r.status_code}, Resp={snippet}'}
            debug_path = self._dump_submit_response(r.content)
            self.last_error = (
                "提交失败 "
                f"Code={r.status_code}, "
                f"Content-Type={content_type or '-'}, "
                f"Content-Encoding={content_encoding or '-'}, "
                f"Len={content_length}, "
                f"Debug={debug_path}"
            )
            return {'success': False, 'status': False, 'msg': self.last_error}
        except Exception as e:
            self.last_error = str(e)
            return {'success': False, 'status': False, 'msg': str(e)}

    def _extract_submit_message(self, text: str) -> str:
        if not text:
            return ""
        patterns = [
            r'alert\(["\']([^"\']+)["\']\)',
            r'layer\.msg\(["\']([^"\']+)["\']\)',
            r'layer\.alert\(["\']([^"\']+)["\']\)',
            r'msg\(["\']([^"\']+)["\']\)',
            r'toast\(["\']([^"\']+)["\']\)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        try:
            soup = BeautifulSoup(text, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            return title
        except Exception:
            return ""

    def _dump_submit_response(self, content: bytes) -> str:
        logs_dir = os.path.join(self.script_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        filename = f"submit_resp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
        path = os.path.join(logs_dir, filename)
        try:
            with open(path, "wb") as f:
                f.write(content or b"")
        except Exception:
            return path
        return path

    def _build_submit_headers(self, unit_id: str, dep_id: str, schedule_id: str) -> dict:
        headers = self.headers.copy()
        if unit_id and dep_id and schedule_id:
            referer_url = (
                "https://www.91160.com/guahao/ystep1/"
                f"uid-{unit_id}/depid-{dep_id}/schid-{schedule_id}.html"
            )
            headers["Referer"] = referer_url
        headers["Origin"] = "https://www.91160.com"
        headers["Connection"] = "keep-alive"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        cookie_header = self._build_submit_cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header
        return headers

    def _build_submit_cookie_header(self) -> str:
        user_cookies = []
        www_cookies = []
        root_cookies = []
        for c in self.session.cookies:
            domain = (getattr(c, "domain", "") or "").lower()
            if "user.91160.com" in domain:
                user_cookies.append(c)
            elif "www.91160.com" in domain:
                www_cookies.append(c)
            elif domain.endswith("91160.com") or domain == "":
                root_cookies.append(c)
        parts = []
        seen = set()
        for cookie in user_cookies + www_cookies + root_cookies:
            name = cookie.name
            if name in seen:
                continue
            seen.add(name)
            parts.append(f"{name}={cookie.value}")
        return "; ".join(parts)

    def get_server_datetime(self):
        """获取服务器时间（用于定时抢号校准）"""
        url = "https://www.91160.com/favicon.ico"
        try:
            r = self.session.get(url, timeout=5)
            date_header = r.headers.get('Date')
            if not date_header:
                return None
            dt = parsedate_to_datetime(date_header)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone()
        except Exception:
            return None

    def get_schedule(self, unit_id, dep_id, date=None):
        self.last_error = None
        self.last_status_code = None
        if not date: date = time.strftime("%Y-%m-%d")
        url = "https://gate.91160.com/guahao/v1/pc/sch/dep"
        
        # 自动提取唯一的 access_hash (如果有多个，取最新的)
        # requests.cookies 是 CookieJar，迭代它
        user_keys = []
        for c in self.session.cookies:
            if c.name == 'access_hash':
                user_keys.append(c.value)
        user_keys = list(set(user_keys))[-1:]  # 只保留最后一个有效 key，避免无效请求
        
        if not user_keys:
            self.last_error = "未登录或缺少 access_hash"
            print("[-] 没有 access_hash")
            return []

        # 尝试所有 key
        for key in user_keys:
            params = {
                "unit_id": unit_id,
                "dep_id": dep_id,
                "date": date,
                "p": 0,
                "user_key": key
            }
            # Gate 接口通常需要 Origin
            headers = self.headers.copy()
            headers['Origin'] = 'https://www.91160.com'
            headers['Referer'] = 'https://www.91160.com/'
            
            try:
                r = self.session.get(url, params=params, headers=headers, timeout=10)
                self.last_status_code = r.status_code
                if r.status_code != 200:
                    self.last_error = f"排班接口 HTTP {r.status_code}"
                    continue
                data = r.json()
                # print(f"[DEBUG] Try Key {key[:5]}... Code={data.get('result_code')}")
                
                if str(data.get('result_code')) == '1':
                    result_data = data.get('data', {})
                    doc_list = result_data.get('doc', [])
                    
                    # 调试：打印 result_data 的 keys
                    # print(f"[DEBUG] Keys in result_data: {list(result_data.keys())[:20]}")
                    
                    sch_data_map = result_data.get('sch', {})

                    # 遍历医生列表，填充排班信息
                    valid_docs = []
                    for doc in doc_list:
                        doc_id = str(doc.get('doctor_id'))
                        # 排班数据在 data['sch'][doc_id] 中
                        sch_map = sch_data_map.get(doc_id)
                        
                        if not sch_map: 
                             # print(f"[DEBUG] No sch_map for {doc_id}")
                             continue
                        
                        # 提取所有时段 (AM/PM)
                        schedules = []
                        for time_type in ['am', 'pm']:
                            type_data = sch_map.get(time_type, {})
                            # type_data 可能是 list (空时) 或 dict (有排班时)
                            if isinstance(type_data, dict):
                                for _, slot in type_data.items():
                                    # 必须有 schedule_id 且未约满 (y_state != 1 且 left_num > 0)
                                    # 注意: 有些情况 left_num=0 但 y_state_desc="可预约"，需综合判断
                                    # 这里先不过滤，全部拿回来让 main.py 决定如何显示
                                    if slot.get('schedule_id'):
                                        schedules.append(slot)
                            elif isinstance(type_data, list):
                                for slot in type_data:
                                    if slot.get('schedule_id'):
                                        schedules.append(slot)

                        if schedules:
                            doc['schedules'] = schedules
                            # 把第一个有效的 schedule_id 放到顶层以便兼容旧代码 (可选)
                            doc['schedule_id'] = schedules[0]['schedule_id']
                            doc['time_type_desc'] = schedules[0].get('time_type_desc', '')
                            # 计算总余号
                            total_left = sum(int(s.get('left_num', 0)) for s in schedules if str(s.get('left_num')).isdigit())
                            doc['total_left_num'] = total_left
                            valid_docs.append(doc)
                    
                    if valid_docs:
                        self.last_error = None
                        return valid_docs
                    
                    # 如果没有有效排班的医生，尝试继续(虽然后续key可能也一样)或直接返回空
                    # 但考虑到可能有缓存或Key差异，继续尝试下一个Key也没问题，
                    # 不过通常一个Key能拿到数据，其他Key拿到的也一样。
                    # 这里如果拿到doc_list但没拼出schedules，说明真没号。
                    if doc_list and not valid_docs:
                        print("[-] 获取到医生列表但无具体排班信息")
                        self.last_error = None
                        return []

                elif str(data.get('error_code')) == '10022':
                    self.last_error = "登录已过期或权限不足 (error_code=10022)"
                    continue # 尝试下一个
                else:
                    err_code = data.get('error_code') or data.get('result_code')
                    err_msg = (data.get('error_msg') or data.get('error_desc') or
                               data.get('msg') or data.get('message') or data.get('result_msg'))
                    self.last_error = f"排班接口返回异常: code={err_code} msg={err_msg}"
            except Exception as e:
                self.last_error = f"排班接口解析失败: {e}"
                print(f"[-] API Exception: {e}")
        
        print(f"[-] 排班查询失败 (Keys tested: {len(user_keys)})")
        if not self.last_error:
            self.last_error = "排班查询失败"
        return []


class CookieKeepAlive(threading.Thread):
    """
    Cookie 保活守护线程
    
    每隔一定时间检查 Session 有效性，
    如果失效则触发回调通知用户
    """
    
    def __init__(self, client: HealthClient, 
                 interval: int = 600,  # 默认 10 分钟
                 on_expired: callable = None):
        """
        初始化保活线程
        
        Args:
            client: HealthClient 实例
            interval: 检查间隔（秒），默认 600
            on_expired: Session 失效时的回调函数
        """
        super().__init__(daemon=True)
        self.client = client
        self.interval = interval
        self.on_expired = on_expired
        self.running = True
        self._last_check = time.time()
        self._consecutive_failures = 0
    
    def run(self):
        """守护线程主循环"""
        print(f"[+] Cookie 保活守护启动 (间隔: {self.interval}秒)")
        
        while self.running:
            time.sleep(self.interval)
            
            if not self.running:
                break
            
            try:
                is_valid = self.client.check_login()
                self._last_check = time.time()
                
                if is_valid:
                    self._consecutive_failures = 0
                    print(f"[*] Cookie 保活检查: 有效")
                else:
                    self._consecutive_failures += 1
                    print(f"[-] Cookie 保活检查: 失效 (连续失败: {self._consecutive_failures})")
                    
                    if self.on_expired:
                        self.on_expired()
                    
                    # 连续失败 3 次后降低检查频率
                    if self._consecutive_failures >= 3:
                        print("[!] Session 持续无效，等待用户重新登录")
                        time.sleep(self.interval * 2)
                        
            except Exception as e:
                print(f"[-] Cookie 保活检查异常: {e}")
    
    def stop(self):
        """停止守护线程"""
        self.running = False
        print("[*] Cookie 保活守护已停止")


def start_cookie_keepalive(client: HealthClient, 
                           on_expired: callable = None,
                           interval: int = 600) -> CookieKeepAlive:
    """
    启动 Cookie 保活守护线程
    
    Args:
        client: HealthClient 实例
        on_expired: Session 失效时的回调
        interval: 检查间隔（秒）
    
    Returns:
        CookieKeepAlive 线程实例
    """
    keepalive = CookieKeepAlive(client, interval, on_expired)
    keepalive.start()
    return keepalive
