#!/usr/bin/env python
# test_qr.py - 测试二维码获取
import httpx
import re

client = httpx.Client(timeout=30, follow_redirects=True, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# 先获取登录页
url = 'https://open.weixin.qq.com/connect/qrconnect?appid=wxdfec0615563d691d&redirect_uri=http%3A%2F%2Fuser.91160.com%2Fsupplier-wechat.html&response_type=code&scope=snsapi_login&state=test123'
resp = client.get(url)
print('页面响应:', resp.status_code)

match = re.search(r'uuid\s*=\s*["\']([^"\']+)["\']', resp.text)
if match:
    uuid = match.group(1)
    print(f'UUID: {uuid}')
    
    # 获取二维码图片
    qr_url = f'https://open.weixin.qq.com/connect/qrcode/{uuid}'
    qr_resp = client.get(qr_url)
    print(f'QR 响应: {qr_resp.status_code}, 类型: {qr_resp.headers.get("content-type")}')
    print(f'内容长度: {len(qr_resp.content)} bytes')
    print(f'内容前20字节: {qr_resp.content[:20]}')
    
    # 保存测试
    with open('test_qr_real.jpg', 'wb') as f:
        f.write(qr_resp.content)
    print('已保存到 test_qr_real.jpg')
else:
    print('未找到 UUID')
    print(resp.text[:500])

client.close()
