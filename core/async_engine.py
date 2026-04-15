#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 核心异步引擎
全新的异步架构，支持并发请求、智能重试、代理池、缓存
"""

import asyncio
import aiohttp
import time
import random
import hashlib
import json
import os
import ssl
import ipaddress
import urllib.parse
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from functools import wraps
import dns.asyncresolver
import dns.resolver

# ============== 缓存系统 ==============

class AsyncCache:
    """异步缓存管理器"""
    
    def __init__(self, ttl: int = 3600, max_size: int = 10000):
        self.cache: Dict[str, tuple] = {}  # key -> (value, expire_time)
        self.ttl = ttl
        self.max_size = max_size
    
    def _hash_key(self, key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        hkey = self._hash_key(key)
        if hkey in self.cache:
            value, expire = self.cache[hkey]
            if time.time() < expire:
                return value
            del self.cache[hkey]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        if len(self.cache) >= self.max_size:
            # 清理过期缓存
            now = time.time()
            expired = [k for k, (v, e) in self.cache.items() if e < now]
            for k in expired:
                del self.cache[k]
        
        hkey = self._hash_key(key)
        expire = time.time() + (ttl or self.ttl)
        self.cache[hkey] = (value, expire)
    
    async def clear(self):
        self.cache.clear()


# ============== 代理池 ==============

@dataclass
class Proxy:
    """代理配置类
    
    Attributes:
        url: 代理地址（不含协议前缀）
        protocol: 代理协议（http/socks5）
        alive: 是否存活
        latency: 延迟（毫秒）
        fail_count: 失败次数
    """
    url: str
    protocol: str = "http"  # http, socks5
    alive: bool = True
    latency: float = 0.0
    fail_count: int = 0
    
    def __str__(self):
        return f"{self.protocol}://{self.url}"


class ProxyPool:
    """代理池管理器"""
    
    def __init__(self, proxies: List[str] = None):
        self.proxies: List[Proxy] = []
        self.index = 0
        
        if proxies:
            for p in proxies:
                if p.startswith("socks5://"):
                    self.proxies.append(Proxy(url=p[9:], protocol="socks5"))
                elif p.startswith("http://"):
                    self.proxies.append(Proxy(url=p[7:], protocol="http"))
                else:
                    self.proxies.append(Proxy(url=p, protocol="http"))
    
    def get(self) -> Optional[Proxy]:
        """获取下一个可用代理"""
        if not self.proxies:
            return None
        
        # 找到可用的代理
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.index]
            self.index = (self.index + 1) % len(self.proxies)
            if proxy.alive:
                return proxy
        
        return None
    
    def mark_success(self, proxy: Proxy):
        proxy.alive = True
        proxy.fail_count = 0
    
    def mark_failed(self, proxy: Proxy):
        proxy.fail_count += 1
        if proxy.fail_count >= 3:
            proxy.alive = False
    
    async def check_all(self, test_url: str = "http://httpbin.org/ip", timeout: int = 10):
        """检测所有代理的可用性"""
        async with aiohttp.ClientSession() as session:
            tasks = [self._check_proxy(session, p, test_url, timeout) for p in self.proxies]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_proxy(self, session: aiohttp.ClientSession, proxy: Proxy, url: str, timeout: int):
        try:
            start = time.time()
            connector = aiohttp.TCPConnector() if proxy.protocol == "http" else None
            
            async with session.get(
                url,
                proxy=str(proxy),
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    proxy.latency = time.time() - start
                    proxy.alive = True
                    proxy.fail_count = 0
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError):
            proxy.alive = False
        except Exception as e:
            proxy.alive = False
            logger.warning(f"Proxy check failed: {e}")


# ============== 智能重试 ==============

@dataclass
class RetryConfig:
    """重试配置类
    
    Attributes:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数退避基数
        jitter: 是否添加随机抖动
        retryable_errors: 可重试的异常类型
    """
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_errors: tuple = (
        asyncio.TimeoutError,
        aiohttp.ClientError,
        ConnectionError,
    )


def async_retry(config: RetryConfig = None):
    """异步重试装饰器"""
    config = config or RetryConfig()
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_errors as e:
                    last_error = e
                    if attempt < config.max_retries:
                        delay = min(
                            config.base_delay * (config.exponential_base ** attempt),
                            config.max_delay
                        )
                        if config.jitter:
                            delay *= random.uniform(0.5, 1.5)
                        await asyncio.sleep(delay)
            
            raise last_error
        return wrapper
    return decorator


# ============== 速率限制 ==============

class AsyncRateLimiter:
    """异步速率限制器
    
    安全限制：防止对目标造成 DoS 攻击
    """
    
    # 安全上限
    MAX_RATE = 100  # 最大 100 请求/秒
    MAX_BURST = 200  # 最大突发 200 请求
    
    def __init__(self, rate: float = 10.0, burst: int = 20):
        # 强制限制在安全范围内
        self.rate = min(rate, self.MAX_RATE)  # 请求/秒
        self.burst = min(burst, self.MAX_BURST)
        self.tokens = self.burst
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= tokens


# ============== DNS 解析器 ==============

class AsyncDNSResolver:
    """异步DNS解析器 - 支持缓存和多服务器"""
    
    DEFAULT_SERVERS = [
        "8.8.8.8", "8.8.4.4",  # Google
        "1.1.1.1", "1.0.0.1",  # Cloudflare
        "114.114.114.114", "223.5.5.5",  # 国内
    ]
    
    def __init__(self, servers: List[str] = None, cache: AsyncCache = None):
        self.servers = servers or self.DEFAULT_SERVERS
        self.cache = cache or AsyncCache(ttl=1800)  # 30分钟缓存
        self.resolver = dns.asyncresolver.Resolver()
        self.resolver.nameservers = self.servers
        self.resolver.timeout = 5
        self.resolver.lifetime = 10
    
    async def resolve(self, domain: str, record_type: str = "A") -> List[str]:
        """解析域名"""
        cache_key = f"dns:{record_type}:{domain}"
        
        # 检查缓存
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        # 解析
        try:
            answers = await self.resolver.resolve(domain, record_type)
            result = [str(r) for r in answers]
            self.cache.set(cache_key, result)
            return result
        except dns.resolver.NXDOMAIN:
            return []
        except dns.resolver.NoAnswer:
            return []
        except dns.resolver.Timeout:
            return []
        except Exception as e:
            logger.warning(f"DNS resolution failed for {domain}: {e}")
            return []
    
    async def resolve_all(self, domain: str) -> List[str]:
        """解析所有A记录"""
        return await self.resolve(domain, "A")
    
    async def get_cname(self, domain: str) -> Optional[str]:
        """获取CNAME"""
        results = await self.resolve(domain, "CNAME")
        return results[0] if results else None
    
    async def check_wildcard(self, domain: str) -> bool:
        """检测泛解析"""
        random_sub = f"{random.randint(100000, 999999)}.{domain}"
        ips = await self.resolve_all(random_sub)
        return len(ips) > 0


# ============== HTTP 客户端 ==============

# SSRF 防护 - 禁止访问的内网 IP 段
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),       # 私有网络 A 类
    ipaddress.ip_network('172.16.0.0/12'),    # 私有网络 B 类
    ipaddress.ip_network('192.168.0.0/16'),   # 私有网络 C 类
    ipaddress.ip_network('127.0.0.0/8'),      # 本地回环 (IPv4)
    ipaddress.ip_network('169.254.0.0/16'),   # 链路本地
    ipaddress.ip_network('0.0.0.0/8'),        # 当前网络
    ipaddress.ip_network('224.0.0.0/4'),      # 多播地址
    ipaddress.ip_network('240.0.0.0/4'),      # 保留地址
]

# IPv6 禁止地址
BLOCKED_IPV6_RANGES = [
    ipaddress.ip_network('::1/128'),          # IPv6 本地回环
    ipaddress.ip_network('fc00::/7'),         # IPv6 唯一本地地址 (ULA)
    ipaddress.ip_network('fe80::/10'),        # IPv6 链路本地
    ipaddress.ip_network('ff00::/8'),         # IPv6 多播
    ipaddress.ip_network('::/128'),           # 未指定地址
    ipaddress.ip_network('::ffff:0:0/96'),    # IPv4 映射地址
]


def is_ip_blocked(ip_str: str) -> bool:
    """检查 IP 是否在禁止访问的范围内"""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        
        # IPv4 检查
        if ip_obj.version == 4:
            for network in BLOCKED_IP_RANGES:
                if ip_obj in network:
                    return True
        
        # IPv6 检查
        else:
            for network in BLOCKED_IPV6_RANGES:
                if ip_obj in network:
                    return True
            # 也检查 IPv4 映射的 IPv6 地址
            if ip_obj.ipv4_mapped:
                for network in BLOCKED_IP_RANGES:
                    if ip_obj.ipv4_mapped in network:
                        return True
        
        return False
    except ValueError:
        return True  # 无效 IP 也阻止


class AsyncHTTPClient:
    """异步HTTP客户端"""
    
    def __init__(
        self,
        timeout: int = 30,
        headers: Dict[str, str] = None,
        proxy_pool: ProxyPool = None,
        rate_limiter: AsyncRateLimiter = None,
        cache: AsyncCache = None,
        verify_ssl: bool = True,  # 默认启用 SSL 验证
    ):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.proxy_pool = proxy_pool
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.verify_ssl = verify_ssl
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        # 根据配置决定是否验证 SSL
        if self.verify_ssl:
            ssl_context = ssl.create_default_context()
        else:
            # 仅在明确禁用时才跳过验证
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(
            limit=100, 
            limit_per_host=10,
            ssl=ssl_context
        )
        
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=self.timeout,
            connector=connector
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def _check_ssrf(self, url: str) -> None:
        """
        SSRF 防护检查
        在发送请求前验证目标 IP 不在禁止范围内
        """
        try:
            parsed = urllib.parse.urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                raise ValueError(f"无法解析 URL 主机名: {url}")
            
            # 如果是 IP 地址直接检查
            try:
                ip = ipaddress.ip_address(hostname)
                if is_ip_blocked(str(ip)):
                    raise ValueError(
                        f"SSRF 防护: 禁止访问内网地址 {ip}。"
                        f"如需扫描内网，请在配置中明确启用。"
                    )
                return
            except ValueError:
                pass  # 不是 IP，继续解析域名
            
            # 解析域名获取 IP
            try:
                resolver = dns.asyncresolver.Resolver()
                resolver.timeout = 3
                resolver.lifetime = 5
                answers = await resolver.resolve(hostname, 'A')
                
                for rdata in answers:
                    ip_str = str(rdata)
                    if is_ip_blocked(ip_str):
                        raise ValueError(
                            f"SSRF 防护: 域名 {hostname} 解析到内网 IP {ip_str}"
                        )
            except dns.resolver.NXDOMAIN:
                pass  # 域名不存在，让后续请求处理
            except dns.resolver.Timeout:
                pass  # DNS 超时，让后续请求处理
            except Exception:
                pass  # 其他 DNS 错误，让后续请求处理
                
        except Exception as e:
            if "SSRF 防护" in str(e):
                raise
            # 其他错误不阻止请求，记录警告即可
    
    @async_retry()
    async def get(self, url: str, skip_ssrf_check: bool = False, **kwargs) -> Dict[str, Any]:
        """GET请求"""
        # SSRF 防护检查
        if not skip_ssrf_check:
            await self._check_ssrf(url)
        
        # 检查缓存
        if self.cache:
            cached = self.cache.get(f"http:get:{url}")
            if cached:
                return cached
        
        # 速率限制
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        # 获取代理
        proxy = None
        if self.proxy_pool:
            proxy = self.proxy_pool.get()
        
        try:
            async with self.session.get(url, proxy=str(proxy) if proxy else None, **kwargs) as resp:
                body = await resp.text()
                result = {
                    "url": url,
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": body,
                    "length": len(body),
                }
                
                # 缓存结果
                if self.cache and resp.status == 200:
                    self.cache.set(f"http:get:{url}", result, ttl=300)
                
                # 标记代理成功
                if proxy:
                    self.proxy_pool.mark_success(proxy)
                
                return result
        except Exception as e:
            if proxy:
                self.proxy_pool.mark_failed(proxy)
            raise
    
    @async_retry()
    async def post(self, url: str, data: Any = None, json: Any = None, skip_ssrf_check: bool = False, **kwargs) -> Dict[str, Any]:
        """POST请求"""
        # SSRF 防护检查
        if not skip_ssrf_check:
            await self._check_ssrf(url)
        
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        proxy = None
        if self.proxy_pool:
            proxy = self.proxy_pool.get()
        
        try:
            async with self.session.post(url, data=data, json=json, proxy=str(proxy) if proxy else None, **kwargs) as resp:
                return {
                    "url": url,
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": await resp.text(),
                }
        except Exception as e:
            if proxy:
                self.proxy_pool.mark_failed(proxy)
            raise


# ============== 进度显示 ==============

class AsyncProgressBar:
    """异步进度条"""
    
    def __init__(self, total: int, desc: str = "进度"):
        self.total = total
        self.desc = desc
        self.current = 0
        self.start_time = time.time()
        self.lock = asyncio.Lock()
    
    async def update(self, n: int = 1):
        async with self.lock:
            self.current += n
            await self._render()
    
    async def _render(self):
        elapsed = time.time() - self.start_time
        if self.total == 0:
            percent = 0
            speed = 0
            eta = 0
        else:
            percent = self.current / self.total * 100
            speed = self.current / elapsed if elapsed > 0 else 0
            eta = (self.total - self.current) / speed if speed > 0 else 0
        
        bar_len = 30
        filled = int(bar_len * self.current / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        
        print(f"\r{self.desc}: [{bar}] {self.current}/{self.total} ({percent:.1f}%) | {speed:.1f}/s | ETA: {eta:.0f}s", end="", flush=True)
    
    async def finish(self):
        await self._render()
        print()


# ============== 结果存储 ==============

class ResultStore:
    """结果存储管理器"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def save_json(self, target: str, results: Dict, filename: str = None):
        filename = filename or f"{target}_{int(time.time())}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def save_txt(self, target: str, data: List[str], filename: str = None):
        filename = filename or f"{target}_{int(time.time())}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(data))
        
        return filepath


# ============== 工具函数 ==============

def get_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

async def run_concurrent(tasks: List, limit: int = 50):
    """限制并发数运行任务"""
    semaphore = asyncio.Semaphore(limit)
    
    async def limited_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*[limited_task(t) for t in tasks], return_exceptions=True)
