#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OTA 自动更新模块
支持: 版本检查、补丁下载、热更新
"""
import os
import json
import shutil
import hashlib
import zipfile
import tempfile
from typing import Optional, Dict, Tuple
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# 版本信息
CURRENT_VERSION = "1.0.0"
VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'version.json')


class AutoUpdater:
    """
    OTA 自动更新器
    
    更新服务器应提供:
    - /update.json: 版本信息
    - /patches/v{version}.zip: 补丁包
    
    update.json 格式:
    {
        "latest_version": "1.1.0",
        "min_version": "1.0.0",
        "release_notes": "修复了xxx问题",
        "patch_url": "https://your-server/patches/v1.1.0.zip",
        "patch_hash": "sha256:xxx",
        "force_update": false
    }
    """
    
    def __init__(
        self,
        update_url: str = None,
        current_version: str = None,
        app_dir: str = None
    ):
        """
        初始化更新器
        
        Args:
            update_url: 更新检查 URL
            current_version: 当前版本号
            app_dir: 应用目录
        """
        self.update_url = update_url
        self.current_version = current_version or self._load_version()
        self.app_dir = app_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self._backup_dir = os.path.join(self.app_dir, '.backup')
        self._temp_dir = tempfile.gettempdir()
    
    def _load_version(self) -> str:
        """加载本地版本"""
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('version', CURRENT_VERSION)
            except:
                pass
        return CURRENT_VERSION
    
    def _save_version(self, version: str):
        """保存版本信息"""
        data = {
            'version': version,
            'updated_at': datetime.now().isoformat()
        }
        with open(VERSION_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """
        比较版本号
        
        Returns:
            -1: v1 < v2
             0: v1 == v2
             1: v1 > v2
        """
        def parse(v):
            return [int(x) for x in v.split('.')]
        
        p1, p2 = parse(v1), parse(v2)
        
        for a, b in zip(p1, p2):
            if a < b:
                return -1
            if a > b:
                return 1
        
        if len(p1) < len(p2):
            return -1
        if len(p1) > len(p2):
            return 1
        
        return 0
    
    async def check_update_async(self) -> Optional[Dict]:
        """异步检查更新"""
        if not self.update_url:
            return None
        
        if not HTTPX_AVAILABLE:
            return self.check_update_sync()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self.update_url)
                data = resp.json()
                
                latest = data.get('latest_version', '')
                if self._compare_versions(self.current_version, latest) < 0:
                    return {
                        'has_update': True,
                        'current_version': self.current_version,
                        'latest_version': latest,
                        'release_notes': data.get('release_notes', ''),
                        'patch_url': data.get('patch_url', ''),
                        'patch_hash': data.get('patch_hash', ''),
                        'force_update': data.get('force_update', False),
                    }
                
                return {'has_update': False}
                
        except Exception as e:
            print(f"[-] 检查更新失败: {e}")
            return None
    
    def check_update_sync(self) -> Optional[Dict]:
        """同步检查更新"""
        if not self.update_url:
            return None
        
        if not REQUESTS_AVAILABLE:
            print("[-] requests 未安装，无法检查更新")
            return None
        
        try:
            resp = requests.get(self.update_url, timeout=10)
            data = resp.json()
            
            latest = data.get('latest_version', '')
            if self._compare_versions(self.current_version, latest) < 0:
                return {
                    'has_update': True,
                    'current_version': self.current_version,
                    'latest_version': latest,
                    'release_notes': data.get('release_notes', ''),
                    'patch_url': data.get('patch_url', ''),
                    'patch_hash': data.get('patch_hash', ''),
                    'force_update': data.get('force_update', False),
                }
            
            return {'has_update': False}
            
        except Exception as e:
            print(f"[-] 检查更新失败: {e}")
            return None
    
    def check_update(self) -> Optional[Dict]:
        """检查更新 (同步版本)"""
        return self.check_update_sync()
    
    async def download_patch_async(self, patch_url: str, expected_hash: str = None) -> Optional[str]:
        """异步下载补丁"""
        if not HTTPX_AVAILABLE:
            return self.download_patch_sync(patch_url, expected_hash)
        
        patch_path = os.path.join(self._temp_dir, 'patch.zip')
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                print(f"[*] 下载补丁: {patch_url}")
                resp = await client.get(patch_url)
                
                with open(patch_path, 'wb') as f:
                    f.write(resp.content)
                
                # 验证哈希
                if expected_hash:
                    if not self._verify_hash(patch_path, expected_hash):
                        print("[-] 补丁校验失败")
                        os.remove(patch_path)
                        return None
                
                print(f"[+] 补丁下载完成: {patch_path}")
                return patch_path
                
        except Exception as e:
            print(f"[-] 下载补丁失败: {e}")
            return None
    
    def download_patch_sync(self, patch_url: str, expected_hash: str = None) -> Optional[str]:
        """同步下载补丁"""
        if not REQUESTS_AVAILABLE:
            return None
        
        patch_path = os.path.join(self._temp_dir, 'patch.zip')
        
        try:
            print(f"[*] 下载补丁: {patch_url}")
            resp = requests.get(patch_url, timeout=60, stream=True)
            
            with open(patch_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 验证哈希
            if expected_hash:
                if not self._verify_hash(patch_path, expected_hash):
                    print("[-] 补丁校验失败")
                    os.remove(patch_path)
                    return None
            
            print(f"[+] 补丁下载完成: {patch_path}")
            return patch_path
            
        except Exception as e:
            print(f"[-] 下载补丁失败: {e}")
            return None
    
    def _verify_hash(self, file_path: str, expected: str) -> bool:
        """验证文件哈希"""
        if ':' in expected:
            algo, hash_value = expected.split(':', 1)
        else:
            algo, hash_value = 'sha256', expected
        
        hasher = hashlib.new(algo)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        
        return hasher.hexdigest() == hash_value
    
    def backup(self) -> bool:
        """备份当前版本"""
        try:
            if os.path.exists(self._backup_dir):
                shutil.rmtree(self._backup_dir)
            
            os.makedirs(self._backup_dir, exist_ok=True)
            
            # 备份 core 目录
            core_dir = os.path.join(self.app_dir, 'core')
            if os.path.exists(core_dir):
                shutil.copytree(core_dir, os.path.join(self._backup_dir, 'core'))
            
            print(f"[+] 已备份到: {self._backup_dir}")
            return True
            
        except Exception as e:
            print(f"[-] 备份失败: {e}")
            return False
    
    def restore(self) -> bool:
        """恢复备份"""
        try:
            if not os.path.exists(self._backup_dir):
                print("[-] 没有可恢复的备份")
                return False
            
            # 恢复 core 目录
            backup_core = os.path.join(self._backup_dir, 'core')
            if os.path.exists(backup_core):
                target_core = os.path.join(self.app_dir, 'core')
                if os.path.exists(target_core):
                    shutil.rmtree(target_core)
                shutil.copytree(backup_core, target_core)
            
            print("[+] 已恢复备份")
            return True
            
        except Exception as e:
            print(f"[-] 恢复失败: {e}")
            return False
    
    def apply_patch(self, patch_path: str) -> bool:
        """应用补丁"""
        if not os.path.exists(patch_path):
            print("[-] 补丁文件不存在")
            return False
        
        try:
            # 先备份
            if not self.backup():
                return False
            
            # 解压补丁
            print("[*] 应用补丁...")
            with zipfile.ZipFile(patch_path, 'r') as zf:
                zf.extractall(self.app_dir)
            
            print("[+] 补丁应用成功")
            return True
            
        except Exception as e:
            print(f"[-] 应用补丁失败: {e}")
            print("[*] 尝试恢复备份...")
            self.restore()
            return False
    
    async def update_async(self) -> Tuple[bool, str]:
        """执行完整更新流程 (异步)"""
        # 检查更新
        update_info = await self.check_update_async()
        if not update_info:
            return False, "检查更新失败"
        
        if not update_info.get('has_update'):
            return False, "已是最新版本"
        
        new_version = update_info['latest_version']
        print(f"[*] 发现新版本: {new_version}")
        print(f"    更新说明: {update_info.get('release_notes', '')}")
        
        # 下载补丁
        patch_url = update_info.get('patch_url')
        if not patch_url:
            return False, "未找到补丁下载地址"
        
        patch_path = await self.download_patch_async(
            patch_url,
            update_info.get('patch_hash')
        )
        if not patch_path:
            return False, "下载补丁失败"
        
        # 应用补丁
        if not self.apply_patch(patch_path):
            return False, "应用补丁失败"
        
        # 更新版本号
        self._save_version(new_version)
        self.current_version = new_version
        
        # 清理
        try:
            os.remove(patch_path)
        except:
            pass
        
        return True, f"已更新到版本 {new_version}"
    
    def update(self) -> Tuple[bool, str]:
        """执行完整更新流程 (同步)"""
        # 检查更新
        update_info = self.check_update_sync()
        if not update_info:
            return False, "检查更新失败"
        
        if not update_info.get('has_update'):
            return False, "已是最新版本"
        
        new_version = update_info['latest_version']
        print(f"[*] 发现新版本: {new_version}")
        
        # 下载补丁
        patch_url = update_info.get('patch_url')
        if not patch_url:
            return False, "未找到补丁下载地址"
        
        patch_path = self.download_patch_sync(
            patch_url,
            update_info.get('patch_hash')
        )
        if not patch_path:
            return False, "下载补丁失败"
        
        # 应用补丁
        if not self.apply_patch(patch_path):
            return False, "应用补丁失败"
        
        # 更新版本号
        self._save_version(new_version)
        self.current_version = new_version
        
        return True, f"已更新到版本 {new_version}"


# 全局更新器
_updater: Optional[AutoUpdater] = None


def get_updater(update_url: str = None) -> AutoUpdater:
    """获取全局更新器"""
    global _updater
    if _updater is None:
        _updater = AutoUpdater(update_url=update_url)
    return _updater


def check_update_on_startup(update_url: str = None) -> Optional[Dict]:
    """
    启动时检查更新 (便捷函数)
    
    Returns:
        更新信息，无更新时返回 None
    """
    updater = get_updater(update_url)
    result = updater.check_update()
    
    if result and result.get('has_update'):
        print("\n" + "=" * 50)
        print(f"🚀 发现新版本: {result['latest_version']}")
        print(f"   当前版本: {result['current_version']}")
        if result.get('release_notes'):
            print(f"   更新说明: {result['release_notes']}")
        print("=" * 50 + "\n")
        return result
    
    return None


if __name__ == "__main__":
    print(f"当前版本: {CURRENT_VERSION}")
    
    # 测试版本比较
    print("\n版本比较测试:")
    print(f"  1.0.0 vs 1.0.1: {AutoUpdater._compare_versions('1.0.0', '1.0.1')}")
    print(f"  1.1.0 vs 1.0.1: {AutoUpdater._compare_versions('1.1.0', '1.0.1')}")
    print(f"  1.0.0 vs 1.0.0: {AutoUpdater._compare_versions('1.0.0', '1.0.0')}")
