#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 信息收集自动化工具
全新异步架构，性能提升 10x+

作者: 小欣
架构: 模块化、异步、可扩展
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
from jinja2 import Environment, FileSystemLoader


class ReconToolV3:
    """信息收集主程序 v3.0"""
    
    VERSION = "3.0.0"
    
    # 可用模块
    AVAILABLE_MODULES = [
        'subdomain', 'port', 'dir', 'fingerprint', 
        'whois', 'cdn', 'sensitive', 'takeover', 'waf', 'vuln'
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
            except:
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
        
        # HTTP头检测
        if not results['cdn']:
            async with AsyncHTTPClient() as client:
                resp = await client.get(f"http://{self.target}")
                headers = {k.lower(): v.lower() for k, v in resp.get('headers', {}).items()}
                
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
  vuln        - 漏洞扫描 (新增)
'''
    )
    
    parser.add_argument('target', nargs='?', help='目标域名或IP')
    parser.add_argument('-m', '--modules', help='指定模块(逗号分隔)，all=全部')
    parser.add_argument('-t', '--threads', type=int, default=50, help='并发数(默认50)')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if not args.target:
        parser.print_help()
        print("\n\u001b[31m错误: 请指定目标域名或IP\u001b[0m")
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
