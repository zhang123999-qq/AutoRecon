#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 信息收集自动化工具
全新异步架构，性能提升 10x+

作者: 小欣
架构: 模块化、异步、可扩展

⚠️ 免责声明 / DISCLAIMER ⚠️

本工具仅供授权的安全测试使用。未经授权对第三方系统进行扫描属于违法行为。
使用者需确保：
1. 已获得目标系统所有者的书面授权
2. 遵守当地法律法规（《网络安全法》、《刑法》第285-287条等）
3. 扫描结果仅用于安全评估目的

作者不对任何滥用行为承担责任。使用者需自行承担法律责任。

This tool is for authorized security testing only. Unauthorized scanning
of third-party systems is illegal. Users must ensure they have proper
authorization before use. The author is not responsible for any misuse.
"""

import asyncio
import sys
import os
import argparse
import time
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.async_engine import (
    AsyncHTTPClient, AsyncDNSResolver, AsyncCache,
    AsyncRateLimiter, ResultStore, get_timestamp
)
from modules.async_subdomain import AsyncSubdomainCollector
from modules.vuln_scanner import VulnerabilityScanner
from modules.sqli_scanner import IntelligentSQLiScanner
from jinja2 import Environment, FileSystemLoader
import urllib.parse
import ipaddress
import re

# 尝试导入 validators，如果不存在则使用内置验证
try:
    import validators
    HAS_VALIDATORS = True
except ImportError:
    HAS_VALIDATORS = False
    validators = None


def _validate_domain_builtin(domain: str) -> bool:
    """内置域名验证（validators 不可用时使用）"""
    # 简单的域名正则验证
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(pattern, domain))


def _validate_ip_builtin(ip: str) -> bool:
    """内置 IP 验证"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def confirm_authorization() -> bool:
    """确认用户已获得授权"""
    print("""
\u001b[33m╔═══════════════════════════════════════════════════════════╗
║                    ⚠️  重要警告                            ║
╠═══════════════════════════════════════════════════════════╣
║  本工具仅供授权的安全测试使用                              ║
║  未经授权的扫描可能违反《网络安全法》等法律法规            ║
║  违者可能面临行政处罚或刑事责任                           ║
╚═══════════════════════════════════════════════════════════╝\u001b[0m

请确认：
  [1] 已获得目标系统所有者的书面授权
  [2] 扫描目的为安全评估或渗透测试
  [3] 了解并愿意承担法律责任
""")
    try:
        answer = input("确认已获得授权？[y/N]: ").strip().lower()
        return answer in ['y', 'yes']
    except EOFError:
        return False


def validate_target(target: str) -> str:
    """验证并清理目标域名或 IP"""
    if not target:
        raise ValueError("目标不能为空")
    
    # 去除协议前缀和路径
    target = target.replace('http://', '').replace('https://', '').strip('/')
    target = target.split('/')[0]
    
    # 处理端口号（注意 IPv6 地址包含冒号）
    # IPv6 地址格式：[::1] 或 2001:4860::8888
    if target.startswith('['):
        # IPv6 带端口号格式：[::1]:8080
        target = target.split(']')[0].strip('[]')
    elif ':' in target and not '::' in target:
        # 可能是 IPv4:端口 或 域名:端口
        # 检查是否是纯数字端口
        parts = target.rsplit(':', 1)
        if parts[-1].isdigit():
            target = parts[0]
    # 如果包含 :: 则是 IPv6 地址，不分割
    
    # 验证域名
    if HAS_VALIDATORS:
        try:
            if validators.domain(target):
                return target
        except (validators.ValidationError, TypeError) as e:
            logger.debug(f"域名验证失败: {target} - {e}")
    else:
        if _validate_domain_builtin(target):
            return target
    
    # 验证 IP
    if HAS_VALIDATORS:
        try:
            if validators.ip_address.ipv4(target) or validators.ip_address.ipv6(target):
                return target
        except (validators.ValidationError, TypeError) as e:
            logger.debug(f"IP验证失败: {target} - {e}")
    else:
        if _validate_ip_builtin(target):
            return target
    
    raise ValueError(f"无效的目标: {target}")


def validate_url(url: str) -> str:
    """验证并清理 URL，防止命令注入和 SSRF"""
    if not url:
        raise ValueError("URL 不能为空")
    
    # 验证 URL 格式
    if HAS_VALIDATORS:
        try:
            if not validators.url(url):
                raise ValueError(f"无效的 URL: {url}")
        except (validators.ValidationError, TypeError):
            raise ValueError(f"无效的 URL: {url}")
    else:
        # 内置 URL 验证
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"无效的 URL: {url}")
        except (ValueError, AttributeError) as e:
            raise ValueError(f"无效的 URL: {url} - {e}")
    
    # 只允许 http/https
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ['http', 'https']:
        raise ValueError(f"只允许 http/https 协议: {url}")
    
    # 防止命令注入字符
    dangerous_chars = [';', '|', '&', '$', '`', '\n', '\r', '{', '}', '<', '>']
    for char in dangerous_chars:
        if char in url:
            raise ValueError(f"URL 包含非法字符: {char}")
    
    return url


def validate_parameter(param: str) -> str:
    """验证参数名，防止命令注入"""
    if not param:
        raise ValueError("参数名不能为空")
    
    # 只允许字母、数字、下划线、连字符
    if not re.match(r'^[a-zA-Z0-9_-]+$', param):
        raise ValueError(f"无效的参数名: {param}")
    
    return param


class ReconToolV3:
    """信息收集主程序 v3.0"""
    
    VERSION = "3.0.0"
    
    # 可用模块
    AVAILABLE_MODULES = [
        'subdomain', 'port', 'dir', 'fingerprint', 
        'whois', 'cdn', 'sensitive', 'takeover', 'waf', 'vuln', 'sqli'
    ]
    
    def __init__(
        self, 
        target: str,
        modules: List[str] = None,
        output_dir: str = None,
        threads: int = 50,
        use_cache: bool = True,
        verbose: bool = False
    ):
        self.target = target
        self.modules = modules or ['subdomain', 'cdn', 'sensitive']
        self.output_dir = output_dir or "reports"
        self.threads = threads
        self.use_cache = use_cache
        self.verbose = verbose
        
        # 结果存储
        self.results = {}
        self.store = ResultStore(self.output_dir)
        
        # 缓存
        self.cache = AsyncCache() if use_cache else None
        
        # DNS
        self.dns = AsyncDNSResolver(cache=self.cache)
        
        # 统计
        self.start_time = None
        self.end_time = None
    
    def _banner(self):
        """显示Banner"""
        banner = f"""
\u001b[36m░████░█░░░░░█████░█░░░█░███░░████░░████░░▀█▀
█░░░░░█░░░░░█░░░█░█░█░█░█░░█░█░░░█░█░░░█░░█░
█░░░░░█░░░░░█████░█░█░█░█░░█░████░░█░░░█░░█░
█░░░░░█░░░░░█░░░█░█░█░█░█░░█░█░░█░░█░░░█░░█░
░████░█████░█░░░█░░█░█░░███░░████░░░███░░░█░\u001b[0m

\u001b[33m    AutoRecon v{self.VERSION} - 异步信息收集框架\u001b[0m
"""
        print(banner)
        print(f"目标: {self.target}")
        print(f"模块: {', '.join(self.modules)}")
        print(f"并发: {self.threads}")
        print(f"时间: {get_timestamp()}")
        print("=" * 55 + "\n")
    
    async def run_subdomain(self) -> Dict:
        """子域名收集"""
        print("\n" + "-" * 55)
        print("\u001b[36m[1] 子域名收集\u001b[0m")
        print("-" * 55)
        
        collector = AsyncSubdomainCollector(
            self.target,
            threads=self.threads,
            use_cache=self.use_cache
        )
        
        results = await collector.run_full()
        
        self.results['subdomain'] = {
            'count': len(results),
            'domains': [r.subdomain for r in results],
            'details': [
                {'subdomain': r.subdomain, 'ip': r.ip, 'source': r.source}
                for r in results
            ]
        }
        
        return self.results['subdomain']
    
    async def run_port_scan(self) -> Dict:
        """端口扫描"""
        print("\n" + "-" * 55)
        print("\u001b[36m[2] 端口扫描\u001b[0m")
        print("-" * 55)
        
        # 获取要扫描的主机
        hosts = [self.target]
        if 'subdomain' in self.results:
            ips = set()
            for detail in self.results['subdomain'].get('details', []):
                if detail.get('ip'):
                    ips.add(detail['ip'])
            hosts.extend(list(ips))
        
        # 常用端口
        common_ports = [
            21, 22, 23, 25, 53, 80, 81, 88, 110, 135, 139, 143,
            443, 445, 465, 587, 993, 995, 1433, 1521, 3306,
            3389, 5432, 5900, 6379, 7001, 8000, 8080, 8443,
            8888, 9000, 9090, 27017, 9200, 11211
        ]
        
        results = {'hosts': {}}
        
        async def scan_port(host: str, port: int) -> tuple:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=3
                )
                writer.close()
                await writer.wait_closed()
                return (port, True)
            except (asyncio.TimeoutError, ConnectionRefusedError, ConnectionResetError):
                return (port, False)
            except Exception as e:
                logger.debug(f"Port scan error for {host}:{port}: {e}")
                return (port, False)
        
        for host in hosts[:10]:  # 限制主机数
            print(f"[\u001b[36m*\u001b[0m] 扫描 {host}...")
            
            tasks = [scan_port(host, port) for port in common_ports]
            done = await asyncio.gather(*tasks)
            
            open_ports = [port for port, is_open in done if is_open]
            results['hosts'][host] = {'open_ports': open_ports}
            
            if open_ports:
                print(f"[\u001b[32m+\u001b[0m] {host}: {open_ports}")
        
        self.results['port'] = results
        return results
    
    async def run_cdn_detect(self) -> Dict:
        """CDN检测"""
        print("\n" + "-" * 55)
        print("\u001b[36m[3] CDN检测\u001b[0m")
        print("-" * 55)
        
        results = {'domain': self.target, 'cdn': None, 'ips': []}
        
        # 解析IP
        ips = await self.dns.resolve_all(self.target)
        results['ips'] = ips
        
        # CDN IP特征检测
        cdn_ranges = {
            'CloudFlare': ['103.21.', '103.22.', '104.16.', '172.64.', '188.114.'],
            'Akamai': ['23.', '104.', '184.', '2.16.', '88.'],
            '阿里云CDN': ['47.', '59.', '110.', '120.'],
            '腾讯云CDN': ['14.', '42.', '49.', '101.', '119.'],
        }
        
        for ip in ips:
            for cdn, ranges in cdn_ranges.items():
                for r in ranges:
                    if ip.startswith(r):
                        results['cdn'] = cdn
                        break
        
        # HTTP头检测 - 尝试 HTTPS 和 HTTP
        if not results['cdn']:
            async with AsyncHTTPClient() as client:
                # 先尝试 HTTPS
                try:
                    resp = await client.get(f"https://{self.target}")
                    headers = {k.lower(): v.lower() for k, v in resp.get('headers', {}).items()}
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.debug(f"HTTPS请求失败: {e}")
                    # HTTPS 失败，尝试 HTTP
                    try:
                        resp = await client.get(f"http://{self.target}")
                        headers = {k.lower(): v.lower() for k, v in resp.get('headers', {}).items()}
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.debug(f"HTTP请求也失败: {e}")
                        headers = {}
                
                cdn_headers = {
                    'CloudFlare': ['cf-ray', 'cloudflare'],
                    'Akamai': ['akamai'],
                    '阿里云CDN': ['ali-swift'],
                    '腾讯云CDN': ['x-cdn'],
                }
                
                for cdn, indicators in cdn_headers.items():
                    for ind in indicators:
                        for h, v in headers.items():
                            if ind in h or ind in v:
                                results['cdn'] = cdn
                                break
        
        if results['cdn']:
            print(f"[\u001b[32m+\u001b[0m] 检测到CDN: {results['cdn']}")
        else:
            print(f"[\u001b[33m-\u001b[0m] 未检测到CDN")
        
        self.results['cdn'] = results
        return results
    
    async def run_sensitive(self) -> Dict:
        """敏感信息检测"""
        print("\n" + "-" * 55)
        print("\u001b[36m[4] 敏感信息检测\u001b[0m")
        print("-" * 55)
        
        import re
        
        patterns = {
            'AWS Key': r'AKIA[0-9A-Z]{16}',
            'GitHub Token': r'ghp_[A-Za-z0-9]{36}',
            'Private Key': r'-----BEGIN.*PRIVATE KEY-----',
            'API Key': r'[aA][pP][iI][_\-]?[kK][eE][yY].{16,}',
            'Password': r'[pP][aA][sS][sS][wW][oO][rR][dD].{6,}',
            'JWT': r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*',
        }
        
        results = {'url': f"http://{self.target}", 'findings': []}
        
        async with AsyncHTTPClient() as client:
            resp = await client.get(f"http://{self.target}")
            body = resp.get('body', '')
            
            for name, pattern in patterns.items():
                matches = re.findall(pattern, body)
                if matches:
                    results['findings'].append({
                        'type': name,
                        'count': len(matches),
                        'sample': matches[0][:50] if matches else None
                    })
        
        if results['findings']:
            print(f"[\u001b[31m!\u001b[0m] 发现 {len(results['findings'])} 类敏感信息")
            for f in results['findings']:
                print(f"    - {f['type']}: {f['count']} 处")
        else:
            print(f"[\u001b[32m+\u001b[0m] 未发现敏感信息")
        
        self.results['sensitive'] = results
        return results
    
    async def run_fingerprint(self) -> Dict:
        """指纹识别"""
        print("\n" + "-" * 55)
        print("\u001b[36m[5] 指纹识别\u001b[0m")
        print("-" * 55)
        
        from data.fingerprints import ALL_FINGERPRINTS
        
        results = {'fingerprints': []}
        
        async with AsyncHTTPClient() as client:
            resp = await client.get(f"http://{self.target}")
            body = resp.get('body', '')
            headers = resp.get('headers', {})
            
            for name, fingerprints in ALL_FINGERPRINTS.items():
                matched = False
                
                # HTML特征
                for pattern in fingerprints.get('html', []):
                    if pattern.lower() in body.lower():
                        matched = True
                        break
                
                # Header特征
                if not matched:
                    for pattern in fingerprints.get('headers', []):
                        for h, v in headers.items():
                            if pattern.lower() in f"{h}: {v}".lower():
                                matched = True
                                break
                
                if matched:
                    results['fingerprints'].append(name)
        
        if results['fingerprints']:
            print(f"[\u001b[32m+\u001b[0m] 识别到: {', '.join(results['fingerprints'][:10])}")
        else:
            print(f"[\u001b[33m-\u001b[0m] 未识别到指纹")
        
        self.results['fingerprint'] = results
        return results
    
    async def run_vuln(self) -> Dict:
        """漏洞扫描"""
        print("\n" + "-" * 55)
        print("\u001b[36m[6] 漏洞扫描\u001b[0m")
        print("-" * 55)
        
        scanner = VulnerabilityScanner(self.target, threads=self.threads)
        results = await scanner.run_all()
        
        self.results['vulnerabilities'] = scanner.get_results()
        return self.results['vulnerabilities']
    
    async def run_sqli(self) -> Dict:
        """SQL注入扫描 (智能化)"""
        print("\n" + "-" * 55)
        print("\u001b[36m[7] 智能 SQL 注入扫描\u001b[0m")
        print("-" * 55)
        
        scanner = IntelligentSQLiScanner(self.target, threads=self.threads)
        results = await scanner.run_full_scan()
        
        self.results['sqli'] = scanner.get_results()
        return self.results['sqli']
    
    async def run_all(self) -> Dict:
        """执行所有模块"""
        self._banner()
        self.start_time = time.time()
        
        # 模块映射
        module_map = {
            'subdomain': self.run_subdomain,
            'port': self.run_port_scan,
            'cdn': self.run_cdn_detect,
            'sensitive': self.run_sensitive,
            'fingerprint': self.run_fingerprint,
            'vuln': self.run_vuln,
            'sqli': self.run_sqli,
        }
        
        for module in self.modules:
            if module in module_map:
                try:
                    await module_map[module]()
                except Exception as e:
                    print(f"[\u001b[31m!\u001b[0m] 模块 {module} 执行失败: {e}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
        
        self.end_time = time.time()
        await self.generate_report()
        
        return self.results
    
    async def generate_report(self):
        """生成报告"""
        elapsed = self.end_time - self.start_time
        
        print("\n" + "=" * 55)
        print(f"\u001b[32m扫描完成! 耗时: {elapsed:.2f}s\u001b[0m")
        print("=" * 55 + "\n")
        
        # 保存JSON报告
        report_file = self.store.save_json(self.target, self.results)
        print(f"[\u001b[32m+\u001b[0m] JSON报告: {report_file}")
        
        # 生成HTML报告
        html_file = await self._generate_html_report(elapsed)
        if html_file:
            print(f"[\u001b[32m+\u001b[0m] HTML报告: {html_file}")
        
        # 打印摘要
        self._print_summary()
    
    async def _generate_html_report(self, elapsed: float) -> Optional[str]:
        """生成HTML报告"""
        try:
            template_dir = os.path.join(os.path.dirname(__file__), 'templates')
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template('report.html')
            
            # 统计数据
            stats = {
                'subdomains': self.results.get('subdomain', {}).get('count', 0),
                'ports': sum(
                    len(h.get('open_ports', []))
                    for h in self.results.get('port', {}).get('hosts', {}).values()
                ),
                'fingerprints': len(self.results.get('fingerprint', {}).get('fingerprints', [])),
                'vulnerabilities': len(self.results.get('vulnerabilities', [])),
                'sensitive': len(self.results.get('sensitive', {}).get('findings', [])),
                'sqli': len(self.results.get('sqli', [])),
            }
            
            html_content = template.render(
                target=self.target,
                scan_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                elapsed=f"{elapsed:.2f}",
                stats=stats,
                subdomains=self.results.get('subdomain'),
                ports=self.results.get('port'),
                cdn=self.results.get('cdn'),
                fingerprints=self.results.get('fingerprint'),
                vulnerabilities=self.results.get('vulnerabilities'),
                sensitive=self.results.get('sensitive'),
                sqli=self.results.get('sqli'),
            )
            
            html_file = os.path.join(self.output_dir, f"{self.target}_report.html")
            os.makedirs(self.output_dir, exist_ok=True)
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return html_file
        except Exception as e:
            if self.verbose:
                print(f"[\u001b[33m!\u001b[0m] HTML报告生成失败: {e}")
            return None
    
    def _print_summary(self):
        """打印摘要"""
        print("\n" + "-" * 55)
        print("扫描摘要")
        print("-" * 55)
        
        if 'subdomain' in self.results:
            print(f"  子域名: {self.results['subdomain']['count']} 个")
        
        if 'port' in self.results:
            total_open = sum(
                len(h.get('open_ports', [])) 
                for h in self.results['port'].get('hosts', {}).values()
            )
            print(f"  开放端口: {total_open} 个")
        
        if 'cdn' in self.results:
            print(f"  CDN: {self.results['cdn'].get('cdn') or '未检测到'}")
        
        if 'sensitive' in self.results:
            count = len(self.results['sensitive'].get('findings', []))
            if count > 0:
                print(f"  \u001b[31m[!] 敏感信息: {count} 类\u001b[0m")
        
        if 'fingerprint' in self.results:
            fps = self.results['fingerprint'].get('fingerprints', [])
            print(f"  指纹: {len(fps)} 个")
        
        if 'vulnerabilities' in self.results:
            count = len(self.results['vulnerabilities'])
            if count > 0:
                high = sum(1 for v in self.results['vulnerabilities'] if v.get('severity') == 'high')
                print(f"  \u001b[31m[!] 安全问题: {count} 个 (高危: {high})\u001b[0m")
        
        if 'sqli' in self.results:
            count = len(self.results['sqli'])
            if count > 0:
                print(f"  \u001b[31m[!] SQL注入: {count} 个\u001b[0m")
        
        print("-" * 55)


async def main():
    parser = argparse.ArgumentParser(
        description=f'AutoRecon v{ReconToolV3.VERSION} - 异步信息收集框架',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python recon_v3.py example.com                    # 快速扫描
  python recon_v3.py example.com -m all             # 全模块扫描
  python recon_v3.py example.com -m subdomain,port  # 指定模块
  python recon_v3.py example.com -m vuln            # 漏洞扫描
  python recon_v3.py example.com -t 100             # 100并发

可用模块:
  subdomain   - 子域名收集
  port        - 端口扫描
  cdn         - CDN检测
  fingerprint - 指纹识别
  sensitive   - 敏感信息检测
  vuln        - 漏洞扫描
  sqli        - 智能 SQL 注入扫描 (新增)
'''
    )
    
    parser.add_argument('target', nargs='?', help='目标域名或IP')
    parser.add_argument('-m', '--modules', help='指定模块(逗号分隔)，all=全部')
    parser.add_argument('-t', '--threads', type=int, default=50, 
                        help='并发数(默认50，范围1-200)')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('-y', '--yes', action='store_true', help='跳过授权确认(已获授权时使用)')
    
    args = parser.parse_args()
    
    # 限制并发数在安全范围内
    if args.threads:
        args.threads = max(1, min(args.threads, 200))  # 限制 1-200
    
    if not args.target:
        parser.print_help()
        print("\n\u001b[31m错误: 请指定目标域名或IP\u001b[0m")
        sys.exit(1)
    
    # 授权确认（安全警告）
    # 使用 --yes 或 -y 参数跳过确认（自动化脚本场景）
    if not args.yes and not confirm_authorization():
        print("\n\u001b[33m未确认授权，扫描已取消。\u001b[0m")
        print("提示: 如需跳过确认，可使用 --yes 或 -y 参数\n")
        sys.exit(0)
    
    # 验证目标
    try:
        args.target = validate_target(args.target)
    except ValueError as e:
        print(f"\n\u001b[31m错误: {e}\u001b[0m")
        sys.exit(1)
    
    # 解析模块
    modules = None
    if args.modules:
        if args.modules.lower() == 'all':
            modules = ReconToolV3.AVAILABLE_MODULES
        else:
            modules = [m.strip() for m in args.modules.split(',')]
    
    tool = ReconToolV3(
        args.target,
        modules=modules,
        output_dir=args.output,
        threads=args.threads,
        verbose=args.verbose
    )
    
    try:
        await tool.run_all()
    except KeyboardInterrupt:
        print("\n\n\u001b[33m扫描被用户中断\u001b[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\n\u001b[31m扫描出错: {e}\u001b[0m")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
