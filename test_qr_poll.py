#!/usr/bin/env python
# test_qr_poll.py - 测试二维码轮询
from curl_cffi import requests
import re
import time

# 使用 Chrome 浏览器指纹
session = requests.Session(impersonate="chrome")

# 获取登录页
url = 'https://open.weixin.qq.com/connect/qrconnect?appid=wxdfec0615563d691d&redirect_uri=http%3A%2F%2Fuser.91160.com%2Fsupplier-wechat.html&response_type=code&scope=snsapi_login&state=test123'
resp = session.get(url)
print(f'页面响应: {resp.status_code}')
print(f'Cookies: {dict(session.cookies)}')

match = re.search(r'/connect/qrcode/([a-zA-Z0-9]+)', resp.text)
if match:
    uuid = match.group(1)
    print(f'UUID: {uuid}')
    
    # 获取二维码图片
    qr_url = f'https://open.weixin.qq.com/connect/qrcode/{uuid}'
    qr_resp = session.get(qr_url)
    print(f'QR 响应: {qr_resp.status_code}')
    
    # 轮询状态
    print('\n开始轮询...')
    for i in range(5):
        ts = int(time.time() * 1000)
        poll_url = f'https://lp.open.weixin.qq.com/connect/l/qrconnect?uuid={uuid}&_={ts}'
        poll_resp = session.get(poll_url, timeout=35)
        
        errcode_match = re.search(r'wx_errcode\s*=\s*(\d+)', poll_resp.text)
        errcode = errcode_match.group(1) if errcode_match else 'none'
        print(f'第{i+1}次轮询: errcode={errcode}, 响应长度={len(poll_resp.text)}')
        print(f'  响应内容: {poll_resp.text[:100]}')
        time.sleep(2)
else:
    print('未找到 UUID')

session.close()
