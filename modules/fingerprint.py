#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指纹识别模块

⚠️ 已废弃警告 ⚠
--------------
此模块已废弃，建议使用异步版本：
    from modules.js_analyzer import JSAnalyzer  # 包含指纹识别功能

原因：
    1. 使用同步 HTTPClient，无 SSRF 防护
    2. 不符合项目异步架构

迁移示例：
    # 旧代码
    scanner = FingerprintScanner(target)
    results = scanner.scan()
    
    # 新代码
    async with JSAnalyzer(target) as analyzer:
        results = await analyzer.detect_tech_stack()

废弃版本: v3.3.0
移除版本: v4.0.0
"""

import warnings

warnings.warn(
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️  FingerprintScanner 已废弃\n"
    "请使用: from modules.js_analyzer import JSAnalyzer\n"
    "原因: 同步方式、无 SSRF 防护\n"
    "废弃版本: v3.3.0 | 移除版本: v4.0.0\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    DeprecationWarning,
    stacklevel=2
)

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, HTTPClient
from config import CONFIG, FINGERPRINTS


class FingerprintScanner:
    """Web指纹扫描器"""
    
    def __init__(self, target, timeout=None):
        self.target = target if target.startswith('http') else f"http://{target}"
        self.timeout = timeout or CONFIG.get('timeout', 30)
        self.client = HTTPClient(timeout=10)
        self.fingerprints = []
        self.details = {}
    
    def fetch_page(self):
        """获取页面内容"""
        Logger.info(f"正在获取 {self.target} 页面内容...")
        
        result = self.client.get(self.target)
        
        if result['status'] == 0:
            Logger.error(f"无法访问目标: {result.get('error', 'Unknown error')}")
            return None
        
        self.details['url'] = self.target
        self.details['status'] = result['status']
        self.details['headers'] = result.get('headers', {})
        self.details['body'] = result.get('body', '')
        self.details['size'] = len(self.details['body'])
        
        Logger.success(f"页面获取成功 (状态码: {result['status']}, 大小: {self.details['size']} bytes)")
        
        return self.details
    
    def identify_server(self):
        """识别服务器类型"""
        headers = self.details.get('headers', {})
        
        server = headers.get('Server', headers.get('server', ''))
        if server:
            self.fingerprints.append(f"Server: {server}")
        
        x_powered = headers.get('X-Powered-By', headers.get('x-powered-by', ''))
        if x_powered:
            self.fingerprints.append(f"Tech: {x_powered}")
        
        return server, x_powered
    
    def identify_framework(self):
        """识别Web框架"""
        body = self.details.get('body', '')
        headers = self.details.get('headers', {})
        combined = body + str(headers)
        
        found_frameworks = []
        
        for name, patterns in FINGERPRINTS.items():
            for pattern in patterns:
                if pattern.lower() in combined.lower():
                    found_frameworks.append(name)
                    break
        
        self.fingerprints.extend(found_frameworks)
        
        return list(set(found_frameworks))
    
    def identify_cms(self):
        """识别CMS"""
        body = self.details.get('body', '')
        
        cms_signatures = {
            'WordPress': ['wp-content', 'wp-includes', 'wp-login.php', 'xmlrpc.php'],
            'Drupal': ['Drupal.settings', 'misc/drupal.js', '/sites/default/'],
            'Joomla': ['Joomla', 'option=com_', '/components/com_'],
            'Discuz!': ['Discuz', 'discuz_uid', 'logging.php'],
            'DedeCMS': ['dedecms', 'dedeajax', '/dede/'],
            'Typecho': ['typecho', 'Typecho'],
            'Z-Blog': ['Z-Blog', 'zblog'],
            'EmpireCMS': ['EmpireCMS', 'empirecms']
        }
        
        found_cms = []
        
        for cms, patterns in cms_signatures.items():
            for pattern in patterns:
                if pattern.lower() in body.lower():
                    found_cms.append(cms)
                    break
        
        self.fingerprints.extend(found_cms)
        
        return found_cms
    
    def identify_frontend(self):
        """识别前端框架"""
        body = self.details.get('body', '')
        
        frontend_signatures = {
            'Vue.js': ['vue', 'Vue', '__vue__', 'v-cloak'],
            'React': ['react', 'React', '_reactRootContainer', 'react-dom'],
            'Angular': ['angular', 'ng-version', 'ng-app', 'ng-controller'],
            'jQuery': ['jquery', 'jQuery', '$().jquery'],
            'Bootstrap': ['bootstrap', 'Bootstrap'],
            'Layui': ['layui', 'Layui'],
            'Element UI': ['element-ui', 'elementui', 'Element UI'],
            'Ant Design': ['ant-design', 'antd']
        }
        
        found_frontend = []
        
        for framework, patterns in frontend_signatures.items():
            for pattern in patterns:
                if pattern.lower() in body.lower():
                    found_frontend.append(framework)
                    break
        
        self.fingerprints.extend(found_frontend)
        
        return found_frontend
    
    def identify_waf(self):
        """识别WAF"""
        headers = self.details.get('headers', {})
        body = self.details.get('body', '')
        
        waf_signatures = {
            'CloudFlare': ['cf-ray', 'cloudflare'],
            'ModSecurity': ['ModSecurity', 'mod_security'],
            '阿里云盾': ['aliyun', 'aliyundun'],
            '腾讯云WAF': ['waf.tencent'],
            '安全狗': ['safedog', 'SafeDog'],
            '宝塔防火墙': ['btwaf'],
            '360网站卫士': ['360wzb']
        }
        
        found_waf = []
        combined = str(headers).lower() + body.lower()
        
        for waf, patterns in waf_signatures.items():
            for pattern in patterns:
                if pattern.lower() in combined:
                    found_waf.append(waf)
                    break
        
        if found_waf:
            self.fingerprints.extend([f"WAF: {w}" for w in found_waf])
        
        return found_waf
    
    def extract_meta_info(self):
        """提取元信息"""
        body = self.details.get('body', '')
        
        meta_info = {}
        
        # 提取title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', body, re.IGNORECASE)
        if title_match:
            meta_info['title'] = title_match.group(1).strip()
        
        # 提取description
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if desc_match:
            meta_info['description'] = desc_match.group(1).strip()
        
        # 提取keywords
        kw_match = re.search(r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if kw_match:
            meta_info['keywords'] = kw_match.group(1).strip()
        
        # 提取generator
        gen_match = re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if gen_match:
            meta_info['generator'] = gen_match.group(1).strip()
        
        self.details['meta'] = meta_info
        
        if meta_info.get('generator'):
            self.fingerprints.append(f"Generator: {meta_info['generator']}")
        
        return meta_info
    
    def run(self):
        """执行完整指纹识别"""
        # 获取页面
        if not self.fetch_page():
            return {'fingerprints': [], 'details': {}}
        
        Logger.info(f"正在进行指纹识别...")
        
        # 各类识别
        self.identify_server()
        frameworks = self.identify_framework()
        cms = self.identify_cms()
        frontend = self.identify_frontend()
        waf = self.identify_waf()
        meta = self.extract_meta_info()
        
        # 去重
        self.fingerprints = list(set(self.fingerprints))
        
        Logger.success(f"识别到 {len(self.fingerprints)} 个指纹")
        
        for fp in self.fingerprints:
            print(f"  - {fp}")
        
        return {
            'fingerprints': self.fingerprints,
            'details': {
                'title': self.details.get('meta', {}).get('title', ''),
                'server': self.details.get('headers', {}).get('Server', ''),
                'frameworks': frameworks,
                'cms': cms,
                'frontend': frontend,
                'waf': waf,
                'meta': meta
            }
        }


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = 'http://baidu.com'
    
    scanner = FingerprintScanner(target)
    results = scanner.run()
    
    print(f"\n指纹信息:")
    for fp in results['fingerprints']:
        print(f"  {fp}")
