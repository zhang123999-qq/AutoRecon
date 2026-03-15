#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CDN检测模块 v2.1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, DNSResolver, HTTPClient, CDNDetector
from config import CONFIG


class CDNScanner:
    """CDN扫描器"""
    
    def __init__(self, target):
        self.target = target if target.startswith('http') else f"http://{target}"
        self.domain = target.replace('http://', '').replace('https://', '').split('/')[0]
        self.results = {}
    
    def detect(self):
        """检测CDN"""
        Logger.info(f"正在检测 {self.domain} 的CDN...")
        
        # 解析IP
        ips = DNSResolver.resolve_all(self.domain)
        self.results['ips'] = ips
        
        Logger.info(f"  解析到 {len(ips)} 个IP: {ips[:5]}{'...' if len(ips) > 5 else ''}")
        
        # 从IP检测CDN
        cdn_from_ip = None
        for ip in ips:
            cdn = CDNDetector.detect_from_ip(ip)
            if cdn:
                cdn_from_ip = cdn
                break
        
        if cdn_from_ip:
            Logger.success(f"  IP检测到CDN: {cdn_from_ip}")
        
        # 从响应头检测CDN
        client = HTTPClient(timeout=10)
        response = client.get(self.target)
        
        cdn_from_headers = None
        if response['status'] > 0:
            headers = response.get('headers', {})
            cdn_from_headers = CDNDetector.detect_from_headers(headers)
            
            if cdn_from_headers:
                Logger.success(f"  响应头检测到CDN: {cdn_from_headers}")
            
            # 显示相关CDN头
            cdn_headers = ['cf-ray', 'x-cache', 'server', 'via', 'x-amz-cf-id', 'x-served-by']
            for h in cdn_headers:
                if h in {k.lower() for k in headers.keys()}:
                    for k, v in headers.items():
                        if k.lower() == h:
                            Logger.info(f"  {k}: {v}")
                            break
        
        # 综合结果
        if cdn_from_ip and cdn_from_headers:
            self.results['cdn'] = cdn_from_ip if cdn_from_ip == cdn_from_headers else f"{cdn_from_ip}/{cdn_from_headers}"
        else:
            self.results['cdn'] = cdn_from_ip or cdn_from_headers
        
        if self.results['cdn']:
            Logger.success(f"最终检测结果: {self.results['cdn']}")
        else:
            Logger.info(f"未检测到CDN（可能是源站或未知的CDN）")
        
        return self.results
    
    def get_cdn(self):
        """获取CDN名称"""
        return self.results.get('cdn')
    
    def is_using_cdn(self):
        """判断是否使用CDN"""
        return bool(self.results.get('cdn'))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = 'baidu.com'
    
    scanner = CDNScanner(target)
    results = scanner.detect()
    
    print(f"\nCDN: {results.get('cdn', 'None')}")
