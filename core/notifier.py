#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多通道通知模块 - 抢号成功后多渠道提醒
支持: 声音、微信(Server酱/PushPlus)、钉钉、桌面通知
"""
import os
import json
import threading
from typing import Optional, Dict, Callable
from datetime import datetime

# 可选依赖
try:
    from playsound import playsound
    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Windows 桌面通知
try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False


class NotifyConfig:
    """通知配置"""
    
    def __init__(self, config_path: str = "notify_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "sound": {
                "enabled": True,
                "file": "alert.wav"  # 警报音文件
            },
            "wechat": {
                "enabled": False,
                "type": "serverchan",  # serverchan 或 pushplus
                "key": ""  # Server酱 SendKey 或 PushPlus Token
            },
            "dingtalk": {
                "enabled": False,
                "webhook": "",  # 钉钉机器人 Webhook URL
                "secret": ""    # 加签密钥 (可选)
            },
            "desktop": {
                "enabled": True
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 合并用户配置
                    for key in default_config:
                        if key in user_config:
                            default_config[key].update(user_config[key])
            except:
                pass
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)


class Notifier:
    """
    多通道通知器
    
    使用示例:
        notifier = Notifier()
        notifier.notify("抢号成功!", "张三 - 人民医院 内科 2026-01-29")
    """
    
    def __init__(self, config: Optional[NotifyConfig] = None):
        self.config = config or NotifyConfig()
        self._callbacks: list[Callable] = []
    
    def add_callback(self, callback: Callable[[str, str], None]):
        """添加自定义回调"""
        self._callbacks.append(callback)
    
    def notify(self, title: str, message: str, level: str = "success"):
        """
        发送多通道通知
        
        Args:
            title: 标题
            message: 消息内容
            level: 级别 (success, warning, error)
        """
        print(f"\n{'='*50}")
        print(f"[NOTIFY] {title}")
        print(f"[NOTIFY] {message}")
        print(f"{'='*50}\n")
        
        # 声音通知
        if self.config.config["sound"]["enabled"]:
            self._notify_sound()
        
        # 桌面通知
        if self.config.config["desktop"]["enabled"]:
            self._notify_desktop(title, message)
        
        # 微信通知
        if self.config.config["wechat"]["enabled"]:
            threading.Thread(
                target=self._notify_wechat,
                args=(title, message)
            ).start()
        
        # 钉钉通知
        if self.config.config["dingtalk"]["enabled"]:
            threading.Thread(
                target=self._notify_dingtalk,
                args=(title, message)
            ).start()
        
        # 自定义回调
        for callback in self._callbacks:
            try:
                callback(title, message)
            except:
                pass
    
    def _notify_sound(self):
        """播放警报音"""
        if not PLAYSOUND_AVAILABLE:
            print("[!] playsound 未安装，跳过声音通知")
            return
        
        sound_file = self.config.config["sound"]["file"]
        
        # 如果没有自定义音频，使用系统蜂鸣
        if not os.path.exists(sound_file):
            try:
                import winsound
                # 播放 3 次蜂鸣
                for _ in range(3):
                    winsound.Beep(1000, 500)  # 1000Hz, 500ms
            except:
                print("\a" * 3)  # 终端蜂鸣
            return
        
        try:
            # 在后台线程播放
            threading.Thread(target=playsound, args=(sound_file,)).start()
        except Exception as e:
            print(f"[-] 播放声音失败: {e}")
    
    def _notify_desktop(self, title: str, message: str):
        """Windows 桌面通知"""
        if TOAST_AVAILABLE:
            try:
                toaster = ToastNotifier()
                toaster.show_toast(
                    title, 
                    message,
                    duration=10,
                    threaded=True
                )
            except:
                pass
        else:
            # 尝试使用 PowerShell 显示通知
            try:
                import subprocess
                ps_cmd = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $textNodes = $template.GetElementsByTagName("text")
                $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
                $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("91160抢号助手").Show($toast)
                '''
                subprocess.run(
                    ["powershell", "-Command", ps_cmd],
                    capture_output=True,
                    timeout=5
                )
            except:
                pass
    
    def _notify_wechat(self, title: str, message: str):
        """微信推送 (Server酱 / PushPlus)"""
        if not REQUESTS_AVAILABLE:
            return
        
        wechat_config = self.config.config["wechat"]
        key = wechat_config.get("key", "")
        if not key:
            return
        
        try:
            notify_type = wechat_config.get("type", "serverchan")
            
            if notify_type == "serverchan":
                # Server酱 (https://sct.ftqq.com/)
                url = f"https://sctapi.ftqq.com/{key}.send"
                data = {
                    "title": title,
                    "desp": message
                }
                requests.post(url, data=data, timeout=10)
                print("[+] Server酱推送成功")
                
            elif notify_type == "pushplus":
                # PushPlus (https://www.pushplus.plus/)
                url = "http://www.pushplus.plus/send"
                data = {
                    "token": key,
                    "title": title,
                    "content": message,
                    "template": "txt"
                }
                requests.post(url, json=data, timeout=10)
                print("[+] PushPlus推送成功")
                
        except Exception as e:
            print(f"[-] 微信推送失败: {e}")
    
    def _notify_dingtalk(self, title: str, message: str):
        """钉钉机器人推送"""
        if not REQUESTS_AVAILABLE:
            return
        
        dingtalk_config = self.config.config["dingtalk"]
        webhook = dingtalk_config.get("webhook", "")
        if not webhook:
            return
        
        try:
            import time
            import hmac
            import hashlib
            import base64
            import urllib.parse
            
            # 如果配置了加签
            secret = dingtalk_config.get("secret", "")
            if secret:
                timestamp = str(round(time.time() * 1000))
                secret_enc = secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{secret}'
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(
                    secret_enc, 
                    string_to_sign_enc, 
                    digestmod=hashlib.sha256
                ).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"
            
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"## {title}\n\n{message}\n\n---\n*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
                }
            }
            
            resp = requests.post(webhook, json=data, timeout=10)
            if resp.json().get("errcode") == 0:
                print("[+] 钉钉推送成功")
            else:
                print(f"[-] 钉钉推送失败: {resp.text}")
                
        except Exception as e:
            print(f"[-] 钉钉推送失败: {e}")
    
    def test_all_channels(self):
        """测试所有通知渠道"""
        print("=== 通知渠道测试 ===\n")
        self.notify(
            "测试通知",
            "这是一条测试消息，如果你能看到这条消息说明通知配置正确。"
        )


# 全局通知器实例
_notifier: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """获取全局通知器"""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier


def notify_success(member_name: str, unit_name: str, dep_name: str, 
                   doctor_name: str, date: str, time_slot: str):
    """抢号成功通知（便捷函数）"""
    notifier = get_notifier()
    
    title = f"🎉 抢号成功！"
    message = f"""
就诊人: {member_name}
医院: {unit_name}
科室: {dep_name}
医生: {doctor_name}
日期: {date}
时段: {time_slot}

请尽快完成支付！
    """.strip()
    
    notifier.notify(title, message, level="success")


if __name__ == "__main__":
    # 测试通知
    notifier = Notifier()
    notifier.test_all_channels()
