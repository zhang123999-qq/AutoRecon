#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 异步子域名收集模块
支持: DNS枚举、证书透明度、搜索引擎、被动API
"""

import asyncio
import json
import re
import time
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.async_engine import (
    AsyncHTTPClient, AsyncDNSResolver, AsyncCache, 
    AsyncRateLimiter, AsyncProgressBar, run_concurrent
)
from data.wordlists import PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW, ALL_PREFIXES


@dataclass
class SubdomainResult:
    """子域名结果"""
    subdomain: str
    ip: Optional[str] = None
    source: str = ""
    port: int = 0
    title: str = ""
    status: int = 0
    cdn: str = ""
    waf: str = ""


class AsyncSubdomainCollector:
    """异步子域名收集器"""
    
    def __init__(
        self, 
        domain: str,
        threads: int = 50,
        dns_servers: List[str] = None,
        use_cache: bool = True
    ):
        self.domain = domain.rstrip('.')
        self.threads = threads
        
        # 缓存
        self.cache = AsyncCache(ttl=1800) if use_cache else None
        
        # DNS解析器
        self.dns = AsyncDNSResolver(dns_servers, self.cache)
        
        # 结果存储
        self.subdomains: Set[str] = set()
        self.results: List[SubdomainResult] = []
        
        # 统计
        self.stats = {
            "dns": 0,
            "certificate": 0,
            "search": 0,
            "api": 0,
            "total": 0
        }
    
    async def _check_subdomain(self, prefix: str) -> Optional[SubdomainResult]:
        """检查单个子域名"""
        subdomain = f"{prefix}.{self.domain}"
        
        # DNS解析
        ips = await self.dns.resolve_all(subdomain)
        if ips:
            return SubdomainResult(
                subdomain=subdomain,
                ip=ips[0],
                source="dns"
            )
        return None
    
    async def collect_from_dns(self, prefixes: List[str] = None, show_progress: bool = True) -> List[SubdomainResult]:
        """DNS枚举收集子域名"""
        prefixes = prefixes or PRIORITY_HIGH + PRIORITY_MEDIUM
        results = []
        
        print(f"[\u001b[36m*\u001b[0m] DNS枚举: {len(prefixes)} 个前缀...")
        
        if show_progress:
            progress = AsyncProgressBar(len(prefixes), "DNS枚举")
        
        # 批量并发
        semaphore = asyncio.Semaphore(self.threads)
        
        async def limited_check(prefix):
            async with semaphore:
                result = await self._check_subdomain(prefix)
                if show_progress:
                    await progress.update()
                return result
        
        tasks = [limited_check(p) for p in prefixes]
        done = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in done:
            if isinstance(result, SubdomainResult):
                if result.subdomain not in self.subdomains:
                    self.subdomains.add(result.subdomain)
                    self.results.append(result)
                    results.append(result)
        
        if show_progress:
            await progress.finish()
        
        self.stats["dns"] = len(results)
        print(f"[\u001b[32m+\u001b[0m] DNS枚举发现: {len(results)} 个子域名")
        return results
    
    async def collect_from_certificate(self) -> List[SubdomainResult]:
        """从证书透明度日志收集子域名"""
        print(f"[\u001b[36m*\u001b[0m] 证书透明度日志查询...")
        
        results = []
        
        try:
            async with AsyncHTTPClient() as client:
                url = f"https://crt.sh/?q=%.{self.domain}&output=json"
                resp = await client.get(url)
                
                if resp["status"] == 200:
                    data = json.loads(resp["body"])
                    
                    for entry in data:
                        name = entry.get("name_value", "")
                        for sub in name.split('\n'):
                            sub = sub.strip().lower()
                            # 过滤通配符
                            if sub.endswith(self.domain) and '*' not in sub:
                                if sub not in self.subdomains:
                                    self.subdomains.add(sub)
                                    ip = (await self.dns.resolve_all(sub))[0] if await self.dns.resolve_all(sub) else None
                                    result = SubdomainResult(
                                        subdomain=sub,
                                        ip=ip,
                                        source="certificate"
                                    )
                                    self.results.append(result)
                                    results.append(result)
        
        except Exception as e:
            print(f"[\u001b[33m!\u001b[0m] 证书查询失败: {e}")
        
        self.stats["certificate"] = len(results)
        print(f"[\u001b[32m+\u001b[0m] 证书透明度发现: {len(results)} 个新子域名")
        return results
    
    async def collect_from_hackertarget(self) -> List[SubdomainResult]:
        """从 HackerTarget API 收集子域名"""
        print(f"[\u001b[36m*\u001b[0m] HackerTarget 查询...")
        
        results = []
        
        try:
            async with AsyncHTTPClient() as client:
                url = f"https://api.hackertarget.com/hostsearch/?q={self.domain}"
                resp = await client.get(url)
                
                if resp["status"] == 200:
                    for line in resp["body"].strip().split('\n'):
                        if ',' in line:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                sub = parts[0].strip()
                                ip = parts[1].strip()
                                if sub.endswith(self.domain) and sub not in self.subdomains:
                                    self.subdomains.add(sub)
                                    result = SubdomainResult(
                                        subdomain=sub,
                                        ip=ip,
                                        source="hackertarget"
                                    )
                                    self.results.append(result)
                                    results.append(result)
        
        except Exception as e:
            print(f"[\u001b[33m!\u001b[0m] HackerTarget 查询失败: {e}")
        
        self.stats["search"] = len(results)
        print(f"[\u001b[32m+\u001b[0m] HackerTarget 发现: {len(results)} 个新子域名")
        return results
    
    async def collect_from_rapiddns(self) -> List[SubdomainResult]:
        """从 RapidDNS 收集子域名"""
        print(f"[\u001b[36m*\u001b[0m] RapidDNS 查询...")
        
        results = []
        
        try:
            async with AsyncHTTPClient() as client:
                url = f"https://rapiddns.io/subdomain/{self.domain}?full=1"
                resp = await client.get(url)
                
                if resp["status"] == 200:
                    # 提取域名
                    pattern = rf'([a-zA-Z0-9][-a-zA-Z0-9]*\.{re.escape(self.domain)})'
                    matches = re.findall(pattern, resp["body"])
                    
                    for sub in set(matches):
                        if sub not in self.subdomains:
                            self.subdomains.add(sub)
                            ip = (await self.dns.resolve_all(sub))[0] if await self.dns.resolve_all(sub) else None
                            result = SubdomainResult(
                                subdomain=sub,
                                ip=ip,
                                source="rapiddns"
                            )
                            self.results.append(result)
                            results.append(result)
        
        except Exception as e:
            print(f"[\u001b[33m!\u001b[0m] RapidDNS 查询失败: {e}")
        
        print(f"[\u001b[32m+\u001b[0m] RapidDNS 发现: {len(results)} 个新子域名")
        return results
    
    async def collect_from_webarchive(self) -> List[SubdomainResult]:
        """从 Web Archive 收集子域名"""
        print(f"[\u001b[36m*\u001b[0m] Web Archive 查询...")
        
        results = []
        
        try:
            async with AsyncHTTPClient() as client:
                url = f"https://web.archive.org/cdx/search/cdx?url=*.{self.domain}/*&output=json&collapse=urlkey&fl=original"
                resp = await client.get(url)
                
                if resp["status"] == 200:
                    try:
                        data = json.loads(resp["body"])
                        for entry in data:
                            if isinstance(entry, dict) and "original" in entry:
                                url = entry["original"]
                                # 提取域名
                                match = re.search(r'://([^/]+)', url)
                                if match:
                                    sub = match.group(1).lower()
                                    if sub.endswith(self.domain) and sub not in self.subdomains:
                                        self.subdomains.add(sub)
                                        ip = (await self.dns.resolve_all(sub))[0] if await self.dns.resolve_all(sub) else None
                                        result = SubdomainResult(
                                            subdomain=sub,
                                            ip=ip,
                                            source="webarchive"
                                        )
                                        self.results.append(result)
                                        results.append(result)
                    except json.JSONDecodeError:
                        pass
        
        except Exception as e:
            print(f"[\u001b[33m!\u001b[0m] Web Archive 查询失败: {e}")
        
        print(f"[\u001b[32m+\u001b[0m] Web Archive 发现: {len(results)} 个新子域名")
        return results
    
    async def run_full(self, methods: List[str] = None) -> List[SubdomainResult]:
        """完整收集"""
        methods = methods or ["dns", "certificate", "hackertarget", "rapiddns", "webarchive"]
        
        print(f"\n{'='*55}")
        print(f"子域名收集: {self.domain}")
        print(f"{'='*55}\n")
        
        start_time = time.time()
        
        if "dns" in methods:
            await self.collect_from_dns()
        
        if "certificate" in methods:
            await self.collect_from_certificate()
        
        if "hackertarget" in methods:
            await self.collect_from_hackertarget()
        
        if "rapiddns" in methods:
            await self.collect_from_rapiddns()
        
        if "webarchive" in methods:
            await self.collect_from_webarchive()
        
        elapsed = time.time() - start_time
        
        self.stats["total"] = len(self.results)
        
        print(f"\n{'='*55}")
        print(f"收集完成! 耗时: {elapsed:.2f}s")
        print(f"总计: {len(self.results)} 个子域名")
        print(f"{'='*55}\n")
        
        return self.results
    
    def get_subdomains(self) -> List[str]:
        """获取所有子域名列表"""
        return list(self.subdomains)
    
    def get_results(self) -> List[Dict]:
        """获取详细结果"""
        return [
            {
                "subdomain": r.subdomain,
                "ip": r.ip,
                "source": r.source
            }
            for r in self.results
        ]


# ============== 命令行入口 ==============

async def main(domain: str):
    collector = AsyncSubdomainCollector(domain)
    results = await collector.run_full()
    
    print("\n发现的子域名:")
    for r in results[:20]:
        print(f"  {r.subdomain} -> {r.ip or 'N/A'}")
    if len(results) > 20:
        print(f"  ... 还有 {len(results) - 20} 个")


if __name__ == "__main__":
    import sys
    domain = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    asyncio.run(main(domain))
