#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多任务管理器 - 支持多账号多任务并发
实现"多卡多待"场景
"""
import threading
import asyncio
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime

from .logger import get_logger
from .database import get_db
from .notifier import get_notifier, notify_success


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 待开始
    WAITING = "waiting"      # 等待定时
    RUNNING = "running"      # 运行中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    STOPPED = "stopped"      # 已停止
    PAUSED = "paused"        # 已暂停


@dataclass
class GrabTask:
    """抢号任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    
    # 配置
    member_id: str = ""
    member_name: str = ""
    unit_id: str = ""
    unit_name: str = ""
    dep_id: str = ""
    dep_name: str = ""
    doctor_ids: List[str] = field(default_factory=list)
    target_dates: List[str] = field(default_factory=list)
    preferred_hours: List[str] = field(default_factory=list)
    start_time: str = ""  # 定时启动 HH:MM:SS
    
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    last_error: str = ""
    result: Dict = field(default_factory=dict)
    
    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    # 内部
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'member_name': self.member_name,
            'unit_name': self.unit_name,
            'dep_name': self.dep_name,
            'target_dates': self.target_dates,
            'start_time': self.start_time,
            'status': self.status.value,
            'attempts': self.attempts,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
        }
    
    @classmethod
    def from_config(cls, config: Dict) -> 'GrabTask':
        """从配置创建任务"""
        return cls(
            name=config.get('name', f"任务-{config.get('member_name', 'Unknown')}"),
            member_id=str(config.get('member_id', '')),
            member_name=config.get('member_name', ''),
            unit_id=str(config.get('unit_id', '')),
            unit_name=config.get('unit_name', ''),
            dep_id=str(config.get('dep_id', '')),
            dep_name=config.get('dep_name', ''),
            doctor_ids=[str(d) for d in config.get('doctor_ids', [])],
            target_dates=config.get('target_dates', []),
            preferred_hours=config.get('preferred_hours', []),
            start_time=config.get('start_time', ''),
        )
    
    def to_config(self) -> Dict:
        """转换为配置字典"""
        return {
            'member_id': self.member_id,
            'member_name': self.member_name,
            'unit_id': self.unit_id,
            'unit_name': self.unit_name,
            'dep_id': self.dep_id,
            'dep_name': self.dep_name,
            'doctor_ids': self.doctor_ids,
            'target_dates': self.target_dates,
            'preferred_hours': self.preferred_hours,
            'start_time': self.start_time,
        }


class TaskManager:
    """
    多任务管理器
    
    支持:
    - 添加/删除任务
    - 启动/停止单个任务
    - 批量启动/停止
    - 任务状态监控
    
    使用示例:
        manager = TaskManager(client)
        task = manager.add_task(config)
        manager.start_task(task.id)
    """
    
    def __init__(self, client_factory: Callable = None, max_concurrent: int = 5):
        """
        初始化任务管理器
        
        Args:
            client_factory: 客户端工厂函数，用于创建 HealthClient 实例
            max_concurrent: 最大并发任务数
        """
        self.client_factory = client_factory
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, GrabTask] = {}
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable]] = {
            'on_start': [],
            'on_finish': [],
            'on_success': [],
            'on_error': [],
            'on_update': [],
        }
        self.logger = get_logger()
    
    def add_callback(self, event: str, callback: Callable):
        """添加事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, task: GrabTask, *args):
        """触发事件"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(task, *args)
            except Exception as e:
                self.logger.error(f"回调执行失败: {e}")
    
    def add_task(self, config: Dict) -> GrabTask:
        """添加任务"""
        task = GrabTask.from_config(config)
        with self._lock:
            self.tasks[task.id] = task
        self.logger.info(f"任务添加: [{task.id}] {task.name}")
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == TaskStatus.RUNNING:
                    self.stop_task(task_id)
                del self.tasks[task_id]
                self.logger.info(f"任务删除: [{task_id}]")
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[GrabTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[GrabTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_running_count(self) -> int:
        """获取正在运行的任务数"""
        return sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING)
    
    def start_task(self, task_id: str) -> bool:
        """启动任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status == TaskStatus.RUNNING:
            self.logger.warning(f"任务已在运行: [{task_id}]")
            return False
        
        if self.get_running_count() >= self.max_concurrent:
            self.logger.warning(f"已达最大并发数 ({self.max_concurrent})，任务排队中")
            task.status = TaskStatus.PENDING
            return False
        
        # 重置状态
        task._stop_event.clear()
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.attempts = 0
        task.last_error = ""
        
        # 启动线程
        task._thread = threading.Thread(
            target=self._run_task,
            args=(task,),
            daemon=True,
            name=f"GrabTask-{task_id}"
        )
        task._thread.start()
        
        self.logger.info(f"任务启动: [{task_id}] {task.name}")
        self._emit('on_start', task)
        return True
    
    def stop_task(self, task_id: str) -> bool:
        """停止任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.RUNNING:
            return False
        
        task._stop_event.set()
        task.status = TaskStatus.STOPPED
        task.finished_at = datetime.now()
        
        self.logger.info(f"任务停止: [{task_id}]")
        self._emit('on_finish', task)
        return True
    
    def start_all(self):
        """启动所有待开始的任务"""
        for task_id, task in self.tasks.items():
            if task.status in [TaskStatus.PENDING, TaskStatus.STOPPED]:
                self.start_task(task_id)
    
    def stop_all(self):
        """停止所有运行中的任务"""
        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.RUNNING:
                self.stop_task(task_id)
    
    def _run_task(self, task: GrabTask):
        """任务执行线程"""
        try:
            # 创建客户端
            if self.client_factory:
                client = self.client_factory()
            else:
                from .client import HealthClient
                client = HealthClient()
            
            # 等待定时
            if task.start_time:
                task.status = TaskStatus.WAITING
                self._emit('on_update', task)
                self._wait_until(task.start_time, task._stop_event)
                
                if task._stop_event.is_set():
                    return
                
                task.status = TaskStatus.RUNNING
                self._emit('on_update', task)
            
            # 抢号循环
            config = task.to_config()
            retry_interval = 0.5
            max_retries = 0  # 0 = 无限
            
            while not task._stop_event.is_set():
                task.attempts += 1
                
                success, result = self._grab_once(client, config, task)
                
                if success:
                    task.status = TaskStatus.SUCCESS
                    task.result = result
                    task.finished_at = datetime.now()
                    
                    # 保存历史
                    get_db().save_history(
                        member_name=task.member_name,
                        unit_name=task.unit_name,
                        dep_name=task.dep_name,
                        doctor_name=result.get('doctor_name', ''),
                        grab_date=result.get('date', ''),
                        time_slot=result.get('time_slot', ''),
                        status='success'
                    )
                    
                    # 通知
                    notify_success(
                        member_name=task.member_name,
                        unit_name=task.unit_name,
                        dep_name=task.dep_name,
                        doctor_name=result.get('doctor_name', ''),
                        date=result.get('date', ''),
                        time_slot=result.get('time_slot', '')
                    )
                    
                    self._emit('on_success', task, result)
                    break
                
                if max_retries > 0 and task.attempts >= max_retries:
                    task.status = TaskStatus.FAILED
                    task.last_error = "达到最大重试次数"
                    break
                
                self._emit('on_update', task)
                time.sleep(retry_interval)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.last_error = str(e)
            self.logger.error(f"任务异常: [{task.id}] {e}")
            self._emit('on_error', task, e)
        
        finally:
            task.finished_at = datetime.now()
            self._emit('on_finish', task)
    
    def _grab_once(self, client, config: Dict, task: GrabTask) -> tuple:
        """执行一次抢号尝试"""
        try:
            from .grab import grab
            success = grab(config, client)
            return success, config if success else {}
        except Exception as e:
            task.last_error = str(e)
            return False, {}
    
    def _wait_until(self, target_time_str: str, stop_event: threading.Event):
        """等待到指定时间"""
        from datetime import datetime as dt
        
        try:
            target_parts = dt.strptime(target_time_str, "%H:%M:%S")
            now = dt.now()
            target = now.replace(
                hour=target_parts.hour,
                minute=target_parts.minute,
                second=target_parts.second,
                microsecond=0
            )
            
            if target <= now:
                return
            
            while dt.now() < target:
                if stop_event.is_set():
                    return
                time.sleep(1)
        except:
            pass
    
    def get_status_summary(self) -> Dict:
        """获取任务状态汇总"""
        summary = {
            'total': len(self.tasks),
            'pending': 0,
            'running': 0,
            'success': 0,
            'failed': 0,
            'stopped': 0,
        }
        
        for task in self.tasks.values():
            status_key = task.status.value
            if status_key in summary:
                summary[status_key] += 1
        
        return summary


# 全局任务管理器
_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器"""
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager


if __name__ == "__main__":
    # 测试任务管理器
    from .client import HealthClient
    
    manager = TaskManager(client_factory=HealthClient)
    
    # 添加测试任务
    task = manager.add_task({
        'name': '测试任务',
        'member_id': '123',
        'member_name': '张三',
        'unit_id': '456',
        'unit_name': '人民医院',
        'dep_id': '789',
        'dep_name': '内科',
        'target_dates': ['2026-01-29'],
    })
    
    print(f"任务列表: {[t.to_dict() for t in manager.get_all_tasks()]}")
    print(f"状态汇总: {manager.get_status_summary()}")
