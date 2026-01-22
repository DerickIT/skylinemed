#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速二维码登录 - 混合方案 (Hybrid Approach)
1. 使用 curl_cffi 模拟 Chrome 获取 UUID 和二维码（绕过反爬）
2. 使用 curl_cffi 进行轮询（保持指纹一致）
3. 增加 404/402 容错重试机制
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from urllib.parse import quote
from dataclasses import dataclass
from typing import Callable, Optional

# 导入两个库
from curl_cffi import requests as cffi_requests


@dataclass
class QRLoginResult:
    success: bool
    message: str
    cookie_path: Optional[str] = None


def _cookie_path() -> str:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, "cookies.json")


def _extract_cookie_list(cookies) -> list:
    """提取 cookie 列表，避免同名不同域导致的异常"""
    if isinstance(cookies, list):
        cookie_list = []
        for item in cookies:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if not name:
                continue
            cookie_list.append({
                "name": name,
                "value": value,
                "domain": item.get("domain") or ".91160.com",
                "path": item.get("path") or "/"
            })
        return cookie_list

    if isinstance(cookies, dict):
        return [
            {"name": k, "value": v, "domain": ".91160.com", "path": "/"}
            for k, v in cookies.items()
        ]

    cookie_list = []
    try:
        iterable = cookies.jar
    except Exception:
        iterable = cookies
    for c in iterable:
        try:
            name = c.name
            value = c.value
        except Exception:
            continue
        domain = getattr(c, "domain", None) or ".91160.com"
        path = getattr(c, "path", None) or "/"
        cookie_list.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path
        })
    return cookie_list


def _save_cookies(cookies) -> str:
    """保存 cookies 为列表格式"""
    path = _cookie_path()
    cookie_list = _extract_cookie_list(cookies)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookie_list, f, ensure_ascii=False, indent=2)
    return path


class FastQRLogin:
    APPID = "wxdfec0615563d691d"
    REDIRECT_URI = "http://user.91160.com/supplier-wechat.html"
    
    def __init__(self):
        self.uuid = None
        self.cookies = {}
        self.state = None
    
    def get_qr_image(self) -> tuple[bytes, str]:
        """
        使用 curl_cffi 获取二维码
        """
        # 使用 Chrome 浏览器指纹，绕过反爬
        session = cffi_requests.Session(impersonate="chrome")
        try:
            self.state = f"login_{int(time.time())}"
            encoded_redirect = quote(self.REDIRECT_URI, safe="")
            url = (
                f"https://open.weixin.qq.com/connect/qrconnect"
                f"?appid={self.APPID}"
                f"&redirect_uri={encoded_redirect}"
                f"&response_type=code"
                f"&scope=snsapi_login"
                f"&state={self.state}"
                f"#wechat_redirect"
            )
            
            resp = session.get(url)
            resp.raise_for_status()
            self.cookies = dict(session.cookies)
            
            # 從 HTML 提取 UUID
            match = re.search(r'/connect/qrcode/([a-zA-Z0-9_-]+)', resp.text)
            if not match:
                raise ValueError("无法获取二维码 UUID")
            
            self.uuid = match.group(1)
            print(f"[QR] 获取 UUID: {self.uuid}")
            
            # 获取图片
            qr_url = f"https://open.weixin.qq.com/connect/qrcode/{self.uuid}"
            qr_resp = session.get(qr_url)
            qr_resp.raise_for_status()
            self.cookies.update(dict(session.cookies))
            
            # 简单验证
            if qr_resp.content[:2] != b'\xff\xd8' and qr_resp.content[:4] != b'\x89PNG':
                raise ValueError("返回的不是图片格式")
                
            return qr_resp.content, self.uuid
            
        finally:
            session.close()
            
    def poll_status(self, timeout_sec=300, on_status=None, stop_flag=None) -> QRLoginResult:
        """
        使用 curl_cffi 进行轮询
        """
        if not self.uuid:
            return QRLoginResult(False, "UUID 未初始化")
            
        # 标准 headers，带 Referer
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://open.weixin.qq.com/"
        }

        session = cffi_requests.Session(impersonate="chrome")
        session.headers.update(headers)
        if self.cookies:
            session.cookies.update(self.cookies)

        try:
            start_time = time.time()
            last_status = ""
            last_param = "404"
            retry_404_count = 0

            while True:
                # 检查取消
                if stop_flag and stop_flag[0]:
                    return QRLoginResult(False, "已取消")

                if time.time() - start_time > timeout_sec:
                    return QRLoginResult(False, "二维码已过期")

                ts = int(time.time() * 1000)
                poll_url = (
                    f"https://lp.open.weixin.qq.com/connect/l/qrconnect"
                    f"?uuid={self.uuid}&last={last_param}&_={ts}"
                )

                try:
                    resp = session.get(poll_url, timeout=35)
                    text = resp.text

                    # 解析
                    errcode_match = re.search(r'wx_errcode\s*=\s*(\d+)', text)
                    code_match = re.search(r'wx_code\s*=\s*[\'"]([^\'"]*)[\'"]', text)
                    url_match = re.search(
                        r'window\.location(?:\.href|\.replace)?\s*\(?[\'"]([^\'"]+)[\'"]\)?',
                        text
                    )

                    status = errcode_match.group(1) if errcode_match else "0"
                    code = code_match.group(1) if code_match else None
                    if status == "0" and (code or url_match):
                        status = "405"
                    if status in {"408", "201", "405", "402", "404"}:
                        last_param = status

                    print(f"[QR] 轮询: {status}")

                    if status == "408":  # 等待扫码
                        if last_status != "408":
                            if on_status: on_status("等待扫码...")
                            last_status = "408"
                        retry_404_count = 0

                    elif status == "404" or status == "402":
                        # 404 可能是暂时的（如用户抓包所示），不要立即退出
                        retry_404_count += 1
                        print(f"[QR] 404/402 响应 (重试 {retry_404_count}): {text[:50]}")
                        last_status = "404"
                        if retry_404_count > 60:  # 连续 1 分钟 404 才放弃
                            return QRLoginResult(False, "二维码已过期/不存在")
                        time.sleep(1)
                        continue

                    elif status == "201":  # 已扫码
                        if last_status != "201":
                            if on_status: on_status("已扫码，请在手机上确认")
                            last_status = "201"
                        retry_404_count = 0

                    elif status == "405":  # 登录成功
                        if not code and url_match:
                            redirect_url = url_match.group(1)
                            code_match2 = re.search(r'[?&]code=([^&]+)', redirect_url)
                            state_match2 = re.search(r'[?&]state=([^&]+)', redirect_url)
                            if state_match2:
                                self.state = state_match2.group(1)
                            if code_match2:
                                code = code_match2.group(1)
                        if not code:
                            if on_status: on_status("已确认，但未获取到登录 code，继续重试...")
                            time.sleep(1)
                            continue
                        if on_status: on_status("正在登录...")
                        return self._exchange_cookie(code)

                except Exception as e:
                    print(f"[QR] 网络错误: {e}")
                    time.sleep(2)

                time.sleep(1)

        finally:
            session.close()

    def _exchange_cookie(self, code: str) -> QRLoginResult:
        """
        使用 curl_cffi 换取 Cookie
        """
        session = cffi_requests.Session(impersonate="chrome")
        try:
            state = self.state or ""
            if state:
                callback_url = f"{self.REDIRECT_URI}?code={code}&state={state}"
            else:
                callback_url = f"{self.REDIRECT_URI}?code={code}"
            print(f"[QR] 换取 Cookie: {callback_url}")
            
            # 清除 cookies
            session.cookies.clear()
            
            # 1. 访问回调 (会自动处理 302/307 跳转)
            resp = session.get(callback_url, allow_redirects=True)
            print(f"[QR] 回调响应: {resp.status_code}, URL: {resp.url}")

            # 2. 访问主页确保 cookie 设置
            session.get("https://www.91160.com/", allow_redirects=True)
            session.get("https://user.91160.com/user/index.html", allow_redirects=True)
            
            cookie_list = _extract_cookie_list(session.cookies)
            print(f"[QR] 获取 Cookies: {len(cookie_list)} 个")

            if not cookie_list:
                return QRLoginResult(False, "未获取到有效 Cookie")
            if not any(c.get("name") == "access_hash" for c in cookie_list):
                return QRLoginResult(False, "登录未完成：缺少 access_hash")

            path = _save_cookies(cookie_list)
            return QRLoginResult(True, "登录成功", cookie_path=path)
            
        except Exception as e:
            print(f"[QR] Cookie交换异常: {e}")
            return QRLoginResult(False, f"登录失败: {e}")
        finally:
            session.close()


# 异步包装器（保留以兼容旧代码，但在 GUI 中已直接使用同步类）
async def run_qr_login(
    on_qr: Callable[[bytes], None],
    on_status: Optional[Callable[[str], None]],
    cancel_event: asyncio.Event,
    timeout_sec: int = 300,
    headless: bool = True,
) -> QRLoginResult:
    """
    异步入口：在线程池中运行同步逻辑
    """
    login = FastQRLogin()
    stop_flag = [False]
    
    # 监控取消
    async def watch_cancel():
        await cancel_event.wait()
        stop_flag[0] = True
        
    watcher = asyncio.create_task(watch_cancel())
    
    def _run():
        # 1. 获取二维码
        try:
            qr_bytes, uuid = login.get_qr_image()
            on_qr(qr_bytes)
        except Exception as e:
            return QRLoginResult(False, f"获取二维码失败: {e}")
            
        if on_status: on_status("请使用微信扫码")
        
        # 2. 轮询
        return login.poll_status(timeout_sec, on_status, stop_flag)
        
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)
    finally:
        watcher.cancel()
