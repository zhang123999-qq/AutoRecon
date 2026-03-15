#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信息收集自动化工具 v2.3
作者: 小欣
功能: 子域名收集、端口扫描、目录扫描、指纹识别、Whois/备案查询、CDN检测、敏感信息检测、子域名接管检测、WAF绕过、外部工具集成
架构: 模块化、面向对象、可扩展
"""

import sys
import os
import argparse
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入核心模块
from core import (
    Logger, get_logger, Timer, ProgressBar, 
    HTTPClient, RateLimiter, DNSResolver,
    PortChecker, CDNDetector, SensitiveDetector,
    ReportGenerator, BaseModule, CommandRunner
)
from config import CONFIG

# 导入扫描模块
from modules.subdomain import SubdomainCollector
from modules.port_scanner import PortScanner
from modules.dir_scanner import DirScanner
from modules.fingerprint import FingerprintScanner
from modules.whois_query import WhoisQuery, ICPQuery
from modules.cdn_detector import CDNScanner
from modules.sensitive import SensitiveScanner
from modules.takeover import SubdomainTakeoverScanner
from modules.waf_bypass import WAFBypassScanner
from modules.external_tools import ExternalToolManager, ExternalToolsScanner


class ReconTool:
    """信息收集主程序"""
    
    VERSION = "2.3"
    
    # 可用模块列表
    AVAILABLE_MODULES = [
        'subdomain', 'port', 'dir', 'fingerprint', 
        'whois', 'icp', 'cdn', 'sensitive', 'takeover', 'waf'
    ]
    
    def __init__(self, target, modules=None, output_dir=None, use_external=False, verbose=False):
        self.target = target
        self.modules = modules or ['subdomain', 'port', 'cdn', 'sensitive']
        self.output_dir = output_dir or CONFIG.get('output_dir', 'reports')
        self.use_external = use_external
        self.verbose = verbose
        self.results = {}
        self.timer = Timer()
        self.reporter = ReportGenerator(self.output_dir)
        self.external = ExternalToolsScanner() if use_external else None
    
    def run_subdomain(self):
        """执行子域名收集"""
        Logger.module_header("子域名收集", 1)
        
        collector = SubdomainCollector(self.target)
        results = collector.run()
        
        self.results['subdomain'] = {
            'count': len(results),
            'domains': results,
            'all_subdomains': collector.get_all_subdomains()
        }
        
        Logger.result(len(results), "子域名")
        return results
    
    def run_port_scan(self):
        """执行端口扫描"""
        Logger.module_header("端口扫描", 2)
        
        scanner = PortScanner(self.target)
        results = scanner.run()
        
        self.results['port'] = results
        Logger.info(f"开放端口: {results.get('open_ports', [])}")
        return results
    
    def run_dir_scan(self):
        """执行目录扫描"""
        Logger.module_header("目录扫描", 3)
        
        scanner = DirScanner(self.target)
        results = scanner.run()
        
        self.results['directory'] = results
        return results
    
    def run_fingerprint(self):
        """执行指纹识别"""
        Logger.module_header("指纹识别", 4)
        
        scanner = FingerprintScanner(self.target)
        results = scanner.run()
        
        self.results['fingerprint'] = results
        Logger.result(len(results.get('fingerprints', [])), "指纹")
        return results
    
    def run_whois(self):
        """执行Whois查询"""
        Logger.module_header("Whois查询", 5)
        
        query = WhoisQuery(self.target)
        results = query.run()
        
        self.results['whois'] = results
        return results
    
    def run_icp(self):
        """执行备案查询"""
        Logger.module_header("备案查询", 6)
        
        query = ICPQuery(self.target)
        results = query.run()
        
        self.results['icp'] = results
        return results
    
    def run_cdn(self):
        """执行CDN检测"""
        Logger.module_header("CDN检测", 7)
        
        scanner = CDNScanner(self.target)
        results = scanner.detect()
        
        self.results['cdn'] = results
        
        cdn = results.get('cdn')
        if cdn:
            Logger.info(f"检测到CDN: {cdn}")
        else:
            Logger.info("未检测到CDN")
        
        return results
    
    def run_sensitive(self):
        """执行敏感信息检测"""
        Logger.module_header("敏感信息检测", 8)
        
        scanner = SensitiveScanner(self.target)
        results = scanner.run()
        
        self.results['sensitive'] = results
        
        total = len(results.get('files', [])) + len(results.get('js_files', [])) + len(results.get('headers', []))
        if total > 0:
            Logger.warn(f"发现 {total} 处敏感信息泄露风险")
        else:
            Logger.success("未发现敏感信息泄露")
        
        return results
    
    def run_takeover(self):
        """执行子域名接管检测"""
        Logger.module_header("子域名接管检测", 9)
        
        # 先收集子域名
        subdomains = self.results.get('subdomain', {}).get('all_subdomains', [])
        
        if not subdomains:
            Logger.subtask("先收集子域名...")
            collector = SubdomainCollector(self.target)
            collector.run()
            subdomains = collector.get_all_subdomains()
        
        scanner = SubdomainTakeoverScanner(subdomains)
        results = scanner.run()
        
        self.results['takeover'] = {
            'vulnerable': results,
            'count': len(results)
        }
        
        if results:
            Logger.error(f"发现 {len(results)} 个存在接管风险的子域名!")
        else:
            Logger.success("未发现子域名接管风险")
        
        return results
    
    def run_waf(self):
        """执行WAF检测和绕过测试"""
        Logger.module_header("WAF检测与绕过", 10)
        
        scanner = WAFBypassScanner(self.target)
        results = scanner.run()
        
        self.results['waf'] = results
        
        waf = results.get('waf')
        if waf:
            Logger.info(f"检测到WAF: {waf}")
            bypass_count = len(results.get('bypass', []))
            if bypass_count > 0:
                Logger.warn(f"发现 {bypass_count} 种绕过方法")
        else:
            Logger.info("未检测到WAF")
        
        return results
    
    def run_external_tools(self):
        """运行外部工具扫描"""
        Logger.module_header("外部工具扫描", "扩展")
        
        if self.external:
            self.external.manager.print_status()
            results = self.external.run_full_scan(self.target)
            self.results['external'] = results
        else:
            Logger.info("未启用外部工具")
    
    def run(self):
        """执行所有模块"""
        Logger.banner()
        Logger.info(f"目标: {self.target}")
        Logger.info(f"启用模块: {', '.join(self.modules)}")
        if self.use_external:
            Logger.info("外部工具: 启用")
        print()
        
        self.timer.start()
        
        # 执行各模块
        module_map = {
            'subdomain': self.run_subdomain,
            'port': self.run_port_scan,
            'dir': self.run_dir_scan,
            'fingerprint': self.run_fingerprint,
            'whois': self.run_whois,
            'icp': self.run_icp,
            'cdn': self.run_cdn,
            'sensitive': self.run_sensitive,
            'takeover': self.run_takeover,
            'waf': self.run_waf,
        }
        
        for module in self.modules:
            if module in module_map:
                try:
                    module_map[module]()
                except Exception as e:
                    Logger.error(f"模块 {module} 执行失败: {e}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
        
        if self.use_external:
            self.run_external_tools()
        
        self.generate_report()
        return self.results
    
    def generate_report(self):
        """生成扫描报告"""
        print("\n" + "=" * 55)
        print(f"扫描完成! 耗时: {self.timer.elapsed_str()}")
        print("=" * 55 + "\n")
        
        # 保存JSON报告
        report_file = self.reporter.save_json(self.target, self.results)
        Logger.success(f"报告已保存: {report_file}")
        
        # 同时生成HTML报告
        html_file = self.reporter.save_html(self.target, self.results)
        Logger.success(f"HTML报告: {html_file}")
        
        self.print_summary()
    
    def print_summary(self):
        """打印扫描摘要"""
        print("\n" + "-" * 55)
        print("扫描摘要")
        print("-" * 55)
        
        if 'subdomain' in self.results:
            count = self.results['subdomain']['count']
            print(f"  子域名: {count} 个")
        
        if 'port' in self.results:
            ports = self.results['port'].get('open_ports', [])
            print(f"  开放端口: {ports}")
        
        if 'cdn' in self.results:
            cdn = self.results['cdn'].get('cdn')
            print(f"  CDN: {cdn or '未检测到'}")
        
        if 'waf' in self.results:
            waf = self.results['waf'].get('waf')
            print(f"  WAF: {waf or '未检测到'}")
        
        if 'takeover' in self.results:
            count = self.results['takeover']['count']
            if count > 0:
                print(f"  [!] 子域名接管风险: {count} 个")
        
        if 'sensitive' in self.results:
            files = self.results['sensitive'].get('files', [])
            js = self.results['sensitive'].get('js_files', [])
            total = len(files) + len(js)
            if total > 0:
                print(f"  [!] 敏感信息泄露: {total} 处")
        
        if 'fingerprint' in self.results:
            fingerprints = self.results['fingerprint'].get('fingerprints', [])
            print(f"  指纹: {len(fingerprints)} 个")
        
        print("-" * 55)


def main():
    parser = argparse.ArgumentParser(
        description=f'信息收集自动化工具 v{ReconTool.VERSION}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python recon.py example.com                        # 快速扫描
  python recon.py example.com -m all                 # 全模块扫描
  python recon.py example.com -m takeover,waf        # 指定模块
  python recon.py example.com --external             # 启用外部工具
  python recon.py example.com --html                 # 生成HTML报告

可用模块: ''' + ', '.join(ReconTool.AVAILABLE_MODULES)
    )
    
    parser.add_argument('target', nargs='?', help='目标域名或IP')
    parser.add_argument('-m', '--modules', help='指定模块(逗号分隔)，all=全部')
    parser.add_argument('-p', '--ports', help='指定端口(逗号分隔)')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-e', '--external', action='store_true', help='启用外部工具(subfinder/nmap/httpx)')
    parser.add_argument('--check-tools', action='store_true', help='检查外部工具状态')
    parser.add_argument('--html', action='store_true', help='生成HTML报告')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 检查工具状态
    if args.check_tools:
        manager = ExternalToolManager()
        manager.print_status()
        return
    
    # 检查目标参数
    if not args.target:
        parser.print_help()
        print("\n错误: 请指定目标域名或IP")
        sys.exit(1)
    
    # 解析模块
    modules = None
    if args.modules:
        if args.modules.lower() == 'all':
            modules = ReconTool.AVAILABLE_MODULES
        else:
            modules = [m.strip() for m in args.modules.split(',')]
    
    tool = ReconTool(
        args.target, 
        modules=modules, 
        output_dir=args.output, 
        use_external=args.external,
        verbose=args.verbose
    )
    
    if args.ports:
        CONFIG['default_ports'] = [int(p.strip()) for p in args.ports.split(',')]
    
    try:
        tool.run()
    except KeyboardInterrupt:
        print("\n\n扫描被用户中断")
        sys.exit(0)
    except Exception as e:
        Logger.error(f"扫描出错: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
