#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子域名收集模块 v2.1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, DNSResolver, CommandRunner, ProgressBar, RateLimiter
from config import CONFIG


class SubdomainCollector:
    """子域名收集器"""
    
    def __init__(self, domain, threads=None, rate_limit=3):
        self.domain = domain
        self.threads = threads or CONFIG.get('subdomain_threads', 10)
        self.rate_limiter = RateLimiter(rate_limit)
        self.subdomains = set()
        self.results = []
    
    def collect_from_dns(self, prefixes=None):
        """DNS枚举收集子域名"""
        Logger.info(f"正在通过DNS枚举收集 {self.domain} 的子域名...")
        
        prefixes = prefixes or CONFIG.get('subdomain_prefixes', [])
        found = []
        
        progress = ProgressBar(len(prefixes), "DNS枚举")
        
        for prefix in prefixes:
            subdomain = f"{prefix}.{self.domain}"
            ip = DNSResolver.resolve(subdomain)
            
            if ip:
                self.subdomains.add(subdomain)
                found.append({
                    'subdomain': subdomain,
                    'ip': ip
                })
            
            progress.update()
        
        progress.finish()
        Logger.success(f"DNS枚举发现 {len(found)} 个子域名")
        return found
    
    def collect_from_certificate(self):
        """从证书透明度日志收集子域名"""
        Logger.info(f"正在从证书透明度日志收集子域名...")
        
        found = []
        self.rate_limiter.wait()
        
        # 使用 crt.sh API
        try:
            import urllib.request
            import json
            
            url = f"https://crt.sh/?q=%.{self.domain}&output=json"
            req = urllib.request.Request(url, headers={'User-Agent': CONFIG['user_agent']})
            response = urllib.request.urlopen(req, timeout=30)
            
            data = json.loads(response.read().decode('utf-8'))
            
            for entry in data:
                name = entry.get('name_value', '')
                for sub in name.split('\n'):
                    sub = sub.strip().lower()
                    if sub.endswith(self.domain) and '*' not in sub:
                        if sub not in self.subdomains:
                            self.subdomains.add(sub)
                            ip = DNSResolver.resolve(sub)
                            found.append({
                                'subdomain': sub,
                                'ip': ip,
                                'source': 'certificate'
                            })
            
            Logger.success(f"证书透明度日志发现 {len(found)} 个新子域名")
        
        except Exception as e:
            Logger.warn(f"证书透明度查询失败: {e}")
        
        return found
    
    def collect_from_search_engine(self):
        """从搜索引擎收集子域名（简单实现）"""
        Logger.info(f"正在从搜索引擎收集子域名...")
        
        found = []
        self.rate_limiter.wait()
        
        # 使用 hackertarget API
        try:
            import urllib.request
            
            url = f"https://api.hackertarget.com/hostsearch/?q={self.domain}"
            req = urllib.request.Request(url, headers={'User-Agent': CONFIG['user_agent']})
            response = urllib.request.urlopen(req, timeout=30)
            
            content = response.read().decode('utf-8')
            
            for line in content.strip().split('\n'):
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        sub = parts[0].strip()
                        ip = parts[1].strip()
                        if sub.endswith(self.domain) and sub not in self.subdomains:
                            self.subdomains.add(sub)
                            found.append({
                                'subdomain': sub,
                                'ip': ip,
                                'source': 'search_engine'
                            })
            
            Logger.success(f"搜索引擎发现 {len(found)} 个新子域名")
        
        except Exception as e:
            Logger.warn(f"搜索引擎查询失败: {e}")
        
        return found
    
    def run(self, methods=None):
        """执行子域名收集
        
        Args:
            methods: 收集方法列表，可选: dns, certificate, search_engine
        
        Returns:
            list: 发现的子域名列表
        """
        methods = methods or ['dns', 'certificate', 'search_engine']
        
        if 'dns' in methods:
            dns_results = self.collect_from_dns()
            self.results.extend(dns_results)
        
        if 'certificate' in methods:
            cert_results = self.collect_from_certificate()
            self.results.extend(cert_results)
        
        if 'search_engine' in methods:
            search_results = self.collect_from_search_engine()
            self.results.extend(search_results)
        
        return self.results
    
    def get_all_subdomains(self):
        """获取所有发现的子域名"""
        return list(self.subdomains)
    
    def get_all_ips(self):
        """获取所有解析的IP"""
        ips = set()
        for result in self.results:
            if result.get('ip'):
                ips.add(result['ip'])
        return list(ips)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        domain = sys.argv[1]
    else:
        domain = 'baidu.com'
    
    collector = SubdomainCollector(domain)
    results = collector.run()
    
    print(f"\n发现 {len(results)} 个子域名:")
    for r in results:
        print(f"  {r['subdomain']} -> {r.get('ip', 'N/A')}")
