#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代理 IP 池管理模块
支持: API 获取代理、本地代理列表、代理轮换、失效检测
"""
import asyncio
import random
import time
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class ProxyInfo:
    """代理信息"""
    url: str                           # 代理地址 (http://ip:port)
    protocol: str = "http"             # 协议类型
    username: str = ""                 # 认证用户名
    password: str = ""                 # 认证密码
    
    success_count: int = 0             # 成功次数
    fail_count: int = 0                # 失败次数
    last_used: Optional[datetime] = None
    last_check: Optional[datetime] = None
    is_valid: bool = True
    
    @property
    def url_with_auth(self) -> str:
        """带认证信息的 URL"""
        if self.username and self.password:
            # http://user:pass@ip:port
            proto, rest = self.url.split("://", 1)
            return f"{proto}://{self.username}:{self.password}@{rest}"
        return self.url
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0


class ProxyPool:
    """
    代理 IP 池
    
    使用示例:
        pool = ProxyPool()
        pool.add_proxy("http://127.0.0.1:7890")
        # 或从 API 加载
        await pool.load_from_api("https://your-proxy-api.com/get?num=10")
        
        proxy = pool.get_proxy()
        # 使用后反馈
        pool.report_success(proxy)
        # 或
        pool.report_failure(proxy)
    """
    
    def __init__(
        self,
        api_url: str = None,
        local_proxies: List[str] = None,
        check_url: str = "https://www.91160.com/favicon.ico",
        check_timeout: float = 5.0
    ):
        """
        初始化代理池
        
        Args:
            api_url: 代理 API 地址
            local_proxies: 本地代理列表
            check_url: 用于检测代理有效性的 URL
            check_timeout: 检测超时时间
        """
        self.api_url = api_url
        self.check_url = check_url
        self.check_timeout = check_timeout
        
        self._proxies: Dict[str, ProxyInfo] = {}
        self._invalid: Set[str] = set()
        self._lock = asyncio.Lock()
        
        # 加载本地代理
        if local_proxies:
            for proxy in local_proxies:
                self.add_proxy(proxy)
    
    def add_proxy(self, proxy_url: str, username: str = "", password: str = ""):
        """添加代理"""
        if proxy_url not in self._proxies and proxy_url not in self._invalid:
            self._proxies[proxy_url] = ProxyInfo(
                url=proxy_url,
                username=username,
                password=password
            )
    
    def remove_proxy(self, proxy_url: str):
        """移除代理"""
        self._proxies.pop(proxy_url, None)
        self._invalid.discard(proxy_url)
    
    def get_proxy(self, prefer_high_success: bool = True) -> Optional[ProxyInfo]:
        """
        获取一个可用代理
        
        Args:
            prefer_high_success: 是否优先选择成功率高的代理
        
        Returns:
            代理信息，无可用代理时返回 None
        """
        valid_proxies = [p for p in self._proxies.values() if p.is_valid]
        
        if not valid_proxies:
            return None
        
        if prefer_high_success:
            # 按成功率排序，但加入随机性避免总是用同一个
            valid_proxies.sort(key=lambda p: p.success_rate, reverse=True)
            # 从前 30% 中随机选一个
            top_count = max(1, len(valid_proxies) // 3)
            selected = random.choice(valid_proxies[:top_count])
        else:
            selected = random.choice(valid_proxies)
        
        selected.last_used = datetime.now()
        return selected
    
    def get_random_proxy(self) -> Optional[ProxyInfo]:
        """随机获取一个代理"""
        return self.get_proxy(prefer_high_success=False)
    
    def report_success(self, proxy: ProxyInfo):
        """报告代理成功"""
        if proxy.url in self._proxies:
            self._proxies[proxy.url].success_count += 1
    
    def report_failure(self, proxy: ProxyInfo):
        """报告代理失败"""
        if proxy.url in self._proxies:
            self._proxies[proxy.url].fail_count += 1
            
            # 连续失败 3 次标记为无效
            if self._proxies[proxy.url].fail_count >= 3:
                self._proxies[proxy.url].is_valid = False
                print(f"[-] 代理失效: {proxy.url}")
    
    async def load_from_api(self, api_url: str = None, count: int = 10) -> int:
        """
        从 API 加载代理
        
        Args:
            api_url: API 地址，默认使用初始化时的地址
            count: 获取数量
        
        Returns:
            成功添加的代理数量
        """
        if not HTTPX_AVAILABLE:
            print("[-] httpx 未安装，无法调用代理 API")
            return 0
        
        url = api_url or self.api_url
        if not url:
            print("[-] 未配置代理 API 地址")
            return 0
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params={"num": count})
                
                # 尝试解析不同格式的响应
                added = 0
                
                # JSON 格式
                try:
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, str):
                                self.add_proxy(item)
                                added += 1
                            elif isinstance(item, dict):
                                ip = item.get('ip') or item.get('host')
                                port = item.get('port')
                                if ip and port:
                                    self.add_proxy(f"http://{ip}:{port}")
                                    added += 1
                    elif isinstance(data, dict):
                        proxies = data.get('data') or data.get('proxies') or data.get('list')
                        if proxies:
                            return await self.load_from_api_response(proxies)
                except:
                    pass
                
                # 纯文本格式 (每行一个)
                if added == 0:
                    lines = resp.text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if ':' in line:
                            if not line.startswith('http'):
                                line = f"http://{line}"
                            self.add_proxy(line)
                            added += 1
                
                print(f"[+] 从 API 加载了 {added} 个代理")
                return added
                
        except Exception as e:
            print(f"[-] 加载代理失败: {e}")
            return 0
    
    async def check_proxy(self, proxy: ProxyInfo) -> bool:
        """检测代理是否可用"""
        if not HTTPX_AVAILABLE:
            return True  # 无法检测时默认可用
        
        try:
            proxies = {"all://": proxy.url_with_auth}
            async with httpx.AsyncClient(proxies=proxies, timeout=self.check_timeout) as client:
                resp = await client.get(self.check_url)
                is_valid = resp.status_code == 200
                
                proxy.last_check = datetime.now()
                proxy.is_valid = is_valid
                
                return is_valid
        except:
            proxy.is_valid = False
            return False
    
    async def check_all(self) -> Dict[str, bool]:
        """检测所有代理"""
        results = {}
        tasks = []
        
        for proxy in self._proxies.values():
            tasks.append(self.check_proxy(proxy))
        
        if tasks:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            for proxy, result in zip(self._proxies.values(), check_results):
                results[proxy.url] = result if isinstance(result, bool) else False
        
        valid_count = sum(1 for r in results.values() if r)
        print(f"[*] 代理检测完成: {valid_count}/{len(results)} 可用")
        
        return results
    
    def get_stats(self) -> Dict:
        """获取代理池统计"""
        valid = sum(1 for p in self._proxies.values() if p.is_valid)
        return {
            'total': len(self._proxies),
            'valid': valid,
            'invalid': len(self._proxies) - valid,
            'proxies': [
                {
                    'url': p.url,
                    'is_valid': p.is_valid,
                    'success_rate': f"{p.success_rate:.1%}",
                    'success_count': p.success_count,
                    'fail_count': p.fail_count,
                }
                for p in self._proxies.values()
            ]
        }
    
    def clear_invalid(self):
        """清理无效代理"""
        to_remove = [url for url, p in self._proxies.items() if not p.is_valid]
        for url in to_remove:
            self._invalid.add(url)
            del self._proxies[url]
        print(f"[*] 清理了 {len(to_remove)} 个无效代理")
    
    @property
    def size(self) -> int:
        """代理池大小"""
        return len(self._proxies)
    
    @property
    def valid_size(self) -> int:
        """可用代理数量"""
        return sum(1 for p in self._proxies.values() if p.is_valid)


# 全局代理池
_pool: Optional[ProxyPool] = None


def get_proxy_pool() -> ProxyPool:
    """获取全局代理池"""
    global _pool
    if _pool is None:
        _pool = ProxyPool()
    return _pool


if __name__ == "__main__":
    # 测试代理池
    pool = ProxyPool()
    
    # 添加测试代理
    pool.add_proxy("http://127.0.0.1:7890")
    pool.add_proxy("http://127.0.0.1:1080")
    
    print(f"代理池统计: {pool.get_stats()}")
    
    proxy = pool.get_proxy()
    if proxy:
        print(f"获取代理: {proxy.url}")
        pool.report_success(proxy)
