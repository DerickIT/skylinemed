#!/usr/bin/env python
# test_hybrid.py
from curl_cffi import requests as cffi_requests
import httpx
import re
import time

def test():
    print("1. Using curl_cffi to get UUID...")
    session = cffi_requests.Session(impersonate='chrome')
    try:
        url = 'https://open.weixin.qq.com/connect/qrconnect?appid=wxdfec0615563d691d&redirect_uri=http%3A%2F%2Fuser.91160.com%2Fsupplier-wechat.html&response_type=code&scope=snsapi_login&state=hybrid_test'
        resp = session.get(url)
        print(f"Login page status: {resp.status_code}")
        
        match = re.search(r'/connect/qrcode/([a-zA-Z0-9]+)', resp.text)
        if not match:
            print("FAILED to find UUID")
            return
            
        uuid = match.group(1)
        print(f"UUID: {uuid}")
        
    finally:
        session.close() # Close cffi session immediately
        
    print("\n2. Using httpx to poll status...")
    client = httpx.Client(timeout=30)
    
    # Needs headers? Browser inspection said Referer might be needed.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://open.weixin.qq.com/"
    }
    
    for i in range(3):
        ts = int(time.time() * 1000)
        poll_url = f'https://lp.open.weixin.qq.com/connect/l/qrconnect?uuid={uuid}&_={ts}'
        print(f"Polling {i+1}...")
        try:
            resp = client.get(poll_url, headers=headers)
            print(f"Response: {resp.status_code}")
            print(f"Body: {resp.text[:100]}")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    test()
