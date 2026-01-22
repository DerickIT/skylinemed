import re

with open('pyside_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old block regex
# We look for def run_login(): ... up to threading.Thread(target=run_login, daemon=True).start()
# Since we know the exact lines from view_file, we can be specific or use a sentinel.

# Old block start:
start_marker = '        def run_login():'
# Old block end (inclusive):
end_marker = '        threading.Thread(target=run_login, daemon=True).start()'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find block")
    exit(1)

# Include the end marker in replacement (or append it back)
end_idx += len(end_marker)

new_code = '''        def run_login():
            # 使用同步的 FastQRLogin，避免 asyncio 环境问题
            from core.qr_login import FastQRLogin, QRLoginResult
            from PySide6.QtCore import QTimer
            
            # 使用列表作为可变引用传递停止标志
            stop_flag = [False]
            
            # 保存到 dialog 以便取消
            if self.qr_dialog:
                self.qr_dialog.stop_flag = stop_flag
            
            def on_qr(qr_bytes: bytes):
                self.signals.log.emit(f"收到二维码 ({len(qr_bytes)} bytes)", "#00D26A")
                self.signals.qr_image.emit(qr_bytes)
            
            def on_status(msg: str):
                self.signals.log.emit(f"登录状态: {msg}", "#AAAAAA")
                self.signals.qr_status.emit(msg)
            
            try:
                # 显式导入避免命名空间问题
                login = FastQRLogin()
                
                # 1. 获取二维码
                try:
                    on_status("正在获取二维码...")
                    qr_bytes, uuid = login.get_qr_image()
                    on_qr(qr_bytes)
                    on_status("请使用微信扫码")
                except Exception as e:
                    self.signals.qr_status.emit(f"获取二维码失败: {e}")
                    self.signals.log.emit(f"获取二维码失败: {e}", "#FF3B30")
                    self.signals.grab_finished.emit(False, str(e))
                    return

                # 2. 轮询状态
                try:
                    result = login.poll_status(
                        timeout_sec=300, 
                        on_status=on_status, 
                        stop_flag=stop_flag
                    )
                except Exception as e:
                    result = QRLoginResult(False, f"轮询异常: {e}")

                if result.success:
                    self.signals.log.emit(f"登录成功! Cookie已保存: {result.cookie_path}", "#00D26A")
                    self.signals.login_status.emit(True)
                    
                    # 重新加载就诊人
                    try:
                        self.client.load_cookies()
                        members = self.client.get_members()
                        self.signals.members_loaded.emit(members)
                    except Exception as e:
                        self.signals.log.emit(f"加载就诊人失败: {e}", "#FF9500")

                    # 关闭对话框
                    if self.qr_dialog:
                        QTimer.singleShot(500, self.qr_dialog.accept)
                    
                    self.signals.grab_finished.emit(True, "登录成功")
                else:
                    msg = result.message or "未知错误"
                    if msg != "已取消":
                        self.signals.log.emit(f"登录失败: {msg}", "#FF3B30")
                    self.signals.grab_finished.emit(False, msg)
                    
            except Exception as e:
                self.signals.log.emit(f"登录过程发生错误: {e}", "#FF3B30")
                import traceback
                traceback.print_exc()
                self.signals.grab_finished.emit(False, str(e))
        
        # 在新线程中运行同步登录逻辑
        threading.Thread(target=run_login, daemon=True).start()'''

new_content = content[:start_idx] + new_code + content[end_idx:]

with open('pyside_gui.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully patched pyside_gui.py")
