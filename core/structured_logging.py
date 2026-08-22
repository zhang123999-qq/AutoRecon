#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 结构化日志 + 链路追踪
支持 JSON 格式、上下文变量、性能指标、异常链路
"""

import logging
import sys
import json
import time
import uuid
import threading
import contextvars
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from functools import wraps
from contextlib import contextmanager
import traceback


# ============ 上下文变量 ============

# 请求/扫描上下文
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
scan_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("scan_id", default="")
target_var: contextvars.ContextVar[str] = contextvars.ContextVar("target", default="")
module_var: contextvars.ContextVar[str] = contextvars.ContextVar("module", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")

# 线程本地存储（用于同步代码）
_thread_local = threading.local()


# ============ 数据模型 ============

class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """日志上下文"""
    request_id: str = ""
    scan_id: str = ""
    target: str = ""
    module: str = ""
    user_id: str = ""
    trace_id: str = ""
    span_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_contextvars(cls) -> "LogContext":
        """从上下文变量创建"""
        return cls(
            request_id=request_id_var.get(""),
            scan_id=scan_id_var.get(""),
            target=target_var.get(""),
            module=module_var.get(""),
            user_id=user_id_var.get(""),
            trace_id=trace_id_var.get(""),
            span_id=span_id_var.get(""),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class StructuredLogRecord:
    """结构化日志记录"""
    timestamp: str
    level: str
    logger: str
    message: str
    context: LogContext
    extra: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[Dict[str, Any]] = None
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        data = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            **self.context.to_dict(),
            **self.extra,
        }
        if self.exception:
            data["exception"] = self.exception
        return json.dumps(data, ensure_ascii=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            **self.context.to_dict(),
            **self.extra,
        }
        if self.exception:
            data["exception"] = self.exception
        return data


# ============ 自定义 Formatter ============

class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, json_output: bool = True, include_extra: bool = True):
        super().__init__()
        self.json_output = json_output
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        # 获取上下文
        context = LogContext.from_contextvars()
        
        # 合并 record 中的额外字段
        extra = {}
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'exc_info', 'exc_text',
                    'stack_info', 'message'
                }:
                    extra[key] = value
        
        # 异常信息
        exception = None
        if record.exc_info:
            exception = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # 创建结构化记录
        structured = StructuredLogRecord(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            context=context,
            extra=extra,
            exception=exception
        )
        
        if self.json_output:
            return structured.to_json()
        else:
            # 控制台友好格式
            ctx_parts = []
            if context.request_id:
                ctx_parts.append(f"req={context.request_id}")
            if context.scan_id:
                ctx_parts.append(f"scan={context.scan_id}")
            if context.target:
                ctx_parts.append(f"target={context.target}")
            if context.module:
                ctx_parts.append(f"mod={context.module}")
            
            ctx_str = f" [{', '.join(ctx_parts)}]" if ctx_parts else ""
            
            extra_str = ""
            if extra:
                extra_str = f" | {json.dumps(extra, ensure_ascii=False)}"
            
            exc_str = ""
            if exception:
                exc_str = f"\n  Exception: {exception['type']}: {exception['message']}"
                if exception.get('traceback'):
                    exc_str += "\n  " + "\n  ".join(exception['traceback'][-3:])  # 只显示最后3行
            
            return f"{structured.timestamp} | {record.levelname:8} | {record.name}{ctx_str} | {record.getMessage()}{extra_str}{exc_str}"


class ConsoleFormatter(StructuredFormatter):
    """控制台格式化器（彩色）"""
    
    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 紫色
        "RESET": "\033[0m",
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, json_output=False, **kwargs)
    
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]
        return f"{color}{formatted}{reset}"


# ============ 自定义 Handler ============

class MetricsHandler(logging.Handler):
    """指标收集 Handler"""
    
    def __init__(self):
        super().__init__()
        self.metrics = {
            "total": 0,
            "by_level": {},
            "by_logger": {},
            "errors": [],
        }
        self.max_errors = 1000
    
    def emit(self, record: logging.LogRecord):
        self.metrics["total"] += 1
        
        level = record.levelname
        self.metrics["by_level"][level] = self.metrics["by_level"].get(level, 0) + 1
        
        logger_name = record.name
        self.metrics["by_logger"][logger_name] = self.metrics["by_logger"].get(logger_name, 0) + 1
        
        if record.levelno >= logging.ERROR:
            error_info = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "logger": logger_name,
                "message": record.getMessage(),
                "level": level,
            }
            if record.exc_info:
                error_info["exception"] = str(record.exc_info[1])
            self.metrics["errors"].append(error_info)
            if len(self.metrics["errors"]) > self.max_errors:
                self.metrics["errors"] = self.metrics["errors"][-self.max_errors:]
    
    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.copy()
    
    def reset(self):
        self.metrics = {
            "total": 0,
            "by_level": {},
            "by_logger": {},
            "errors": [],
        }


# ============ Logger 管理器 ============

class LoggerManager:
    """日志管理器 - 统一配置和获取 logger"""
    
    _instance = None
    _initialized = False
    _metrics_handler: Optional[MetricsHandler] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._loggers: Dict[str, logging.Logger] = {}
    
    def configure(
        self,
        level: str = "INFO",
        json_output: bool = False,
        log_file: Optional[str] = None,
        console_output: bool = True,
        colored_console: bool = True,
    ):
        """配置全局日志
        
        Args:
            level: 日志级别
            json_output: 是否输出 JSON 格式
            log_file: 日志文件路径
            console_output: 是否输出到控制台
            colored_console: 控制台是否彩色
        """
        # 清除现有 handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(getattr(logging, level.upper()))
        
        # 控制台 handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            if colored_console and sys.stdout.isatty():
                console_handler.setFormatter(ConsoleFormatter())
            else:
                console_handler.setFormatter(StructuredFormatter(json_output=False))
            root_logger.addHandler(console_handler)
        
        # 文件 handler
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(StructuredFormatter(json_output=json_output))
            root_logger.addHandler(file_handler)
        
        # 指标 handler
        self._metrics_handler = MetricsHandler()
        root_logger.addHandler(self._metrics_handler)
        
        # 设置第三方库日志级别
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取 logger（自动绑定上下文）"""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]
    
    def get_metrics(self) -> Dict[str, Any]:
        if self._metrics_handler:
            return self._metrics_handler.get_metrics()
        return {}
    
    def reset_metrics(self):
        if self._metrics_handler:
            self._metrics_handler.reset()


# 全局实例
logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """获取结构化 logger"""
    return logger_manager.get_logger(name)


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
    console_output: bool = True,
    colored_console: bool = True,
):
    """配置全局日志（便捷函数）"""
    logger_manager.configure(
        level=level,
        json_output=json_output,
        log_file=log_file,
        console_output=console_output,
        colored_console=colored_console,
    )


# ============ 上下文管理器 ============

@contextmanager
def log_context(
    request_id: str = None,
    scan_id: str = None,
    target: str = None,
    module: str = None,
    user_id: str = None,
    trace_id: str = None,
    **extra
):
    """日志上下文管理器
    
    使用示例:
        with log_context(request_id="req-123", target="example.com"):
            logger.info("开始扫描")
    """
    tokens = []
    
    if request_id is not None:
        tokens.append(request_id_var.set(request_id))
    if scan_id is not None:
        tokens.append(scan_id_var.set(scan_id))
    if target is not None:
        tokens.append(target_var.set(target))
    if module is not None:
        tokens.append(module_var.set(module))
    if user_id is not None:
        tokens.append(user_id_var.set(user_id))
    if trace_id is not None:
        tokens.append(trace_id_var.set(trace_id))
    
    try:
        yield
    finally:
        for token in reversed(tokens):
            if token.var is request_id_var:
                request_id_var.reset(token)
            elif token.var is scan_id_var:
                scan_id_var.reset(token)
            elif token.var is target_var:
                target_var.reset(token)
            elif token.var is module_var:
                module_var.reset(token)
            elif token.var is user_id_var:
                user_id_var.reset(token)
            elif token.var is trace_id_var:
                trace_id_var.reset(token)


@contextmanager
def scan_context(scan_id: str, target: str, module: str = None):
    """扫描上下文管理器"""
    with log_context(scan_id=scan_id, target=target, module=module or ""):
        yield


# ============ 性能计时装饰器 ============

def timed_operation(operation_name: str = None, logger_name: str = None):
    """性能计时装饰器
    
    使用示例:
        @timed_operation("dns_resolve", "scanner.dns")
        async def resolve_domain(domain):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            log = get_logger(logger_name or func.__module__)
            start = time.perf_counter()
            
            with log_context(module=op_name):
                log.info(f"开始操作: {op_name}")
                try:
                    result = await func(*args, **kwargs)
                    elapsed = (time.perf_counter() - start) * 1000
                    log.info(f"操作完成: {op_name}", extra={"duration_ms": elapsed})
                    return result
                except Exception as e:
                    elapsed = (time.perf_counter() - start) * 1000
                    log.error(f"操作失败: {op_name}", extra={
                        "duration_ms": elapsed,
                        "error": str(e)
                    })
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            log = get_logger(logger_name or func.__module__)
            start = time.perf_counter()
            
            with log_context(module=op_name):
                log.info(f"开始操作: {op_name}")
                try:
                    result = func(*args, **kwargs)
                    elapsed = (time.perf_counter() - start) * 1000
                    log.info(f"操作完成: {op_name}", extra={"duration_ms": elapsed})
                    return result
                except Exception as e:
                    elapsed = (time.perf_counter() - start) * 1000
                    log.error(f"操作失败: {op_name}", extra={
                        "duration_ms": elapsed,
                        "error": str(e)
                    })
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============ 异常追踪 ============

def log_exception(logger: logging.Logger, e: Exception, context: Dict = None, level: int = logging.ERROR):
    """记录异常（包含上下文）"""
    extra = {"error_type": type(e).__name__}
    if context:
        extra["context"] = context
    
    logger.log(level, f"异常: {e}", extra=extra, exc_info=True)


class ExceptionTracker:
    """异常追踪器 - 收集和分析异常"""
    
    def __init__(self, max_exceptions: int = 100):
        self.exceptions: List[Dict] = []
        self.max_exceptions = max_exceptions
        self._lock = threading.Lock()
    
    def track(self, e: Exception, context: Dict = None):
        with self._lock:
            exc_info = {
                "timestamp": datetime.now().isoformat(),
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
                "context": context or {},
            }
            self.exceptions.append(exc_info)
            if len(self.exceptions) > self.max_exceptions:
                self.exceptions = self.exceptions[-self.max_exceptions:]
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        with self._lock:
            return self.exceptions[-limit:]
    
    def get_by_type(self, exc_type: str) -> List[Dict]:
        with self._lock:
            return [e for e in self.exceptions if e["type"] == exc_type]
    
    def clear(self):
        with self._lock:
            self.exceptions.clear()


# 全局异常追踪器
exception_tracker = ExceptionTracker()


# ============ 集成示例 ============

if __name__ == "__main__":
    # 配置日志
    configure_logging(
        level="DEBUG",
        json_output=False,
        log_file="logs/autorecon.log",
        colored_console=True
    )
    
    log = get_logger("demo")
    
    # 测试基本日志
    log.debug("调试信息")
    log.info("普通信息")
    log.warning("警告信息")
    log.error("错误信息")
    
    # 测试上下文
    with log_context(request_id="req-123", scan_id="scan-456", target="example.com"):
        log.info("在上下文中记录")
        
        with scan_context("scan-456", "example.com", "subdomain"):
            log.info("子域名扫描上下文")
    
    # 测试性能计时
    @timed_operation("test_operation", "demo")
    async def test_async():
        await asyncio.sleep(0.1)
        return "done"
    
    import asyncio
    asyncio.run(test_async())
    
    # 测试异常追踪
    try:
        raise ValueError("测试异常")
    except Exception as e:
        exception_tracker.track(e, {"target": "test"})
        log_exception(log, e, {"target": "test"})
    
    print("\n异常追踪:")
    for exc in exception_tracker.get_recent(5):
        print(f"  {exc['type']}: {exc['message']}")
    
    print("\n日志指标:")
    print(json.dumps(logger_manager.get_metrics(), indent=2, ensure_ascii=False))