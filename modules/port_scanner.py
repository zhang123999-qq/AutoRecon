#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端口扫描模块 v2.1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import Logger, PortChecker, ProgressBar
from config import CONFIG, SERVICE_SIGNATURES


class PortScanner:
    """端口扫描器"""
    
    def __init__(self, target, ports=None, threads=None):
        self.target = target
        self.ports = ports or CONFIG.get('default_ports', [])
        self.threads = threads or CONFIG.get('port_threads', 50)
        self.open_ports = []
        self.services = {}
    
    def _scan_single_port(self, port):
        """扫描单个端口"""
        if PortChecker.is_open(self.target, port):
            return port
        return None
    
    def _identify_service(self, port):
        """识别端口服务"""
        # 先根据端口号识别
        service = SERVICE_SIGNATURES.get(port, 'unknown')
        
        # 尝试获取Banner
        banner = PortChecker.get_banner(self.target, port)
        
        result = {
            'port': port,
            'service': service,
            'banner': banner,
            'status': 'open'
        }
        
        # 根据Banner优化识别
        if banner:
            banner_lower = banner.lower()
            
            # FTP
            if 'ftp' in banner_lower or 'filezilla' in banner_lower:
                result['service'] = 'FTP'
            # SSH
            elif 'ssh' in banner_lower:
                result['service'] = 'SSH'
            # HTTP
            elif 'http' in banner_lower or 'apache' in banner_lower or 'nginx' in banner_lower:
                result['service'] = 'HTTP'
            # MySQL
            elif 'mysql' in banner_lower or 'mariadb' in banner_lower:
                result['service'] = 'MySQL'
            # Redis
            elif 'redis' in banner_lower:
                result['service'] = 'Redis'
            # MongoDB
            elif 'mongodb' in banner_lower:
                result['service'] = 'MongoDB'
        
        return result
    
    def scan(self, ports=None):
        """执行端口扫描"""
        ports = ports or self.ports
        Logger.info(f"正在扫描 {self.target} 的 {len(ports)} 个端口...")
        
        open_ports = []
        progress = ProgressBar(len(ports), "端口扫描")
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._scan_single_port, port): port for port in ports}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    open_ports.append(result)
                progress.update()
        
        progress.finish()
        
        self.open_ports = sorted(open_ports)
        Logger.success(f"发现 {len(self.open_ports)} 个开放端口: {self.open_ports}")
        
        return self.open_ports
    
    def identify_services(self):
        """识别开放端口的服务"""
        if not self.open_ports:
            return {}
        
        Logger.info(f"正在识别端口服务...")
        
        for port in self.open_ports:
            service_info = self._identify_service(port)
            self.services[port] = service_info
            
            banner_info = ""
            if service_info['banner']:
                banner_info = f" | Banner: {service_info['banner'][:50]}..."
            
            Logger.success(f"  {port}/{service_info['service']}{banner_info}")
        
        return self.services
    
    def run(self):
        """执行完整端口扫描和服务识别"""
        self.scan()
        self.identify_services()
        return {
            'open_ports': self.open_ports,
            'services': self.services
        }
    
    def get_http_ports(self):
        """获取HTTP相关端口"""
        return [p for p in self.open_ports if p in [80, 8080, 8000, 8888, 3000]]
    
    def get_https_ports(self):
        """获取HTTPS相关端口"""
        return [p for p in self.open_ports if p in [443, 8443]]


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = 'baidu.com'
    
    scanner = PortScanner(target)
    results = scanner.run()
    
    print(f"\n开放端口: {results['open_ports']}")
    print(f"\n服务信息:")
    for port, info in results['services'].items():
        print(f"  {port}: {info['service']}")
