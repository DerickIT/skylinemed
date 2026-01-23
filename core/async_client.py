#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
异步高并发 HTTP 客户端 - 基于 httpx
支持并发查询多个日期/医生的排班信息
"""
import httpx
import asyncio
import json
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Any


class AsyncHealthClient:
    """异步高并发健康160客户端"""
    
    BASE_URL = "https://www.91160.com"
    GATE_URL = "https://gate.91160.com"
    
    def __init__(self, max_concurrency: int = 10):
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.cookies = {}
        self.access_hash = None
        
        # 使用脚本所在目录的绝对路径
        self.script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cookie_file = os.path.join(self.script_dir, 'cookies.json')
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.91160.com/',
            'Origin': 'https://www.91160.com'
        }
    
    async def load_cookies(self) -> bool:
        """加载本地 Cookie"""
        if not os.path.exists(self.cookie_file):
            return False
        
        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookies_list = json.load(f)
            
            if isinstance(cookies_list, list):
                for cookie in cookies_list:
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    self.cookies[name] = value
                    if name == 'access_hash':
                        self.access_hash = value
            else:
                self.cookies = cookies_list
                self.access_hash = cookies_list.get('access_hash')
            
            print(f"[+] 异步客户端: 加载了 {len(self.cookies)} 个 Cookie")
            return True
        except Exception as e:
            print(f"[-] 加载 Cookie 失败: {e}")
            return False
    
    def _get_client(self) -> httpx.AsyncClient:
        """创建带 Cookie 的异步客户端"""
        return httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=10.0,
            follow_redirects=True
        )
    
    async def get_schedule(self, unit_id: str, dep_id: str, date: str) -> List[Dict]:
        """获取单个日期的排班（带并发限制）"""
        async with self.semaphore:
            return await self._get_schedule_impl(unit_id, dep_id, date)
    
    async def _get_schedule_impl(self, unit_id: str, dep_id: str, date: str) -> List[Dict]:
        """排班查询实现"""
        url = f"{self.GATE_URL}/guahao/v1/pc/sch/dep"
        
        if not self.access_hash:
            print("[-] 没有 access_hash")
            return []
        
        params = {
            "unit_id": unit_id,
            "dep_id": dep_id,
            "date": date,
            "p": 0,
            "user_key": self.access_hash
        }
        
        try:
            async with self._get_client() as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                
                if str(data.get('result_code')) != '1':
                    return []
                
                result_data = data.get('data', {})
                doc_list = result_data.get('doc', [])
                sch_data_map = result_data.get('sch', {})
                
                valid_docs = []
                for doc in doc_list:
                    doc_id = str(doc.get('doctor_id'))
                    sch_map = sch_data_map.get(doc_id)
                    
                    if not sch_map:
                        continue
                    
                    schedules = []
                    for time_type in ['am', 'pm']:
                        type_data = sch_map.get(time_type, {})
                        if isinstance(type_data, dict):
                            for _, slot in type_data.items():
                                if slot.get('schedule_id'):
                                    slot['query_date'] = date
                                    schedules.append(slot)
                        elif isinstance(type_data, list):
                            for slot in type_data:
                                if slot.get('schedule_id'):
                                    slot['query_date'] = date
                                    schedules.append(slot)
                    
                    if schedules:
                        doc['schedules'] = schedules
                        doc['schedule_id'] = schedules[0]['schedule_id']
                        doc['query_date'] = date
                        total_left = sum(int(s.get('left_num', 0)) for s in schedules 
                                        if str(s.get('left_num')).isdigit())
                        doc['total_left_num'] = total_left
                        valid_docs.append(doc)
                
                return valid_docs
                
        except Exception as e:
            print(f"[-] 查询 {date} 排班失败: {e}")
            return []
    
    async def get_schedule_batch(self, unit_id: str, dep_id: str, dates: List[str]) -> List[Dict]:
        """并发查询多个日期的排班"""
        tasks = [self.get_schedule(unit_id, dep_id, d) for d in dates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_docs = []
        for result in results:
            if isinstance(result, list):
                all_docs.extend(result)
            elif isinstance(result, Exception):
                print(f"[-] 批量查询异常: {result}")
        
        return all_docs
    
    async def get_ticket_detail(self, unit_id: str, dep_id: str, sch_id: str) -> Optional[Dict]:
        """获取号源详情"""
        url = f"{self.BASE_URL}/guahao/ystep1/uid-{unit_id}/depid-{dep_id}/schid-{sch_id}.html"
        
        try:
            async with self._get_client() as client:
                resp = await client.get(url)
                html = resp.text
                
                # 简化解析（生产环境建议用 BeautifulSoup）
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # 提取时间段
                delts_div = soup.find(id='delts')
                time_slots = []
                if delts_div:
                    for li in delts_div.find_all('li'):
                        text = li.get_text(strip=True)
                        val = li.get('val')
                        if val:
                            time_slots.append({'name': text, 'value': val})
                
                # 提取隐藏参数
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
                
                return {
                    'times': time_slots,
                    'time_slots': time_slots,
                    'sch_data': sch_data.get('value') if sch_data else '',
                    'detlid_realtime': detlid_realtime.get('value') if detlid_realtime else '',
                    'level_code': level_code.get('value') if level_code else '',
                    'addressId': address_id,
                    'address': address_text,
                    'addresses': address_list
                }
        except Exception as e:
            print(f"[-] 获取号源详情失败: {e}")
            return None
    
    async def submit_order(self, params: Dict) -> Dict:
        """异步提交订单"""
        url = f"{self.BASE_URL}/guahao/ysubmit.html"
        
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
            async with self._get_client() as client:
                headers = self._build_submit_headers(
                    params.get("unit_id"),
                    params.get("dep_id"),
                    params.get("schedule_id"),
                )
                resp = await client.post(url, data=data, headers=headers, follow_redirects=False)
                
                if resp.status_code in [301, 302]:
                    redirect_url = resp.headers.get('Location', '')
                    if 'success' in redirect_url:
                        return {'success': True, 'status': True, 'msg': 'OK', 'url': redirect_url}
                    else:
                        return {'success': False, 'status': False, 'msg': f'跳转异常: {redirect_url}'}

                content_type = resp.headers.get('Content-Type', '')
                content_encoding = resp.headers.get('Content-Encoding', '')
                content_length = len(resp.content or b'')
                text = resp.text or ""
                if not text.strip() and resp.content:
                    try:
                        text = resp.content.decode(resp.encoding or "utf-8", errors="ignore")
                    except Exception:
                        text = ""
                msg = self._extract_submit_message(text)
                if msg:
                    return {'success': False, 'status': False, 'msg': f'提交失败: {msg}'}
                snippet = re.sub(r'[\x00-\x1f\x7f]+', ' ', text)
                snippet = re.sub(r'\s+', ' ', snippet).strip()[:200]
                if snippet:
                    return {'success': False, 'status': False, 'msg': f'提交失败 Code={resp.status_code}, Resp={snippet}'}
                debug_path = self._dump_submit_response(resp.content)
                return {
                    'success': False,
                    'status': False,
                    'msg': (
                        "提交失败 "
                        f"Code={resp.status_code}, "
                        f"Content-Type={content_type or '-'}, "
                        f"Content-Encoding={content_encoding or '-'}, "
                        f"Len={content_length}, "
                        f"Debug={debug_path}"
                    ),
                }
        except Exception as e:
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
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            return title
        except Exception:
            return ""

    def _dump_submit_response(self, content: bytes) -> str:
        logs_dir = os.path.join(self.script_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        filename = f"submit_resp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
        path = os.path.join(logs_dir, filename)
        try:
            with open(path, "wb") as f:
                f.write(content or b"")
        except Exception:
            return path
        return path

    def _build_submit_headers(self, unit_id: str, dep_id: str, schedule_id: str) -> Dict:
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
        parts = []
        seen = set()
        for name, value in (self.cookies or {}).items():
            if name in seen:
                continue
            seen.add(name)
            parts.append(f"{name}={value}")
        return "; ".join(parts)
    
    async def get_server_time(self) -> Optional[datetime]:
        """获取服务器时间（用于时间校准）"""
        url = f"{self.BASE_URL}/favicon.ico"
        
        try:
            async with self._get_client() as client:
                resp = await client.get(url)
                date_header = resp.headers.get('Date')
                
                if date_header:
                    from email.utils import parsedate_to_datetime
                    import datetime as dt
                    server_dt = parsedate_to_datetime(date_header)
                    if server_dt.tzinfo is None:
                        server_dt = server_dt.replace(tzinfo=dt.timezone.utc)
                    return server_dt.astimezone()
        except Exception as e:
            print(f"[-] 获取服务器时间失败: {e}")
        
        return None


async def test_concurrency():
    """并发性能测试"""
    client = AsyncHealthClient(max_concurrency=5)
    await client.load_cookies()
    
    if not client.access_hash:
        print("[-] 请先登录获取 Cookie")
        return
    
    # 测试并发查询 7 天
    from datetime import timedelta
    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
    print(f"[*] 测试并发查询 {len(dates)} 天排班...")
    start = time.time()
    
    # 这里需要真实的 unit_id 和 dep_id
    # results = await client.get_schedule_batch("xxx", "xxx", dates)
    
    elapsed = time.time() - start
    print(f"[+] 完成，耗时: {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(test_concurrency())
