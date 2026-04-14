#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志模块 - 支持分级日志、彩色输出和敏感信息过滤
"""

import sys
import logging
import re
from datetime import datetime

# Windows控制台编码修复
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


# ============== 敏感信息过滤 ==============

SENSITIVE_PATTERNS = [
    # 密码
    (r'(password\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(passwd\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(pwd\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    # API Keys
    (r'(api_key\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(apikey\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(api-key\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    # Token
    (r'(token\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(access_token\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(auth_token\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(bearer\s+)[a-zA-Z0-9_-]+', r'\1***'),
    # Secret
    (r'(secret\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    (r'(secret_key\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
    # Authorization Header
    (r'(Authorization\s*:\s*Bearer\s+)[a-zA-Z0-9_-]+', r'\1***'),
    # Cookie
    (r'(cookie\s*[=:]\s*)[^\s,;\}\]]+', r'\1***'),
]


def sanitize_message(message: str) -> str:
    """清理日志消息中的敏感信息
    
    将密码、API Key、Token 等敏感信息替换为 ***
    
    Args:
        message: 原始消息
        
    Returns:
        清理后的消息
    """
    if not isinstance(message, str):
        message = str(message)
    
    sanitized = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    return sanitized


class LogLevel:
    """日志级别"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    SUCCESS = 25  # 自定义成功级别


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（带敏感信息过滤）"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[37m',      # 白色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'SUCCESS': '\033[32m',   # 绿色
        'RESET': '\033[0m'       # 重置
    }
    
    def format(self, record):
        # 获取颜色
        level_name = record.levelname
        color = self.COLORS.get(level_name, self.COLORS['RESET'])
        
        # 格式化消息
        timestamp = datetime.now().strftime('%H:%M:%S')
        message = record.getMessage()
        
        # 过滤敏感信息
        message = sanitize_message(message)
        
        return f"{color}[{timestamp}] [{level_name}] {message}{self.COLORS['RESET']}"


def get_logger(name='recon', level=logging.INFO):
    """获取日志器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
    
    # 添加 SUCCESS 级别
    logging.addLevelName(LogLevel.SUCCESS, 'SUCCESS')
    
    return logger


# 全局日志器
_logger = None


def _get_logger():
    """获取全局日志器"""
    global _logger
    if _logger is None:
        _logger = get_logger()
    return _logger


class Logger:
    """静态日志工具类（兼容旧代码）"""
    
    @staticmethod
    def debug(msg):
        _get_logger().debug(msg)
    
    @staticmethod
    def info(msg):
        _get_logger().info(msg)
    
    @staticmethod
    def success(msg):
        _get_logger().log(LogLevel.SUCCESS, msg)
    
    @staticmethod
    def warn(msg):
        _get_logger().warning(msg)
    
    @staticmethod
    def error(msg):
        _get_logger().error(msg)
    
    @staticmethod
    def banner():
        print()
        print("=" * 55)
        print("     信息收集自动化工具 v2.3")
        print("     作者: 小欣 | 模块化架构")
        print("=" * 55)
        print()
    
    @staticmethod
    def module_header(module_name, module_num=None):
        """打印模块标题"""
        print("\n" + "=" * 55)
        if module_num:
            print(f"[模块{module_num}] {module_name}")
        else:
            print(f"[{module_name}]")
        print("=" * 55)
    
    @staticmethod
    def subtask(task_name):
        """打印子任务"""
        print(f"\n  → {task_name}")
    
    @staticmethod
    def result(count, item_name):
        """打印结果统计"""
        _get_logger().log(LogLevel.SUCCESS, f"发现 {count} 个{item_name}")


# 添加 success 方法到 Logger
logging.Logger.success = lambda self, msg: self.log(LogLevel.SUCCESS, msg)
