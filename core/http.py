#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP客户端模块 - 支持速率限制和重试

⚠️ 已废弃警告 ⚠
--------------
此模块已废弃，建议使用异步版本：
    from core.async_engine import AsyncHTTPClient

原因：
    1. 使用同步 urllib，与项目异步架构不一致
    2. 无 SSRF 防护
    3. 性能较差

迁移示例：
    # 旧代码
    client = HTTPClient()
    result = client.get(url)
    
    # 新代码
    async with AsyncHTTPClient() as client:
        result = await client.get(url)

废弃版本: v3.3.0
移除版本: v4.0.0
"""

import warnings

# 显示废弃警告
warnings.warn(
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️  HTTPClient 已废弃\n"
    "请使用: from core.async_engine import AsyncHTTPClient\n"
    "原因: 同步架构、无 SSRF 防护、性能较差\n"
    "废弃版本: v3.3.0 | 移除版本: v4.0.0\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    DeprecationWarning,
    stacklevel=2
)

import time
import threading
import socket
import ipaddress
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from typing import Optional, List


# ============== SSRF 防护 ==============

class SSRFError(Exception):
    """SSRF 防护错误"""
    pass


# 内网 IP 黑名单
BLOCKED_IP_RANGES = [
    '10.0.0.0/8',      # 私有网络 A 类
    '172.16.0.0/12',   # 私有网络 B 类
    '192.168.0.0/16',  # 私有网络 C 类
    '127.0.0.0/8',     # 本地回环
    '169.254.0.0/16',  # 链路本地
    '0.0.0.0/8',       # 当前网络
    '224.0.0.0/4',     # 多播
    '240.0.0.0/4',     # 保留
    '255.255.255.255', # 广播
]


def _check_ssrf(url: str) -> bool:
    """检查 URL 是否指向内网地址
    
    Args:
        url: 要检查的 URL
        
    Returns:
        True 表示安全
        
    Raises:
        SSRFError: 如果 URL 指向内网地址
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    
    if not hostname:
        raise SSRFError(f"无效的 URL: {url}")
    
    # 解析域名对应的 IP
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except socket.gaierror:
        raise SSRFError(f"无法解析域名: {hostname}")
    except ValueError:
        raise SSRFError(f"无效的 IP 地址: {hostname}")
    
    # 检查是否在内网 IP 黑名单中
    for cidr in BLOCKED_IP_RANGES:
        if ip in ipaddress.ip_network(cidr, strict=False):
            raise SSRFError(
                f"SSRF 防护: 禁止访问内网地址 {ip_str} ({hostname})"
            )
    
    return True


class RateLimiter:
    """速率控制器"""
    
    def __init__(self, requests_per_second=5):
        self.min_interval = 1.0 / requests_per_second
        self.last_request = 0
        self._lock = threading.Lock()
    
    def wait(self):
        """等待到可以发送下一个请求"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            
            self.last_request = time.time()


class HTTPClient:
    """HTTP请求客户端
    
    ⚠️ 已废弃，请使用 AsyncHTTPClient
    """
    
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def __init__(
        self, 
        timeout=10, 
        user_agent=None, 
        rate_limit=None, 
        proxy=None,
        enable_ssrf_check: bool = True  # 新增：SSRF 防护开关
    ):
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        self.proxy = proxy
        self.enable_ssrf_check = enable_ssrf_check
    
    def _check_ssrf(self, url: str) -> bool:
        """检查 URL 是否安全"""
        if self.enable_ssrf_check:
            return _check_ssrf(url)
        return True
    
    def get(self, url, headers=None, allow_redirects=True):
        """发送GET请求
        
        Args:
            url: 请求URL
            headers: 额外请求头
            allow_redirects: 是否跟随重定向
            
        Raises:
            SSRFError: 如果 URL 指向内网地址（当 enable_ssrf_check=True）
        """
        # SSRF 检查
        self._check_ssrf(url)
        
        if self.rate_limiter:
            self.rate_limiter.wait()
        
        default_headers = {'User-Agent': self.user_agent}
        if headers:
            default_headers.update(headers)
        
        try:
            req = Request(url, headers=default_headers, method='GET')
            response = urlopen(req, timeout=self.timeout)
            
            return {
                'status': response.status,
                'headers': dict(response.headers),
                'body': response.read().decode('utf-8', errors='ignore'),
                'url': response.url
            }
        
        except HTTPError as e:
            return {
                'status': e.code,
                'headers': dict(e.headers) if e.headers else {},
                'body': e.read().decode('utf-8', errors='ignore') if e.fp else '',
                'error': str(e),
                'url': url
            }
        
        except URLError as e:
            return {
                'status': 0,
                'error': str(e),
                'url': url
            }
        
        except Exception as e:
            return {
                'status': 0,
                'error': str(e),
                'url': url
            }
    
    def head(self, url, headers=None):
        """发送HEAD请求"""
        # SSRF 检查
        self._check_ssrf(url)
        
        if self.rate_limiter:
            self.rate_limiter.wait()
        
        default_headers = {'User-Agent': self.user_agent}
        if headers:
            default_headers.update(headers)
        
        try:
            req = Request(url, headers=default_headers, method='HEAD')
            response = urlopen(req, timeout=self.timeout)
            
            return {
                'status': response.status,
                'headers': dict(response.headers),
                'url': response.url
            }
        
        except HTTPError as e:
            return {
                'status': e.code,
                'headers': dict(e.headers) if e.headers else {},
                'error': str(e)
            }
        
        except Exception as e:
            return {
                'status': 0,
                'error': str(e)
            }
    
    def post(self, url, data=None, headers=None, json_data=None):
        """发送POST请求"""
        # SSRF 检查
        self._check_ssrf(url)
        
        if self.rate_limiter:
            self.rate_limiter.wait()
        
        default_headers = {'User-Agent': self.user_agent}
        if json_data:
            import json
            data = json.dumps(json_data).encode('utf-8')
            default_headers['Content-Type'] = 'application/json'
        if headers:
            default_headers.update(headers)
        
        try:
            req = Request(url, data=data, headers=default_headers, method='POST')
            response = urlopen(req, timeout=self.timeout)
            
            return {
                'status': response.status,
                'headers': dict(response.headers),
                'body': response.read().decode('utf-8', errors='ignore')
            }
        
        except HTTPError as e:
            return {
                'status': e.code,
                'error': str(e)
            }
        
        except Exception as e:
            return {
                'status': 0,
                'error': str(e)
            }
