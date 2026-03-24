#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.1 - JavaScript 分析模块
从 JS 文件中提取 URL、API 端点、敏感信息
"""

import asyncio
import re
import json
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup


@dataclass
class JSAnalysisResult:
    """JS 分析结果"""
    js_url: str
    size: int = 0
    urls: Set[str] = field(default_factory=set)
    api_endpoints: List[str] = field(default_factory=list)
    secrets: List[Dict[str, str]] = field(default_factory=list)
    paths: Set[str] = field(default_factory=set)
    domains: Set[str] = field(default_factory=set)
    parameters: Set[str] = field(default_factory=set)
    technologies: Set[str] = field(default_factory=set)
    comments: List[str] = field(default_factory=list)


@dataclass
class PageJSResult:
    """页面 JS 分析结果"""
    target: str
    total_js_files: int = 0
    results: List[JSAnalysisResult] = field(default_factory=list)
    all_urls: Set[str] = field(default_factory=set)
    all_apis: List[str] = field(default_factory=list)
    all_secrets: List[Dict] = field(default_factory=list)
    all_domains: Set[str] = field(default_factory=set)


class JavaScriptAnalyzer:
    """
    JavaScript 分析器
    
    功能：
    - 提取页面中的 JS 文件
    - 解析 JS 中的 URL 和 API 端点
    - 检测敏感信息（API Key、密码等）
    - 识别技术栈
    """
    
    # URL 匹配模式
    URL_PATTERNS = [
        # 完整 URL
        r'https?://[^\s\'"<>]+',
        # 相对路径
        r'["\']/(api|v\d|graphql|rest|ajax)/[^\s\'"<>]+["\']',
        # API 端点
        r'["\'][/]?[\w\-/]+\.(?:json|xml|html?|php|asp)[\'"]',
    ]
    
    # 敏感信息模式
    SECRET_PATTERNS = [
        ('AWS Key', r'AKIA[0-9A-Z]{16}'),
        ('AWS Secret', r'(?i)aws(.{0,20})?secret(.{0,20})?[\'"][0-9a-zA-Z/+=]{40}[\'"]'),
        ('API Key', r'(?i)(api[_-]?key|apikey)[\s]*[:=]\s*[\'"][0-9a-zA-Z\-_]{20,}[\'"]'),
        ('Bearer Token', r'Bearer\s+[0-9a-zA-Z\-_\.]{20,}'),
        ('JWT', r'eyJ[a-zA-Z0-9\-_]+\.eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+'),
        ('Google API', r'AIza[0-9A-Za-z\-_]{35}'),
        ('Stripe Key', r'sk_[live|test]_[0-9a-zA-Z]{24}'),
        ('GitHub Token', r'ghp_[0-9a-zA-Z]{36}'),
        ('Slack Token', r'xox[baprs]-[0-9]{10,}-[0-9a-zA-Z]{24,}'),
        ('Private Key', r'-----BEGIN.*PRIVATE KEY-----'),
        ('Password', r'(?i)(password|passwd|pwd)[\s]*[:=]\s*[\'"][^\'"]{6,}[\'"]'),
        ('Secret', r'(?i)(secret|token|auth)[\s]*[:=]\s*[\'"][0-9a-zA-Z\-_]{16,}[\'"]'),
    ]
    
    # 技术栈特征
    TECH_SIGNATURES = {
        'React': [r'react\.production\.min\.js', r'__REACT_DEVTOOLS_GLOBAL_HOOK__', r'React\.createElement'],
        'Vue.js': [r'vue\.runtime\.min\.js', r'__VUE__', r'Vue\.component'],
        'Angular': [r'angular\.min\.js', r'ngModule', r'angular\.module'],
        'jQuery': [r'jquery[-.]?[\d.]*\.min\.js', r'\$\([^)]+\)', r'jQuery'],
        'Next.js': [r'__NEXT_DATA__', r'_next/static'],
        'Nuxt.js': [r'__NUXT__', r'_nuxt/'],
        'Express': [r'express', r'express\.static'],
        'Axios': [r'axios\.[get|post|put|delete]', r'axios\.defaults'],
        'GraphQL': [r'graphql', r'gql`', r'query\s*\{'],
        'Firebase': [r'firebaseapp\.com', r'firebase\.initializeApp'],
        'Stripe': [r'stripe\.js', r'Stripe\('],
        'Google Analytics': [r'google-analytics\.com', r'ga\('],
        'Sentry': [r'sentry\.io', r'Sentry\.init'],
        'Intercom': [r'intercom\.com', r'Intercom\('],
    }
    
    def __init__(self, target: str, timeout: int = 10, max_js_size: int = 5_000_000):
        """
        初始化分析器
        
        Args:
            target: 目标 URL
            timeout: 超时时间（秒）
            max_js_size: 最大 JS 文件大小（字节）
        """
        self.target = target
        self.timeout = timeout
        self.max_js_size = max_js_size
        self.result = PageJSResult(target=target)
    
    async def fetch_page(self) -> Optional[str]:
        """获取页面 HTML"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.target, timeout=self.timeout, ssl=False) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception as e:
            print(f"[!] 获取页面失败: {e}")
        return None
    
    def extract_js_urls(self, html: str) -> Set[str]:
        """从 HTML 中提取 JS URL"""
        js_urls = set()
        soup = BeautifulSoup(html, 'lxml')
        
        # <script src="...">
        for script in soup.find_all('script', src=True):
            src = script.get('src', '')
            if src:
                full_url = urljoin(self.target, src)
                js_urls.add(full_url)
        
        # <link href="*.js">
        for link in soup.find_all('link', href=True):
            href = link.get('href', '')
            if href.endswith('.js'):
                full_url = urljoin(self.target, href)
                js_urls.add(full_url)
        
        # 内联 JS 中的 URL
        for script in soup.find_all('script'):
            if script.string:
                inline_urls = self._extract_urls_from_js(script.string)
                # 将内联脚本作为特殊处理
                if inline_urls:
                    result = JSAnalysisResult(js_url=f"{self.target}#inline")
                    result.urls.update(inline_urls)
                    self.result.results.append(result)
        
        return js_urls
    
    async def analyze_js(self, js_url: str) -> Optional[JSAnalysisResult]:
        """分析单个 JS 文件"""
        result = JSAnalysisResult(js_url=js_url)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(js_url, timeout=self.timeout, ssl=False) as resp:
                    if resp.status != 200:
                        return None
                    
                    # 检查大小
                    content = await resp.text()
                    result.size = len(content)
                    
                    if result.size > self.max_js_size:
                        print(f"[!] JS 文件过大，跳过: {js_url}")
                        return None
                    
                    # 提取 URL
                    result.urls.update(self._extract_urls_from_js(content))
                    
                    # 提取 API 端点
                    result.api_endpoints = self._extract_api_endpoints(content)
                    
                    # 提取敏感信息
                    result.secrets = self._extract_secrets(content)
                    
                    # 提取路径
                    result.paths.update(self._extract_paths(content))
                    
                    # 提取域名
                    result.domains.update(self._extract_domains(content))
                    
                    # 提取参数
                    result.parameters.update(self._extract_parameters(content))
                    
                    # 识别技术栈
                    result.technologies.update(self._identify_technologies(content))
                    
                    # 提取注释
                    result.comments = self._extract_comments(content)
        
        except Exception as e:
            print(f"[!] 分析 JS 失败 {js_url}: {e}")
        
        return result
    
    def _extract_urls_from_js(self, content: str) -> Set[str]:
        """从 JS 内容中提取 URL"""
        urls = set()
        
        for pattern in self.URL_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # 清理
                if isinstance(match, tuple):
                    match = match[0]
                
                # 过滤无效
                if match.startswith(('http://', 'https://', '/', 'api/', 'v1/', 'v2/')):
                    # 构建完整 URL
                    if match.startswith('/'):
                        match = urljoin(self.target, match)
                    urls.add(match)
        
        return urls
    
    def _extract_api_endpoints(self, content: str) -> List[str]:
        """提取 API 端点"""
        endpoints = []
        
        # REST API 端点
        patterns = [
            r'["\']/(api|v\d|rest|graphql)/[a-zA-Z0-9_\-/]+["\']',
            r'["\'][a-zA-Z0-9_\-/]+\.(json|xml|php)["\']',
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.[a-z]+\(["\']([^"\']+)["\']',
            r'\.ajax\([^)]*url\s*:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[-1]
                
                if match and len(match) > 2:
                    endpoints.append(match)
        
        return list(set(endpoints))
    
    def _extract_secrets(self, content: str) -> List[Dict[str, str]]:
        """提取敏感信息"""
        secrets = []
        
        for name, pattern in self.SECRET_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # 截取上下文
                idx = content.find(match) if isinstance(match, str) else content.find(match[0])
                context = content[max(0, idx-50):idx+50] if idx > 0 else match
                
                secrets.append({
                    'type': name,
                    'value': match[:50] + '...' if len(str(match)) > 50 else match,
                    'context': context[:100],
                })
        
        return secrets
    
    def _extract_paths(self, content: str) -> Set[str]:
        """提取路径"""
        paths = set()
        
        # 相对路径
        pattern = r'["\'](/[a-zA-Z0-9_\-./]+)["\']'
        matches = re.findall(pattern, content)
        
        for path in matches:
            # 过滤静态资源
            if not any(ext in path for ext in ['.png', '.jpg', '.gif', '.css', '.woff']):
                paths.add(path)
        
        return paths
    
    def _extract_domains(self, content: str) -> Set[str]:
        """提取域名"""
        domains = set()
        
        pattern = r'https?://([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}'
        matches = re.findall(pattern, content)
        
        for match in matches:
            # 提取完整域名
            idx = content.find(match)
            if idx > 0:
                domain_match = re.search(r'https?://([a-zA-Z0-9][-a-zA-Z0-9.]+[a-zA-Z]{2,})', content[max(0,idx-10):idx+len(match)+20])
                if domain_match:
                    domains.add(domain_match.group(1))
        
        return domains
    
    def _extract_parameters(self, content: str) -> Set[str]:
        """提取参数名"""
        params = set()
        
        # URL 参数
        patterns = [
            r'[?&]([a-zA-Z_][a-zA-Z0-9_]*)=',
            r'params\s*:\s*\{([^}]+)\}',
            r'data\s*:\s*\{([^}]+)\}',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, str):
                    # 提取参数名
                    param_names = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', match)
                    params.update(param_names)
        
        return params
    
    def _identify_technologies(self, content: str) -> Set[str]:
        """识别技术栈"""
        technologies = set()
        
        for tech, patterns in self.TECH_SIGNATURES.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    technologies.add(tech)
                    break
        
        return technologies
    
    def _extract_comments(self, content: str) -> List[str]:
        """提取注释"""
        comments = []
        
        # 单行注释
        single_line = re.findall(r'//(.+)$', content, re.MULTILINE)
        comments.extend(single_line[:10])  # 限制数量
        
        # 多行注释
        multi_line = re.findall(r'/\*(.+?)\*/', content, re.DOTALL)
        comments.extend([c.replace('\n', ' ')[:100] for c in multi_line[:5]])
        
        return comments
    
    async def scan(self) -> PageJSResult:
        """
        执行完整分析
        
        Returns:
            PageJSResult: 分析结果
        """
        print(f"\n[*] JavaScript 分析: {self.target}")
        
        # 1. 获取页面
        print("[*] 获取页面 HTML...")
        html = await self.fetch_page()
        
        if not html:
            print("[!] 获取页面失败")
            return self.result
        
        # 2. 提取 JS URL
        print("[*] 提取 JS 文件...")
        js_urls = self.extract_js_urls(html)
        print(f"[+] 发现 {len(js_urls)} 个 JS 文件")
        
        self.result.total_js_files = len(js_urls)
        
        # 3. 分析每个 JS 文件
        print("[*] 分析 JS 文件...")
        for i, js_url in enumerate(js_urls[:20]):  # 限制数量
            print(f"    [{i+1}/{min(len(js_urls), 20)}] {js_url[:60]}...")
            
            result = await self.analyze_js(js_url)
            if result:
                self.result.results.append(result)
                self.result.all_urls.update(result.urls)
                self.result.all_apis.extend(result.api_endpoints)
                self.result.all_secrets.extend(result.secrets)
                self.result.all_domains.update(result.domains)
            
            await asyncio.sleep(0.1)  # 避免 WAF
        
        # 4. 统计
        print(f"\n[+] 分析完成:")
        print(f"    JS 文件: {self.result.total_js_files}")
        print(f"    URL: {len(self.result.all_urls)}")
        print(f"    API 端点: {len(self.result.all_apis)}")
        print(f"    敏感信息: {len(self.result.all_secrets)}")
        print(f"    域名: {len(self.result.all_domains)}")
        
        return self.result
    
    def print_results(self):
        """打印结果"""
        print("\n" + "=" * 60)
        print("JavaScript 分析报告")
        print("=" * 60)
        
        # API 端点
        if self.result.all_apis:
            print(f"\n[+] API 端点 ({len(self.result.all_apis)} 个):")
            for api in self.result.all_apis[:20]:
                print(f"  - {api}")
        
        # 敏感信息
        if self.result.all_secrets:
            print(f"\n[!] 敏感信息 ({len(self.result.all_secrets)} 个):")
            for secret in self.result.all_secrets[:10]:
                print(f"  类型: {secret['type']}")
                print(f"  值: {secret['value'][:50]}")
        
        # 技术栈
        all_techs = set()
        for r in self.result.results:
            all_techs.update(r.technologies)
        
        if all_techs:
            print(f"\n[+] 技术栈:")
            for tech in all_techs:
                print(f"  - {tech}")
        
        # 新域名
        if self.result.all_domains:
            print(f"\n[+] 发现域名 ({len(self.result.all_domains)} 个):")
            for domain in sorted(self.result.all_domains)[:15]:
                print(f"  - {domain}")


# ============== 使用示例 ==============

async def main():
    """示例：JS 分析"""
    
    analyzer = JavaScriptAnalyzer("https://example.com")
    result = await analyzer.scan()
    analyzer.print_results()


if __name__ == "__main__":
    asyncio.run(main())
