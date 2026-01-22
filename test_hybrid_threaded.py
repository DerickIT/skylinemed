#!/usr/bin/env python
# test_hybrid_threaded.py
from curl_cffi import requests as cffi_requests
import httpx
import re
import time
import threading

def run_login_logic():
    print(f"Thread {threading.current_thread().name}: Starting...")
    
    print("1. Using curl_cffi to get UUID...")
    session = cffi_requests.Session(impersonate='chrome')
    uuid = None
    try:
        url = 'https://open.weixin.qq.com/connect/qrconnect?appid=wxdfec0615563d691d&redirect_uri=http%3A%2F%2Fuser.91160.com%2Fsupplier-wechat.html&response_type=code&scope=snsapi_login&state=hybrid_thread'
        resp = session.get(url)
        print(f"Login page status: {resp.status_code}")
        
        match = re.search(r'/connect/qrcode/([a-zA-Z0-9]+)', resp.text)
        if not match:
            print("FAILED to find UUID")
            return
            
        uuid = match.group(1)
        print(f"UUID: {uuid}")
        
    finally:
        session.close()
        
    print("\n2. Using httpx to poll status...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://open.weixin.qq.com/"
    }
    
    client = httpx.Client(timeout=30, headers=headers)
    try:
        for i in range(3):
            ts = int(time.time() * 1000)
            poll_url = f'https://lp.open.weixin.qq.com/connect/l/qrconnect?uuid={uuid}&_={ts}'
            print(f"Polling {i+1}: {poll_url}")
            try:
                resp = client.get(poll_url)
                print(f"Response: {resp.status_code}")
                print(f"Body: {resp.text[:100]}")
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(1)
    finally:
        client.close()

def main():
    print("Main: Starting thread...")
    t = threading.Thread(target=run_login_logic)
    t.start()
    t.join()
    print("Main: Thread finished.")

if __name__ == "__main__":
    main()
