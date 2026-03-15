#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
敏感信息检测模块 v2.1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, HTTPClient, SensitiveDetector, ProgressBar, RateLimiter
from config import CONFIG, SENSITIVE_PATHS


class SensitiveScanner:
    """敏感信息扫描器"""
    
    def __init__(self, target, rate_limit=2):
        self.target = target if target.startswith('http') else f"http://{target}"
        self.rate_limiter = RateLimiter(rate_limit)
        self.client = HTTPClient(timeout=10, rate_limit=rate_limit)
        self.findings = []
    
    def scan_common_files(self):
        """扫描常见敏感文件"""
        Logger.info(f"正在扫描敏感文件...")
        
        sensitive_files = [
            '/.env',
            '/.git/config',
            '/.svn/entries',
            '/web.config',
            '/config.php',
            '/database.yml',
            '/wp-config.php',
            '/.htaccess',
            '/robots.txt',
            '/sitemap.xml',
            '/phpinfo.php',
            '/info.php',
            '/.DS_Store',
            '/backup.sql',
            '/backup.zip',
            '/admin.php',
            '/admin/',
            '/api/',
            '/swagger-ui.html',
            '/api-docs/',
            '/graphql',
            '/.well-known/security.txt',
        ]
        
        progress = ProgressBar(len(sensitive_files), "敏感文件扫描")
        found_files = []
        
        for path in sensitive_files:
            self.rate_limiter.wait()
            url = f"{self.target}{path}"
            response = self.client.get(url)
            
            if response['status'] == 200:
                # 扫描文件内容中的敏感信息
                sensitive_findings = SensitiveDetector.scan(response.get('body', ''))
                
                finding = {
                    'path': path,
                    'url': url,
                    'status': response['status'],
                    'size': len(response.get('body', '')),
                    'sensitive_info': sensitive_findings
                }
                
                found_files.append(finding)
                
                if sensitive_findings:
                    Logger.success(f"  发现敏感文件: {path} (含敏感信息)")
                    for info in sensitive_findings:
                        Logger.warn(f"    - {info['type']}: {info['count']} 处")
                else:
                    Logger.info(f"  发现文件: {path}")
            
            progress.update()
        
        progress.finish()
        self.findings.extend(found_files)
        
        return found_files
    
    def scan_js_files(self):
        """扫描JS文件中的敏感信息"""
        Logger.info(f"正在扫描JS文件中的敏感信息...")
        
        # 先获取首页
        response = self.client.get(self.target)
        
        if response['status'] != 200:
            return []
        
        body = response.get('body', '')
        
        # 提取JS文件URL
        import re
        js_pattern = r'src=["\']([^"\']*\.js[^"\']*)["\']'
        js_urls = re.findall(js_pattern, body)
        
        # 去重并处理相对路径
        js_urls = list(set(js_urls))
        processed_urls = []
        
        for url in js_urls:
            if url.startswith('http'):
                processed_urls.append(url)
            elif url.startswith('//'):
                processed_urls.append(f"http:{url}")
            else:
                processed_urls.append(f"{self.target.rstrip('/')}{url if url.startswith('/') else '/' + url}")
        
        if not processed_urls:
            Logger.info("  未发现JS文件")
            return []
        
        progress = ProgressBar(min(len(processed_urls), 10), "JS文件扫描")  # 最多扫描10个
        js_findings = []
        
        for url in processed_urls[:10]:
            self.rate_limiter.wait()
            js_response = self.client.get(url)
            
            if js_response['status'] == 200:
                sensitive = SensitiveDetector.scan(js_response.get('body', ''))
                
                if sensitive:
                    finding = {
                        'file': url,
                        'sensitive_info': sensitive
                    }
                    js_findings.append(finding)
                    
                    Logger.success(f"  发现敏感信息: {url}")
                    for info in sensitive:
                        Logger.warn(f"    - {info['type']}: {info['count']} 处")
            
            progress.update()
        
        progress.finish()
        self.findings.extend(js_findings)
        
        return js_findings
    
    def scan_response_headers(self):
        """扫描响应头中的敏感信息"""
        Logger.info(f"正在扫描响应头...")
        
        response = self.client.get(self.target)
        
        headers = response.get('headers', {})
        sensitive_headers = []
        
        # 检查敏感头
        sensitive_header_names = [
            'x-powered-by', 'server', 'x-aspnet-version',
            'x-runtime', 'x-version', 'x-api-version'
        ]
        
        for name, value in headers.items():
            if name.lower() in sensitive_header_names:
                sensitive_headers.append({
                    'header': name,
                    'value': value
                })
                Logger.info(f"  发现信息泄露: {name}: {value}")
        
        # 检查Cookie安全
        set_cookie = headers.get('Set-Cookie', headers.get('set-cookie', ''))
        if set_cookie and 'httponly' not in set_cookie.lower():
            sensitive_headers.append({
                'header': 'Set-Cookie',
                'value': '缺少HttpOnly标记'
            })
            Logger.warn(f"  Cookie安全: 缺少HttpOnly标记")
        
        if not sensitive_headers:
            Logger.info("  响应头安全")
        
        return sensitive_headers
    
    def run(self):
        """执行完整敏感信息扫描"""
        results = {
            'files': [],
            'js_files': [],
            'headers': []
        }
        
        results['files'] = self.scan_common_files()
        results['js_files'] = self.scan_js_files()
        results['headers'] = self.scan_response_headers()
        
        return results


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = 'http://baidu.com'
    
    scanner = SensitiveScanner(target)
    results = scanner.run()
    
    print(f"\n敏感文件: {len(results['files'])}")
    print(f"JS敏感信息: {len(results['js_files'])}")
    print(f"响应头泄露: {len(results['headers'])}")
