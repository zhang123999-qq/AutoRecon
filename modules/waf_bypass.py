#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF绕过检测模块 v2.2
检测并尝试绕过Web应用防火墙
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, HTTPClient
from config import CONFIG


class WAFBypassScanner:
    """WAF绕过扫描器"""
    
    WAF_SIGNATURES = {
        'CloudFlare': {
            'headers': ['cf-ray', 'cloudflare'],
            'block_code': [403, 503],
            'block_content': ['cloudflare', 'ray id', 'cf-ray']
        },
        'ModSecurity': {
            'headers': ['modsecurity'],
            'block_code': [403],
            'block_content': ['modsecurity', 'not acceptable']
        },
        '阿里云盾': {
            'headers': [],
            'block_code': [405, 403],
            'block_content': ['aliyun', 'blocked', '安全拦截']
        },
        '腾讯云WAF': {
            'headers': [],
            'block_code': [403],
            'block_content': ['waf.tencent', '安全防护']
        },
        '安全狗': {
            'headers': [],
            'block_code': [403, 404],
            'block_content': ['safedog', '安全狗', '请求被拦截']
        },
        '宝塔防火墙': {
            'headers': [],
            'block_code': [403],
            'block_content': ['btwaf', '宝塔', '请求频率过高']
        },
        '360网站卫士': {
            'headers': [],
            'block_code': [403],
            'block_content': ['360wzb', '360网站卫士']
        },
        '百度云加速': {
            'headers': [],
            'block_code': [403],
            'block_content': ['百度云加速', 'yunjiasu']
        }
    }
    
    # 绕过payload
    BYPASS_PAYLOADS = {
        'headers': [
            {'X-Forwarded-For': '127.0.0.1'},
            {'X-Real-IP': '127.0.0.1'},
            {'X-Originating-IP': '127.0.0.1'},
            {'X-Remote-IP': '127.0.0.1'},
            {'X-Client-IP': '127.0.0.1'},
            {'X-Forwarded-Host': 'localhost'},
            {'X-Host': 'localhost'},
            {'X-Forwarded-Server': 'localhost'},
            {'X-HTTP-Host-Override': 'localhost'},
        ],
        'path_tricks': [
            '/{path}/',           # 路径斜杠
            '/{path}/*',          # 通配符
            '/{path}.json',       # 扩展名
            '/{path}%00',         # 空字节
            '/{path}%0a',         # 换行
            '/{path}%09',         # Tab
            '/./{path}',          # 点号
            '/{path}/..;',        # 目录穿越
        ],
        'encoding': [
            'URL编码',
            '双重URL编码',
            'Unicode编码',
            'HTML实体编码',
            'Base64编码'
        ]
    }
    
    def __init__(self, target):
        self.target = target if target.startswith('http') else f"http://{target}"
        self.client = HTTPClient(timeout=10)
        self.waf_detected = None
        self.bypass_results = []
    
    def detect_waf(self):
        """检测WAF"""
        Logger.info(f"正在检测 {self.target} 的WAF...")
        
        # 发送正常请求
        normal_response = self.client.get(self.target)
        
        # 发送恶意请求触发WAF
        test_payloads = [
            "/?id=1' OR '1'='1",
            "/?id=1 AND 1=1",
            "/?file=../../../etc/passwd",
            "/?<script>alert(1)</script>",
        ]
        
        for payload in test_payloads:
            test_url = f"{self.target}{payload}"
            response = self.client.get(test_url)
            
            # 检查响应头和内容
            headers_str = str(response.get('headers', {})).lower()
            body = response.get('body', '').lower()
            
            for waf_name, signatures in self.WAF_SIGNATURES.items():
                # 检查头
                for header in signatures['headers']:
                    if header.lower() in headers_str:
                        self.waf_detected = waf_name
                        Logger.success(f"  检测到WAF: {waf_name} (通过响应头)")
                        return waf_name
                
                # 检查状态码和内容
                if response['status'] in signatures['block_code']:
                    for content in signatures['block_content']:
                        if content.lower() in body:
                            self.waf_detected = waf_name
                            Logger.success(f"  检测到WAF: {waf_name} (通过阻断响应)")
                            return waf_name
        
        if not self.waf_detected:
            Logger.info("  未检测到已知WAF")
        
        return self.waf_detected
    
    def test_header_bypass(self):
        """测试头部绕过"""
        Logger.info("  测试头部绕过...")
        
        success_bypasses = []
        
        for header in self.BYPASS_PAYLOADS['headers']:
            header_name = list(header.keys())[0]
            header_value = list(header.values())[0]
            
            response = self.client.get(self.target, headers=header)
            
            if response['status'] == 200:
                success_bypasses.append({
                    'method': 'Header',
                    'payload': f"{header_name}: {header_value}",
                    'status': '可能成功'
                })
                Logger.success(f"    [+] {header_name}: {header_value}")
        
        return success_bypasses
    
    def test_path_bypass(self):
        """测试路径绕过"""
        Logger.info("  测试路径绕过...")
        
        success_bypasses = []
        test_path = "admin"  # 测试路径
        
        for trick in self.BYPASS_PAYLOADS['path_tricks']:
            path = trick.format(path=test_path)
            url = f"{self.target}{path}"
            
            response = self.client.get(url)
            
            if response['status'] not in [403, 503]:
                success_bypasses.append({
                    'method': 'Path',
                    'payload': path,
                    'status': response['status']
                })
                Logger.success(f"    [+] {path} -> {response['status']}")
        
        return success_bypasses
    
    def run(self):
        """执行WAF检测和绕过测试"""
        Logger.info(f"开始WAF绕过测试...")
        
        # 检测WAF
        waf = self.detect_waf()
        
        results = {
            'waf': waf,
            'bypass': []
        }
        
        if waf:
            # 测试绕过
            results['bypass'].extend(self.test_header_bypass())
            results['bypass'].extend(self.test_path_bypass())
            
            if results['bypass']:
                Logger.success(f"发现 {len(results['bypass'])} 个可能的绕过方法")
            else:
                Logger.info("未发现有效绕过方法")
        
        return results


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = 'http://example.com'
    
    scanner = WAFBypassScanner(target)
    results = scanner.run()
    
    print(f"\nWAF: {results['waf'] or 'None'}")
    print(f"Bypass: {len(results['bypass'])} methods")
