#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用工具模块 - 进度条、计时器、命令执行等
"""

import os
import sys
import time
import threading
import subprocess
from typing import Callable, Any, Optional, Tuple


class ProgressBar:
    """进度条显示"""
    
    def __init__(self, total: int, desc: str = "进度", width: int = 30):
        self.total = total
        self.desc = desc
        self.width = width
        self.current = 0
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._finished = False
    
    def update(self, n: int = 1):
        """更新进度"""
        with self._lock:
            self.current = min(self.current + n, self.total)
            self._display()
    
    def set_current(self, current: int):
        """设置当前进度"""
        with self._lock:
            self.current = min(current, self.total)
            self._display()
    
    def _display(self):
        """显示进度条"""
        if self._finished:
            return
        
        percent = int(self.current / self.total * 100) if self.total > 0 else 100
        filled = int(self.width * self.current / self.total) if self.total > 0 else self.width
        bar = '█' * filled + '░' * (self.width - filled)
        
        elapsed = time.time() - self.start_time
        speed = self.current / elapsed if elapsed > 0 else 0
        
        print(f"\r  {self.desc}: [{bar}] {percent}% ({self.current}/{self.total}) {speed:.1f}/s", end='', flush=True)
    
    def finish(self, message: str = None):
        """完成进度条"""
        self._finished = True
        print()  # 换行
        if message:
            print(f"  ✓ {message}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.finish()


class Timer:
    """计时工具类"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self) -> 'Timer':
        """开始计时"""
        self.start_time = time.time()
        return self
    
    def stop(self) -> float:
        """停止计时并返回耗时"""
        self.end_time = time.time()
        return self.elapsed()
    
    def elapsed(self) -> float:
        """获取已耗时（秒）"""
        if self.start_time is None:
            return 0
        end = self.end_time or time.time()
        return end - self.start_time
    
    def elapsed_str(self) -> str:
        """获取格式化的耗时字符串"""
        elapsed = self.elapsed()
        if elapsed < 60:
            return f"{elapsed:.2f}秒"
        else:
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            return f"{minutes}分{seconds:.2f}秒"
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


class RetryHelper:
    """重试助手"""
    
    @staticmethod
    def retry(
        func: Callable[[], Any], 
        max_retries: int = 3, 
        delay: float = 1.0, 
        backoff: float = 2.0,
        exceptions: Tuple = (Exception,)
    ) -> Any:
        """带重试的执行函数
        
        Args:
            func: 要执行的函数
            max_retries: 最大重试次数
            delay: 初始延迟时间（秒）
            backoff: 延迟时间倍数
            exceptions: 要捕获的异常类型
        
        Returns:
            函数返回值
        
        Raises:
            最后一次失败的异常
        """
        last_error = None
        current_delay = delay
        
        for i in range(max_retries):
            try:
                return func()
            except exceptions as e:
                last_error = e
                if i < max_retries - 1:
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        raise last_error


class CommandRunner:
    """命令行执行工具"""
    
    @staticmethod
    def run(
        cmd: str, 
        timeout: int = 30, 
        encoding: str = None,
        shell: bool = True,
        cwd: str = None
    ) -> dict:
        """执行命令
        
        Args:
            cmd: 命令字符串
            timeout: 超时时间（秒）
            encoding: 输出编码
            shell: 是否使用shell
            cwd: 工作目录
        
        Returns:
            包含 success, stdout, stderr, returncode 的字典
        """
        # Windows默认使用gbk编码
        if sys.platform == 'win32':
            encoding = encoding or 'gbk'
        else:
            encoding = encoding or 'utf-8'
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding=encoding,
                errors='ignore',
                shell=shell,
                cwd=cwd
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Timeout',
                'stdout': '',
                'stderr': 'Command timed out'
            }
        
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'Command not found',
                'stdout': '',
                'stderr': f'Command not found: {cmd}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': str(e)
            }
    
    @staticmethod
    def run_async(cmd: str, callback: Callable = None, **kwargs):
        """异步执行命令
        
        Args:
            cmd: 命令字符串
            callback: 完成回调函数
            **kwargs: 传递给 run() 的其他参数
        """
        def _run():
            result = CommandRunner.run(cmd, **kwargs)
            if callback:
                callback(result)
        
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread


class FileHelper:
    """文件操作助手"""
    
    @staticmethod
    def ensure_dir(path: str):
        """确保目录存在"""
        os.makedirs(path, exist_ok=True)
    
    @staticmethod
    def read_file(path: str, encoding: str = 'utf-8') -> Optional[str]:
        """读取文件内容"""
        try:
            with open(path, 'r', encoding=encoding) as f:
                return f.read()
        except:
            return None
    
    @staticmethod
    def write_file(path: str, content: str, encoding: str = 'utf-8'):
        """写入文件"""
        FileHelper.ensure_dir(os.path.dirname(path))
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
    
    @staticmethod
    def append_file(path: str, content: str, encoding: str = 'utf-8'):
        """追加写入文件"""
        FileHelper.ensure_dir(os.path.dirname(path))
        with open(path, 'a', encoding=encoding) as f:
            f.write(content)


class Validator:
    """验证工具"""
    
    import re
    
    # 预编译正则
    _domain_pattern = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')
    _ip_pattern = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    _url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    
    @classmethod
    def is_domain(cls, value: str) -> bool:
        """验证域名格式"""
        return bool(cls._domain_pattern.match(value))
    
    @classmethod
    def is_ip(cls, value: str) -> bool:
        """验证IP格式"""
        return bool(cls._ip_pattern.match(value))
    
    @classmethod
    def is_url(cls, value: str) -> bool:
        """验证URL格式"""
        return bool(cls._url_pattern.match(value))
    
    @classmethod
    def is_port(cls, value: int) -> bool:
        """验证端口号"""
        return isinstance(value, int) and 0 < value <= 65535
