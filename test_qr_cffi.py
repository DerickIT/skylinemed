#!/usr/bin/env python
# test_qr_cffi.py - 使用 curl_cffi 模拟浏览器测试
from curl_cffi import requests
import re

# 使用 Chrome 浏览器指纹
session = requests.Session(impersonate="chrome")

# 获取登录页
url = 'https://open.weixin.qq.com/connect/qrconnect?appid=wxdfec0615563d691d&redirect_uri=http%3A%2F%2Fuser.91160.com%2Fsupplier-wechat.html&response_type=code&scope=snsapi_login&state=test123'
resp = session.get(url)
print('页面响应:', resp.status_code)

# 从 HTML 中提取二维码路径
# 格式: src="/connect/qrcode/0817tD4Y21bN0w3p"
match = re.search(r'/connect/qrcode/([a-zA-Z0-9]+)', resp.text)
if match:
    uuid = match.group(1)
    print(f'UUID: {uuid}')
    
    # 获取二维码图片 - 需要完整 URL
    qr_url = f'https://open.weixin.qq.com/connect/qrcode/{uuid}'
    qr_resp = session.get(qr_url)
    print(f'QR 响应: {qr_resp.status_code}, 类型: {qr_resp.headers.get("content-type")}')
    print(f'内容长度: {len(qr_resp.content)} bytes')
    print(f'内容前10字节: {qr_resp.content[:10]}')
    
    # 检查是否是图片
    if qr_resp.content[:4] == b'\x89PNG' or qr_resp.content[:2] == b'\xff\xd8':
        print('✓ 成功获取到图片!')
        with open('test_qr_cffi.jpg', 'wb') as f:
            f.write(qr_resp.content)
        print('已保存到 test_qr_cffi.jpg')
    else:
        print('✗ 不是图片格式')
        print('前100字节:', qr_resp.content[:100])
else:
    print('未找到 UUID')
    # 保存 HTML 以便调试
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(resp.text)
    print('已保存页面到 debug_page.html')

session.close()
