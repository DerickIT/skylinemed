#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TLS 指纹伪造客户端 - 使用 curl_cffi 模拟真实浏览器
绕过 Cloudflare/阿里云 WAF 的 TLS 指纹检测
"""
import json
import os
import time
import hashlib
import random
import string
from datetime import datetime
from typing import List, Dict, Optional, Any

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("[!] curl_cffi 未安装，TLS 指纹伪造不可用")
    print("[!] 安装命令: pip install curl_cffi")

from bs4 import BeautifulSoup


class TLSHealthClient:
    """
    TLS 指纹伪造客户端
    
    使用 curl_cffi 模拟 Chrome/Safari 的真实 TLS 握手特征
    可绕过基于 JA3 指纹的 WAF 检测
    """
    
    # 支持的浏览器指纹
    IMPERSONATE_OPTIONS = [
        "chrome120",
        "chrome119", 
        "chrome110",
        "safari17_0",
        "safari15_5",
        "edge101"
    ]
    
    def __init__(self, impersonate: str = "chrome120"):
        """
        初始化 TLS 客户端
        
        Args:
            impersonate: 模拟的浏览器类型，默认 chrome120
        """
        if not CURL_CFFI_AVAILABLE:
            raise ImportError("curl_cffi 未安装，请运行: pip install curl_cffi")
        
        self.impersonate = impersonate
        self.session = curl_requests.Session(impersonate=impersonate)
        
        # 使用脚本所在目录
        self.script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cookie_file = os.path.join(self.script_dir, 'cookies.json')
        
        self.headers = {
            'User-Agent': self._get_ua_for_impersonate(),
            'Referer': 'https://www.91160.com/',
            'Origin': 'https://www.91160.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.session.headers.update(self.headers)
        
        self.access_hash = None
        
        if self.load_cookies():
            print(f"[+] TLS客户端初始化成功 (指纹: {impersonate})")
    
    def _get_ua_for_impersonate(self) -> str:
        """根据模拟类型返回匹配的 User-Agent"""
        ua_map = {
            "chrome120": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "chrome119": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "chrome110": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "safari17_0": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "safari15_5": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
            "edge101": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.53",
        }
        return ua_map.get(self.impersonate, ua_map["chrome120"])
    
    def load_cookies(self) -> bool:
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
                    self.session.cookies.set(name, value)
                    if name == 'access_hash':
                        self.access_hash = value
            else:
                for name, value in cookies_list.items():
                    self.session.cookies.set(name, value)
                self.access_hash = cookies_list.get('access_hash')
            
            return True
        except Exception as e:
            print(f"[-] 加载 Cookie 失败: {e}")
            return False
    
    def check_login(self) -> bool:
        """检查登录状态"""
        if not self.access_hash:
            return False
        
        try:
            r = self.session.get(
                "https://user.91160.com/user/index.html",
                allow_redirects=False,
                timeout=10
            )
            return r.status_code == 200
        except Exception:
            return False
    
    def get_hospitals_by_city(self, city_id: str = "5") -> List[Dict]:
        """获取医院列表"""
        url = "https://www.91160.com/ajax/getunitbycity.html"
        try:
            r = self.session.post(url, data={"c": city_id})
            return r.json()
        except:
            return []
    
    def get_deps_by_unit(self, unit_id: str) -> List[Dict]:
        """获取科室列表"""
        url = "https://www.91160.com/ajax/getdepbyunit.html"
        try:
            r = self.session.post(url, data={"keyValue": unit_id})
            return r.json()
        except:
            return []
    
    def get_members(self) -> List[Dict]:
        """获取就诊人列表"""
        url = "https://user.91160.com/member.html"
        try:
            r = self.session.get(url)
            
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
                    is_certified = any("认证" in td.text for td in tds)
                    members.append({
                        'id': mid,
                        'name': name,
                        'certified': is_certified
                    })
            
            return members
        except Exception as e:
            print(f"[-] 获取就诊人失败: {e}")
            return []
    
    def get_schedule(self, unit_id: str, dep_id: str, date: str = None) -> List[Dict]:
        """获取排班信息"""
        if not date:
            date = time.strftime("%Y-%m-%d")
        
        url = "https://gate.91160.com/guahao/v1/pc/sch/dep"
        
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
            r = self.session.get(url, params=params)
            data = r.json()
            
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
                                schedules.append(slot)
                    elif isinstance(type_data, list):
                        for slot in type_data:
                            if slot.get('schedule_id'):
                                schedules.append(slot)
                
                if schedules:
                    doc['schedules'] = schedules
                    doc['schedule_id'] = schedules[0]['schedule_id']
                    total_left = sum(int(s.get('left_num', 0)) for s in schedules 
                                    if str(s.get('left_num')).isdigit())
                    doc['total_left_num'] = total_left
                    valid_docs.append(doc)
            
            return valid_docs
            
        except Exception as e:
            print(f"[-] 排班查询失败: {e}")
            return []
    
    def get_ticket_detail(self, unit_id: str, dep_id: str, sch_id: str) -> Optional[Dict]:
        """获取号源详情"""
        url = f"https://www.91160.com/guahao/ystep1/uid-{unit_id}/depid-{dep_id}/schid-{sch_id}.html"
        
        try:
            r = self.session.get(url)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            delts_div = soup.find(id='delts')
            time_slots = []
            if delts_div:
                for li in delts_div.find_all('li'):
                    text = li.get_text(strip=True)
                    val = li.get('val')
                    if val:
                        time_slots.append({'name': text, 'value': val})
            
            sch_data = soup.find('input', {'name': 'sch_data'})
            detlid_realtime = soup.find(id='detlid_realtime')
            level_code = soup.find(id='level_code')
            
            return {
                'times': time_slots,
                'time_slots': time_slots,
                'sch_data': sch_data.get('value') if sch_data else '',
                'detlid_realtime': detlid_realtime.get('value') if detlid_realtime else '',
                'level_code': level_code.get('value') if level_code else ''
            }
        except Exception as e:
            print(f"[-] 获取号源详情失败: {e}")
            return None
    
    def submit_order(self, params: Dict) -> Dict:
        """提交订单"""
        url = "https://www.91160.com/guahao/ysubmit.html"
        
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
            r = self.session.post(url, data=data, allow_redirects=False)
            
            if r.status_code in [301, 302]:
                redirect_url = r.headers.get('Location', '')
                if 'success' in redirect_url:
                    return {'success': True, 'status': True, 'msg': 'OK', 'url': redirect_url}
                else:
                    return {'success': False, 'status': False, 'msg': f'跳转异常: {redirect_url}'}
            else:
                return {'success': False, 'status': False, 'msg': f'Code={r.status_code}'}
        except Exception as e:
            return {'success': False, 'status': False, 'msg': str(e)}
    
    def get_server_datetime(self) -> Optional[datetime]:
        """获取服务器时间"""
        url = "https://www.91160.com/favicon.ico"
        try:
            r = self.session.get(url, timeout=5)
            date_header = r.headers.get('Date')
            if date_header:
                from email.utils import parsedate_to_datetime
                import datetime as dt
                server_dt = parsedate_to_datetime(date_header)
                if server_dt.tzinfo is None:
                    server_dt = server_dt.replace(tzinfo=dt.timezone.utc)
                return server_dt.astimezone()
        except:
            pass
        return None
    
    def rotate_fingerprint(self):
        """切换浏览器指纹（用于规避检测）"""
        new_impersonate = random.choice(self.IMPERSONATE_OPTIONS)
        self.impersonate = new_impersonate
        self.session = curl_requests.Session(impersonate=new_impersonate)
        self.session.headers.update(self.headers)
        self.headers['User-Agent'] = self._get_ua_for_impersonate()
        self.load_cookies()
        print(f"[*] 切换指纹: {new_impersonate}")


def test_tls_client():
    """测试 TLS 客户端"""
    print("=== TLS 指纹客户端测试 ===\n")
    
    try:
        client = TLSHealthClient(impersonate="chrome120")
    except ImportError as e:
        print(f"[-] {e}")
        return
    
    if client.check_login():
        print("[+] 登录状态: 有效")
        members = client.get_members()
        print(f"[+] 就诊人: {len(members)} 位")
    else:
        print("[-] 登录状态: 无效，请重新扫码登录")


if __name__ == "__main__":
    test_tls_client()
