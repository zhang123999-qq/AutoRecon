#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 漏洞扫描模块
检测常见 Web 漏洞: 敏感文件泄露、目录遍历、未授权访问等
"""

import asyncio
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.async_engine import AsyncHTTPClient, AsyncProgressBar


class Severity(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Vulnerability:
    """漏洞信息"""
    name: str
    url: str
    severity: Severity
    description: str
    evidence: str = ""
    references: List[str] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


class VulnerabilityScanner:
    """漏洞扫描器"""
    
    def __init__(self, target: str, threads: int = 20):
        self.target = target
        self.threads = threads
        self.vulnerabilities: List[Vulnerability] = []
    
    async def _check_path(self, client: AsyncHTTPClient, path: str, expected_status: List[int] = None) -> Dict:
        """检查单个路径"""
        url = f"http://{self.target}{path}"
        try:
            resp = await client.get(url, allow_redirects=False)
            return {
                "url": url,
                "path": path,
                "status": resp.get("status", 0),
                "length": resp.get("length", 0),
                "body": resp.get("body", "")[:500],
                "headers": resp.get("headers", {})
            }
        except:
            return {"url": url, "path": path, "status": 0}
    
    async def scan_sensitive_files(self) -> List[Vulnerability]:
        """扫描敏感文件泄露"""
        print("[\u001b[36m*\u001b[0m] 扫描敏感文件...")
        
        results = []
        
        # 敏感文件列表
        sensitive_paths = [
            # 版本控制
            ("/.git/config", "Git 配置文件泄露", Severity.HIGH),
            ("/.git/HEAD", "Git HEAD 泄露", Severity.MEDIUM),
            ("/.svn/entries", "SVN 配置泄露", Severity.HIGH),
            ("/.hg/", "Mercurial 配置泄露", Severity.HIGH),
            
            # 配置文件
            ("/.env", "环境变量文件泄露", Severity.HIGH),
            ("/config.php", "PHP 配置文件", Severity.MEDIUM),
            ("/configuration.php", "Joomla 配置文件", Severity.HIGH),
            ("/wp-config.php", "WordPress 配置文件", Severity.HIGH),
            ("/settings.py", "Django 配置文件", Severity.MEDIUM),
            ("/database.yml", "数据库配置文件", Severity.HIGH),
            ("/.htaccess", "Apache 配置文件", Severity.LOW),
            ("/web.config", "IIS 配置文件", Severity.MEDIUM),
            
            # 备份文件
            ("/backup.sql", "SQL 备份文件", Severity.HIGH),
            ("/backup.zip", "备份压缩包", Severity.HIGH),
            ("/db.sql", "数据库备份", Severity.HIGH),
            ("/dump.sql", "数据库备份", Severity.HIGH),
            ("/www.zip", "网站源码备份", Severity.HIGH),
            ("/web.zip", "网站源码备份", Severity.HIGH),
            ("/backup.tar.gz", "备份文件", Severity.HIGH),
            ("/1.zip", "常见备份文件", Severity.MEDIUM),
            ("/www.rar", "RAR 备份文件", Severity.HIGH),
            
            # 信息泄露
            ("/phpinfo.php", "PHP 信息泄露", Severity.MEDIUM),
            ("/info.php", "PHP 信息泄露", Severity.MEDIUM),
            ("/test.php", "测试文件", Severity.LOW),
            ("/robots.txt", "Robots 文件", Severity.INFO),
            ("/sitemap.xml", "站点地图", Severity.INFO),
            ("/README.md", "README 文件", Severity.LOW),
            ("/CHANGELOG.md", "更新日志", Severity.LOW),
            
            # 后台
            ("/admin", "管理后台", Severity.INFO),
            ("/admin/", "管理后台", Severity.INFO),
            ("/administrator/", "Joomla 后台", Severity.INFO),
            ("/wp-admin/", "WordPress 后台", Severity.INFO),
            ("/wp-login.php", "WordPress 登录", Severity.INFO),
            ("/manager/html", "Tomcat 管理后台", Severity.MEDIUM),
            ("/console/", "WebLogic 控制台", Severity.MEDIUM),
            
            # API
            ("/swagger-ui.html", "Swagger API 文档", Severity.MEDIUM),
            ("/swagger-ui/", "Swagger API 文档", Severity.MEDIUM),
            ("/api-docs", "API 文档", Severity.MEDIUM),
            ("/graphql", "GraphQL 端点", Severity.INFO),
            ("/graphiql", "GraphiQL 调试工具", Severity.MEDIUM),
            
            # 监控
            ("/actuator", "Spring Actuator", Severity.MEDIUM),
            ("/actuator/health", "健康检查端点", Severity.LOW),
            ("/actuator/env", "环境变量端点", Severity.HIGH),
            ("/druid/", "Druid 监控", Severity.MEDIUM),
            ("/solr/", "Solr 管理界面", Severity.MEDIUM),
            ("/jenkins/", "Jenkins 未授权", Severity.HIGH),
            
            # 其他
            ("/.DS_Store", "macOS 系统文件", Severity.LOW),
            ("/Thumbs.db", "Windows 缩略图", Severity.LOW),
            ("/crossdomain.xml", "Flash 跨域策略", Severity.LOW),
            ("/clientaccesspolicy.xml", "Silverlight 策略", Severity.LOW),
        ]
        
        async with AsyncHTTPClient() as client:
            semaphore = asyncio.Semaphore(self.threads)
            
            async def check(path, name, severity):
                async with semaphore:
                    resp = await self._check_path(client, path)
                    
                    # 判断是否存在
                    status = resp.get("status", 0)
                    body = resp.get("body", "")
                    
                    # 排除 404 和重定向
                    if status == 200:
                        # 进一步验证
                        if path == "/.git/config" and "[core]" in body:
                            return Vulnerability(
                                name=name,
                                url=resp["url"],
                                severity=severity,
                                description="Git 版本控制配置文件泄露，可能导致源码泄露",
                                evidence=body[:100]
                            )
                        elif path == "/.env" and ("=" in body or "DB_" in body):
                            return Vulnerability(
                                name=name,
                                url=resp["url"],
                                severity=severity,
                                description="环境变量文件泄露，可能包含数据库密码等敏感信息",
                                evidence=body[:100]
                            )
                        elif path == "/phpinfo.php" and "PHP Version" in body:
                            return Vulnerability(
                                name=name,
                                url=resp["url"],
                                severity=severity,
                                description="PHP 信息页面泄露，暴露服务器配置信息",
                                evidence="PHP Version found"
                            )
                        elif any(x in path for x in [".sql", ".zip", ".tar.gz", ".rar"]):
                            if resp.get("length", 0) > 100:
                                return Vulnerability(
                                    name=name,
                                    url=resp["url"],
                                    severity=severity,
                                    description="备份文件可能泄露，包含敏感数据",
                                    evidence=f"文件大小: {resp.get('length', 0)} bytes"
                                )
                        elif "actuator" in path:
                            return Vulnerability(
                                name=name,
                                url=resp["url"],
                                severity=severity,
                                description="Spring Boot Actuator 端点暴露",
                                evidence=body[:100]
                            )
                        elif "swagger" in path.lower() or "api-docs" in path:
                            return Vulnerability(
                                name=name,
                                url=resp["url"],
                                severity=severity,
                                description="API 文档泄露，暴露接口信息",
                                evidence=body[:100]
                            )
                        else:
                            # 通用检测
                            if resp.get("length", 0) > 0:
                                return Vulnerability(
                                    name=name,
                                    url=resp["url"],
                                    severity=severity,
                                    description=f"敏感路径可访问",
                                    evidence=f"状态码: {status}, 大小: {resp.get('length', 0)}"
                                )
                    return None
            
            tasks = [check(path, name, severity) for path, name, severity in sensitive_paths]
            done = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in done:
                if isinstance(result, Vulnerability):
                    self.vulnerabilities.append(result)
                    results.append(result)
        
        if results:
            print(f"[\u001b[31m!\u001b[0m] 发现 {len(results)} 个敏感文件问题")
        else:
            print(f"[\u001b[32m+\u001b[0m] 未发现敏感文件泄露")
        
        return results
    
    async def scan_directory_traversal(self) -> List[Vulnerability]:
        """目录遍历漏洞检测"""
        print("[\u001b[36m*\u001b[0m] 检测目录遍历漏洞...")
        
        results = []
        
        # 目录遍历 Payload
        payloads = [
            "/../../../etc/passwd",
            "/..%2f..%2f..%2fetc/passwd",
            "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
            "/....//....//....//etc/passwd",
            "/..\\..\\..\\windows\\win.ini",
            "/%2e%2e\\%2e%2e\\%2e%2e\\windows\\win.ini",
        ]
        
        async with AsyncHTTPClient() as client:
            for payload in payloads:
                try:
                    resp = await self._check_path(client, payload)
                    body = resp.get("body", "")
                    
                    # 检测是否包含敏感文件内容
                    if "root:" in body or "[extensions]" in body:
                        vuln = Vulnerability(
                            name="目录遍历漏洞",
                            url=resp["url"],
                            severity=Severity.HIGH,
                            description="存在目录遍历漏洞，可读取系统敏感文件",
                            evidence=body[:100]
                        )
                        self.vulnerabilities.append(vuln)
                        results.append(vuln)
                        break
                except:
                    pass
        
        if results:
            print(f"[\u001b[31m!\u001b[0m] 发现目录遍历漏洞!")
        else:
            print(f"[\u001b[32m+\u001b[0m] 未发现目录遍历漏洞")
        
        return results
    
    async def scan_sqli(self) -> List[Vulnerability]:
        """SQL 注入检测"""
        print("[\u001b[36m*\u001b[0m] 检测 SQL 注入...")
        
        results = []
        
        # 常见注入点
        test_urls = [
            f"/?id=1'",
            f"/?id=1\"",
            f"/?id=1 AND 1=1",
            f"/?id=1' AND '1'='1",
            f"/?search=test'",
            f"/?page=1'",
        ]
        
        # SQL 错误特征
        error_patterns = [
            r"SQL syntax.*MySQL",
            r"Warning.*mysql_",
            r"MySqlException",
            r"PostgreSQL.*ERROR",
            r"Warning.*pg_",
            r"ORA-\d{5}",
            r"Microsoft SQL Server",
            r"SQLite3::SQLException",
        ]
        
        async with AsyncHTTPClient() as client:
            for url_path in test_urls:
                try:
                    resp = await self._check_path(client, url_path)
                    body = resp.get("body", "")
                    
                    for pattern in error_patterns:
                        if re.search(pattern, body, re.IGNORECASE):
                            vuln = Vulnerability(
                                name="SQL 注入",
                                url=resp["url"],
                                severity=Severity.HIGH,
                                description="存在 SQL 注入漏洞，可能导致数据库被攻击",
                                evidence=f"匹配到错误信息: {pattern}"
                            )
                            self.vulnerabilities.append(vuln)
                            results.append(vuln)
                            break
                except:
                    pass
        
        if results:
            print(f"[\u001b[31m!\u001b[0m] 发现 {len(results)} 个 SQL 注入点")
        else:
            print(f"[\u001b[32m+\u001b[0m] 未发现 SQL 注入")
        
        return results
    
    async def scan_xss(self) -> List[Vulnerability]:
        """XSS 漏洞检测"""
        print("[\u001b[36m*\u001b[0m] 检测 XSS 漏洞...")
        
        results = []
        
        # XSS Payload
        payloads = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
        ]
        
        test_params = ["q", "search", "keyword", "name", "input"]
        
        async with AsyncHTTPClient() as client:
            for param in test_params:
                for payload in payloads:
                    try:
                        url_path = f"/?{param}={payload}"
                        resp = await self._check_path(client, url_path)
                        body = resp.get("body", "")
                        
                        # 检测 Payload 是否被反射
                        if payload in body and resp.get("status") == 200:
                            vuln = Vulnerability(
                                name="反射型 XSS",
                                url=resp["url"],
                                severity=Severity.MEDIUM,
                                description="存在反射型 XSS 漏洞，可能导致 Cookie 窃取等攻击",
                                evidence=f"参数 {param} 反射了 Payload"
                            )
                            self.vulnerabilities.append(vuln)
                            results.append(vuln)
                            break
                    except:
                        pass
        
        if results:
            print(f"[\u001b[31m!\u001b[0m] 发现 {len(results)} 个 XSS 漏洞")
        else:
            print(f"[\u001b[32m+\u001b[0m] 未发现 XSS 漏洞")
        
        return results
    
    async def scan_unauthorized_access(self) -> List[Vulnerability]:
        """未授权访问检测"""
        print("[\u001b[36m*\u001b[0m] 检测未授权访问...")
        
        results = []
        
        # 未授权访问路径
        auth_paths = [
            ("/actuator/env", "Spring Actuator 未授权", Severity.HIGH),
            ("/druid/index.html", "Druid 未授权访问", Severity.MEDIUM),
            ("/jenkins/script", "Jenkins 脚本执行", Severity.HIGH),
            ("/manager/html", "Tomcat 管理界面", Severity.MEDIUM),
            ("/solr/admin/", "Solr 未授权访问", Severity.MEDIUM),
            ("/redis-cli", "Redis 未授权", Severity.HIGH),
            ("/mongo/", "MongoDB 未授权", Severity.HIGH),
            ("/elasticsearch/", "Elasticsearch 未授权", Severity.MEDIUM),
            ("/kibana/", "Kibana 未授权", Severity.LOW),
            ("/grafana/", "Grafana 未授权", Severity.LOW),
            ("/zabbix/", "Zabbix 未授权", Severity.MEDIUM),
            ("/nacos/", "Nacos 未授权", Severity.HIGH),
            ("/sentinel/", "Sentinel 未授权", Severity.MEDIUM),
        ]
        
        async with AsyncHTTPClient() as client:
            semaphore = asyncio.Semaphore(self.threads)
            
            async def check(path, name, severity):
                async with semaphore:
                    resp = await self._check_path(client, path)
                    
                    if resp.get("status") == 200:
                        body = resp.get("body", "")
                        
                        # 验证是否有敏感内容
                        indicators = {
                            "/actuator/env": ["activeProfiles", "propertySources"],
                            "/druid/": ["druid", "stat"],
                            "/jenkins/": ["Jenkins", "script"],
                            "/manager/html": ["Tomcat", "Manager"],
                            "/solr/": ["Solr", "Admin"],
                            "/kibana/": ["kbn", "Kibana"],
                            "/grafana/": ["grafana", "Grafana"],
                            "/zabbix/": ["Zabbix", "Dashboard"],
                            "/nacos/": ["nacos", "Nacos"],
                        }
                        
                        for indicator_path, keywords in indicators.items():
                            if indicator_path in path:
                                if any(kw in body for kw in keywords):
                                    return Vulnerability(
                                        name=name,
                                        url=resp["url"],
                                        severity=severity,
                                        description=f"{name}，可能导致敏感信息泄露或系统被控制",
                                        evidence=body[:100]
                                    )
                        return None
                    return None
            
            tasks = [check(path, name, severity) for path, name, severity in auth_paths]
            done = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in done:
                if isinstance(result, Vulnerability):
                    self.vulnerabilities.append(result)
                    results.append(result)
        
        if results:
            print(f"[\u001b[31m!\u001b[0m] 发现 {len(results)} 个未授权访问问题")
        else:
            print(f"[\u001b[32m+\u001b[0m] 未发现未授权访问")
        
        return results
    
    async def run_all(self) -> List[Vulnerability]:
        """运行所有漏洞扫描"""
        print("\n" + "=" * 55)
        print("\u001b[36m漏洞扫描\u001b[0m")
        print("=" * 55 + "\n")
        
        await self.scan_sensitive_files()
        await self.scan_directory_traversal()
        await self.scan_sqli()
        await self.scan_xss()
        await self.scan_unauthorized_access()
        
        print(f"\n[\u001b[33m总结\u001b[0m] 发现 {len(self.vulnerabilities)} 个安全问题")
        
        return self.vulnerabilities
    
    def get_results(self) -> List[Dict]:
        """获取结果"""
        return [
            {
                "name": v.name,
                "url": v.url,
                "severity": v.severity.value,
                "description": v.description,
                "evidence": v.evidence
            }
            for v in self.vulnerabilities
        ]


# 测试
async def main(target: str):
    scanner = VulnerabilityScanner(target)
    results = await scanner.run_all()
    
    for v in results:
        print(f"[{v.severity.value.upper()}] {v.name}: {v.url}")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    asyncio.run(main(target))
