#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP客户端模块 - 支持速率限制和重试
"""

import time
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


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
    """HTTP请求客户端"""
    
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def __init__(self, timeout=10, user_agent=None, rate_limit=None, proxy=None):
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        self.proxy = proxy
    
    def get(self, url, headers=None, allow_redirects=True):
        """发送GET请求
        
        Args:
            url: 请求URL
            headers: 额外请求头
            allow_redirects: 是否跟随重定向
        
        Returns:
            dict: 包含 status, headers, body 等字段
        """
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
