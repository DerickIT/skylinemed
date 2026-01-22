#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志模块 - 持久化日志记录
支持文件轮转、控制台输出、自定义格式
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from typing import Optional


# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器 (仅终端)"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_message = super().format(record)
        color = self.COLORS.get(record.levelname, self.RESET)
        return f"{color}{log_message}{self.RESET}"


def setup_logger(
    name: str = "grab91160",
    log_file: str = "app.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    配置日志器
    
    Args:
        name: 日志器名称
        log_file: 日志文件名
        level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        console_output: 是否输出到控制台
    
    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 日志格式
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_format = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 文件处理器 (轮转)
    log_path = os.path.join(LOG_DIR, log_file)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # 控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    return logger


def setup_grab_logger(task_id: str = None) -> logging.Logger:
    """
    配置抢号专用日志器
    
    Args:
        task_id: 任务ID (用于区分多任务日志)
    
    Returns:
        Logger 实例
    """
    if task_id:
        log_file = f"grab_{task_id}.log"
        name = f"grab91160.{task_id}"
    else:
        log_file = f"grab_{datetime.now().strftime('%Y%m%d')}.log"
        name = "grab91160"
    
    return setup_logger(name=name, log_file=log_file)


# 全局日志器
_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """获取全局日志器"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def log_info(msg: str):
    """记录 INFO 日志"""
    get_logger().info(msg)


def log_warning(msg: str):
    """记录 WARNING 日志"""
    get_logger().warning(msg)


def log_error(msg: str):
    """记录 ERROR 日志"""
    get_logger().error(msg)


def log_debug(msg: str):
    """记录 DEBUG 日志"""
    get_logger().debug(msg)


def log_critical(msg: str):
    """记录 CRITICAL 日志"""
    get_logger().critical(msg)


def log_grab_attempt(attempt: int, date: str, doctor: str = None, result: str = "扫描中"):
    """记录抢号尝试"""
    logger = get_logger()
    if doctor:
        logger.info(f"[尝试#{attempt}] {date} - {doctor} - {result}")
    else:
        logger.info(f"[尝试#{attempt}] {date} - {result}")


def log_grab_success(member: str, hospital: str, dep: str, doctor: str, date: str, time_slot: str):
    """记录抢号成功"""
    logger = get_logger()
    logger.critical("=" * 50)
    logger.critical("抢号成功!")
    logger.critical(f"就诊人: {member}")
    logger.critical(f"医院: {hospital}")
    logger.critical(f"科室: {dep}")
    logger.critical(f"医生: {doctor}")
    logger.critical(f"日期: {date}")
    logger.critical(f"时段: {time_slot}")
    logger.critical("=" * 50)


def log_grab_failed(reason: str):
    """记录抢号失败"""
    get_logger().error(f"抢号失败: {reason}")


class LogCapture:
    """
    日志捕获器 - 用于 GUI 显示
    
    使用示例:
        capture = LogCapture()
        capture.start()
        # ... 执行操作 ...
        logs = capture.get_logs()
        capture.stop()
    """
    
    def __init__(self, logger_name: str = "grab91160"):
        self.logger_name = logger_name
        self.logs = []
        self._handler = None
    
    def start(self):
        """开始捕获"""
        logger = logging.getLogger(self.logger_name)
        
        class ListHandler(logging.Handler):
            def __init__(self, log_list):
                super().__init__()
                self.log_list = log_list
            
            def emit(self, record):
                self.log_list.append(self.format(record))
        
        self._handler = ListHandler(self.logs)
        self._handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(self._handler)
    
    def stop(self):
        """停止捕获"""
        if self._handler:
            logger = logging.getLogger(self.logger_name)
            logger.removeHandler(self._handler)
            self._handler = None
    
    def get_logs(self) -> list:
        """获取捕获的日志"""
        return self.logs.copy()
    
    def clear(self):
        """清空日志"""
        self.logs.clear()


if __name__ == "__main__":
    # 测试日志
    logger = setup_logger()
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误")
    
    print(f"\n日志文件位置: {LOG_DIR}")
