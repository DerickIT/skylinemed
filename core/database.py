#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库模块 - SQLite 配置持久化
支持: 预设方案、多账号、抢号历史
"""
import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager


# 数据库文件路径
DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'grab91160.db')


class Database:
    """
    SQLite 数据库管理器
    
    表结构:
    - presets: 预设方案
    - accounts: 多账号管理
    - history: 抢号历史记录
    - settings: 全局设置
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """获取数据库连接 (上下文管理器)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 支持字典式访问
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 预设方案表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    config TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 账号表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cookies TEXT,
                    is_default INTEGER DEFAULT 0,
                    last_login TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 抢号历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_name TEXT,
                    unit_name TEXT,
                    dep_name TEXT,
                    doctor_name TEXT,
                    grab_date TEXT,
                    time_slot TEXT,
                    status TEXT,
                    result TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 全局设置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    # ==================== 预设方案 ====================
    
    def save_preset(self, name: str, config: Dict) -> bool:
        """
        保存预设方案
        
        Args:
            name: 方案名称
            config: 配置字典
        
        Returns:
            是否成功
        """
        try:
            config_json = json.dumps(config, ensure_ascii=False)
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO presets (name, config, updated_at)
                    VALUES (?, ?, ?)
                ''', (name, config_json, datetime.now().isoformat()))
            return True
        except Exception as e:
            print(f"[-] 保存预设失败: {e}")
            return False
    
    def load_preset(self, name: str) -> Optional[Dict]:
        """加载预设方案"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT config FROM presets WHERE name = ?', (name,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row['config'])
        except Exception as e:
            print(f"[-] 加载预设失败: {e}")
        return None
    
    def list_presets(self) -> List[Dict]:
        """列出所有预设方案"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT name, created_at, updated_at FROM presets ORDER BY updated_at DESC')
                return [dict(row) for row in cursor.fetchall()]
        except:
            return []
    
    def delete_preset(self, name: str) -> bool:
        """删除预设方案"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM presets WHERE name = ?', (name,))
            return True
        except:
            return False
    
    # ==================== 账号管理 ====================
    
    def save_account(self, name: str, cookies: Dict, is_default: bool = False) -> bool:
        """保存账号"""
        try:
            cookies_json = json.dumps(cookies, ensure_ascii=False)
            with self._get_conn() as conn:
                cursor = conn.cursor()
                
                # 如果设为默认，先取消其他默认
                if is_default:
                    cursor.execute('UPDATE accounts SET is_default = 0')
                
                cursor.execute('''
                    INSERT OR REPLACE INTO accounts (name, cookies, is_default, last_login)
                    VALUES (?, ?, ?, ?)
                ''', (name, cookies_json, 1 if is_default else 0, datetime.now().isoformat()))
            return True
        except Exception as e:
            print(f"[-] 保存账号失败: {e}")
            return False
    
    def load_account(self, name: str) -> Optional[Dict]:
        """加载账号"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT cookies FROM accounts WHERE name = ?', (name,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row['cookies'])
        except:
            pass
        return None
    
    def get_default_account(self) -> Optional[Dict]:
        """获取默认账号"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT name, cookies FROM accounts WHERE is_default = 1')
                row = cursor.fetchone()
                if row:
                    return {
                        'name': row['name'],
                        'cookies': json.loads(row['cookies'])
                    }
        except:
            pass
        return None
    
    def list_accounts(self) -> List[Dict]:
        """列出所有账号"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT name, is_default, last_login FROM accounts ORDER BY is_default DESC')
                return [dict(row) for row in cursor.fetchall()]
        except:
            return []
    
    def delete_account(self, name: str) -> bool:
        """删除账号"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM accounts WHERE name = ?', (name,))
            return True
        except:
            return False
    
    # ==================== 抢号历史 ====================
    
    def save_history(self, member_name: str, unit_name: str, dep_name: str,
                     doctor_name: str, grab_date: str, time_slot: str,
                     status: str, result: str = None) -> bool:
        """保存抢号历史"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO history 
                    (member_name, unit_name, dep_name, doctor_name, grab_date, time_slot, status, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (member_name, unit_name, dep_name, doctor_name, grab_date, time_slot, status, result))
            return True
        except Exception as e:
            print(f"[-] 保存历史失败: {e}")
            return False
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取抢号历史"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM history ORDER BY created_at DESC LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except:
            return []
    
    def get_success_count(self) -> int:
        """获取成功抢号次数"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM history WHERE status = 'success'")
                return cursor.fetchone()[0]
        except:
            return 0
    
    # ==================== 全局设置 ====================
    
    def set_setting(self, key: str, value: Any) -> bool:
        """设置全局配置"""
        try:
            value_json = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (key, value_json, datetime.now().isoformat()))
            return True
        except:
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取全局配置"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row['value'])
                    except:
                        return row['value']
        except:
            pass
        return default


# 全局数据库实例
_db: Optional[Database] = None


def get_db() -> Database:
    """获取全局数据库实例"""
    global _db
    if _db is None:
        _db = Database()
    return _db


if __name__ == "__main__":
    # 测试数据库
    db = Database()
    
    # 测试预设
    print("=== 测试预设方案 ===")
    db.save_preset("测试方案", {
        "unit_id": "123",
        "dep_id": "456",
        "member_id": "789"
    })
    print(f"预设列表: {db.list_presets()}")
    print(f"加载预设: {db.load_preset('测试方案')}")
    
    # 测试历史
    print("\n=== 测试抢号历史 ===")
    db.save_history("张三", "人民医院", "内科", "王医生", "2026-01-29", "09:00-09:30", "success")
    print(f"历史记录: {db.get_history()}")
    print(f"成功次数: {db.get_success_count()}")
    
    print(f"\n数据库位置: {DB_PATH}")
