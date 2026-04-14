#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子域名接管检测模块 v2.2
检测未使用的DNS记录是否可被接管
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, HTTPClient, DNSResolver
from config import CONFIG


class SubdomainTakeoverScanner:
    """子域名接管扫描器"""
    
    # 各平台的接管特征
    TAKEOVER_SIGNATURES = {
        'GitHub Pages': {
            'cname': ['github.io', 'githubusercontent.com'],
            'response': ['There isn\'t a GitHub Pages site here', 'For root URLs (like http://example.com/)'],
            'severity': 'HIGH'
        },
        'Heroku': {
            'cname': ['herokuapp.com'],
            'response': ['herokucdn.com/error-pages/no-such-app.html', 'no such app'],
            'severity': 'HIGH'
        },
        'Shopify': {
            'cname': ['myshopify.com'],
            'response': ['Sorry, this shop is currently unavailable', 'Only one step left!'],
            'severity': 'HIGH'
        },
        'Tumblr': {
            'cname': ['tumblr.com'],
            'response': ['Whatever you were looking for doesn\'t currently exist', 'There\'s nothing here'],
            'severity': 'HIGH'
        },
        'WordPress': {
            'cname': ['wordpress.com'],
            'response': ['Do you want to register', 'wordpress.com'],
            'severity': 'MEDIUM'
        },
        'S3 Bucket': {
            'cname': ['amazonaws.com', 's3.amazonaws.com'],
            'response': ['NoSuchBucket', 'The specified bucket does not exist'],
            'severity': 'HIGH'
        },
        'Azure': {
            'cname': ['azurewebsites.net', 'cloudapp.net'],
            'response': ['404 Web Site not found', 'Error 404 - Web app not found'],
            'severity': 'HIGH'
        },
        'Firebase': {
            'cname': ['firebaseapp.com'],
            'response': ['Hosting site not found', 'Firebase Hosting'],
            'severity': 'HIGH'
        },
        'Netlify': {
            'cname': ['netlify.com'],
            'response': ['Not Found - Request ID', 'netlify'],
            'severity': 'MEDIUM'
        },
        'Vercel': {
            'cname': ['vercel.app'],
            'response': ['The deployment could not be found', 'VERCEL'],
            'severity': 'MEDIUM'
        },
        'Fastly': {
            'cname': ['fastly.net'],
            'response': ['Fastly error: unknown domain', 'Please check the URL'],
            'severity': 'MEDIUM'
        },
        'Ghost': {
            'cname': ['ghost.io'],
            'response': ['The thing you were looking for is no longer here', 'ghost'],
            'severity': 'MEDIUM'
        },
        'Readme.io': {
            'cname': ['readme.io'],
            'response': ['Project doesnt exist... yet', 'readme'],
            'severity': 'MEDIUM'
        },
        'Bitbucket': {
            'cname': ['bitbucket.io'],
            'response': ['Repository not found', 'bitbucket'],
            'severity': 'MEDIUM'
        },
    }
    
    def __init__(self, subdomains):
        """
        初始化
        
        Args:
            subdomains: 子域名列表
        """
        self.subdomains = subdomains
        self.client = HTTPClient(timeout=10)
        self.vulnerable = []
    
    def check_cname(self, domain):
        """检查CNAME记录"""
        import subprocess
        
        try:
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['nslookup', '-type=CNAME', domain],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding='gbk',
                    errors='ignore'
                )
            else:
                result = subprocess.run(
                    ['dig', '+short', 'CNAME', domain],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            output = result.stdout.lower()
            
            # 检查是否指向已知平台
            for platform, info in self.TAKEOVER_SIGNATURES.items():
                for cname in info['cname']:
                    if cname.lower() in output:
                        return {
                            'platform': platform,
                            'cname': cname,
                            'severity': info['severity']
                        }
            
            return None
            
        except Exception as e:
            return None
    
    def check_response(self, domain, platform_info):
        """检查响应内容是否包含接管特征"""
        url = f"http://{domain}"
        response = self.client.get(url)
        
        if response['status'] == 0:
            return False
        
        body = response.get('body', '').lower()
        
        for signature in platform_info['response']:
            if signature.lower() in body:
                return True
        
        return False
    
    def scan(self):
        """执行子域名接管扫描"""
        Logger.info(f"正在检测 {len(self.subdomains)} 个子域名的接管风险...")
        
        for item in self.subdomains:
            domain = item.get('subdomain') if isinstance(item, dict) else item
            
            # 检查CNAME
            cname_info = self.check_cname(domain)
            
            if cname_info:
                # 检查响应是否确认可接管
                is_vulnerable = self.check_response(domain, cname_info)
                
                if is_vulnerable:
                    vulnerability = {
                        'domain': domain,
                        'platform': cname_info['platform'],
                        'severity': cname_info['severity'],
                        'cname': cname_info['cname'],
                        'status': 'VULNERABLE'
                    }
                    self.vulnerable.append(vulnerability)
                    Logger.success(f"  [!] 发现可接管: {domain} -> {cname_info['platform']} ({cname_info['severity']})")
                else:
                    # 可能存在风险，但不确定
                    Logger.info(f"  [?] 潜在风险: {domain} -> {cname_info['platform']}")
        
        if not self.vulnerable:
            Logger.info("  未发现可接管的子域名")
        
        return self.vulnerable
    
    def run(self):
        """执行扫描"""
        return self.scan()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        domains = sys.argv[1:]
    else:
        domains = ['test.github.io']
    
    scanner = SubdomainTakeoverScanner(domains)
    results = scanner.run()
    
    print(f"\n发现 {len(results)} 个可接管子域名")
    for r in results:
        print(f"  {r['domain']} -> {r['platform']} ({r['severity']})")
