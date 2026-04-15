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
    
    def __init__(self, total: int, desc: str = "进度", width: int = 30) -> None:
        self.total = total
        self.desc = desc
        self.width = width
        self.current = 0
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._finished = False
    
    def update(self, n: int = 1) -> None:
        """更新进度"""
        with self._lock:
            self.current = min(self.current + n, self.total)
            self._display()
    
    def set_current(self, current: int) -> None:
        """设置当前进度"""
        with self._lock:
            self.current = min(current, self.total)
            self._display()
    
    def _display(self) -> None:
        """显示进度条"""
        if self._finished:
            return
        
        percent = int(self.current / self.total * 100) if self.total > 0 else 100
        filled = int(self.width * self.current / self.total) if self.total > 0 else self.width
        bar = '█' * filled + '░' * (self.width - filled)
        
        elapsed = time.time() - self.start_time
        speed = self.current / elapsed if elapsed > 0 else 0
        
        print(f"\r  {self.desc}: [{bar}] {percent}% ({self.current}/{self.total}) {speed:.1f}/s", end='', flush=True)
    
    def finish(self, message: Optional[str] = None) -> None:
        """完成进度条"""
        self._finished = True
        print()  # 换行
        if message:
            print(f"  ✓ {message}")
    
    def __enter__(self) -> 'ProgressBar':
        return self
    
    def __exit__(self, *args) -> None:
        self.finish()


class Timer:
    """计时工具类"""
    
    def __init__(self) -> None:
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
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
    
    def __enter__(self) -> 'Timer':
        self.start()
        return self
    
    def __exit__(self, *args) -> None:
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
    """命令行执行工具
    
    安全说明:
        - 默认 shell=False，更安全
        - 提供 shell=True 选项用于兼容旧代码
        - 当 shell=True 时，会对命令进行安全检查
    """
    
    # 安全命令模式白名单（仅包含可信工具）
    _SAFE_COMMAND_PATTERNS = [
        r'^subfinder\s',
        r'^nmap\s',
        r'^httpx\s',
        r'^naabu\s',
        r'^nuclei\s',
        r'^whois\s',
        r'^dig\s',
        r'^nslookup\s',
    ]
    
    @staticmethod
    def _validate_shell_command(cmd: str) -> bool:
        """验证 shell 命令是否安全
        
        检查命令是否在白名单中，防止任意命令执行。
        
        Args:
            cmd: 命令字符串
            
        Returns:
            是否安全
        """
        import re
        
        # 检查是否匹配白名单
        for pattern in CommandRunner._SAFE_COMMAND_PATTERNS:
            if re.match(pattern, cmd, re.IGNORECASE):
                return True
        
        # 不在白名单中，记录警告
        import logging
        logging.getLogger(__name__).warning(
            f"安全警告: 命令不在白名单中: {cmd[:50]}..."
        )
        return False
    
    @staticmethod
    def run(
        cmd: str, 
        timeout: int = 30, 
        encoding: str = None,
        shell: bool = False,  # 默认改为 False，更安全
        cwd: str = None,
        unsafe_skip_validation: bool = False  # 允许跳过验证（仅用于受信任场景）
    ) -> dict:
        """执行命令
        
        Args:
            cmd: 命令字符串或列表
            timeout: 超时时间（秒）
            encoding: 输出编码
            shell: 是否使用shell（默认 False 更安全）
            cwd: 工作目录
            unsafe_skip_validation: 是否跳过安全验证（仅用于受信任场景）
        
        Returns:
            包含 success, stdout, stderr, returncode 的字典
            
        Security:
            - shell=False (默认) 使用参数列表，更安全
            - shell=True 时会进行命令白名单检查
            - 不建议在生产环境使用 shell=True
        """
        # Windows默认使用gbk编码
        if sys.platform == 'win32':
            encoding = encoding or 'gbk'
        else:
            encoding = encoding or 'utf-8'
        
        # 安全检查
        if shell and not unsafe_skip_validation:
            if not CommandRunner._validate_shell_command(str(cmd)):
                return {
                    'success': False,
                    'error': 'Security',
                    'stdout': '',
                    'stderr': f'命令不在安全白名单中。如需执行，请使用 unsafe_skip_validation=True'
                }
        
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
    def run_safe(
        tool_path: str,
        args: list,
        timeout: int = 30,
        encoding: str = None,
        cwd: str = None
    ) -> dict:
        """安全执行命令（推荐使用）
        
        使用参数列表而非 shell 字符串，防止命令注入。
        
        Args:
            tool_path: 工具路径
            args: 参数列表
            timeout: 超时时间（秒）
            encoding: 输出编码
            cwd: 工作目录
        
        Returns:
            包含 success, stdout, stderr, returncode 的字典
        """
        # Windows默认使用gbk编码
        if sys.platform == 'win32':
            encoding = encoding or 'gbk'
        else:
            encoding = encoding or 'utf-8'
        
        # 构建命令列表
        cmd_list = [tool_path] + [str(arg) for arg in args]
        
        try:
            result = subprocess.run(
                cmd_list,  # 使用列表，不是字符串
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding=encoding,
                errors='ignore',
                shell=False,  # 明确使用 shell=False
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
                'stderr': f'Command not found: {tool_path}'
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
        except (IOError, OSError, UnicodeDecodeError) as e:
            logger.debug(f"读取文件失败: {path} - {e}")
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
