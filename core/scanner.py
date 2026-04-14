#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描工具模块 - 端口检测、CDN识别、敏感信息检测
"""

import re
import socket
import threading
from typing import List, Dict, Optional

from .dns import DNSResolver

# 导入 CDN 特征库
try:
    from .cdn_signatures import CDN_IP_RANGES, CDN_HEADERS
except ImportError:
    # 回退到内置特征
    CDN_IP_RANGES = {
        'CloudFlare': ['103.21.', '103.22.', '103.31.', '104.16.', '104.17.', '104.18.', '104.19.', '104.20.', '141.101.', '162.158.', '172.64.', '172.65.', '172.66.', '172.67.', '188.114.'],
        'Akamai': ['23.', '104.', '184.', '2.16.', '2.17.', '88.', '96.'],
        'Fastly': ['151.101.', '199.232.', '167.99.', '140.248.'],
        'CloudFront': ['13.', '52.', '54.', '99.', '143.204.'],
        '阿里云CDN': ['47.', '59.', '110.', '120.', '203.'],
        '腾讯云CDN': ['14.', '42.', '49.', '101.', '119.', '125.', '150.', '157.', '182.', '203.'],
        '百度云CDN': ['180.', '220.', '182.'],
        '华为云CDN': ['43.', '49.', '61.', '111.', '119.', '120.', '124.', '182.', '211.'],
        '网宿CDN': ['58.', '59.', '61.', '113.', '117.', '118.', '120.', '121.', '122.', '123.', '180.', '183.', '202.', '210.', '211.', '218.', '219.', '220.', '221.', '222.', '223.', '59.151.'],
    }
    CDN_HEADERS = {
        'CloudFlare': ['cf-ray', 'cloudflare', 'cf-cache-status'],
        'Akamai': ['akamai', 'x-akamai-transformed', 'x-akamai-staging'],
        'Fastly': ['x-served-by', 'x-cache', 'fastly', 'x-fastly-request-id'],
        'CloudFront': ['x-amz-cf', 'cloudfront', 'x-amz-cf-pop'],
        '阿里云CDN': ['ali-swift', 'x-swift', 'x-cache-ali'],
        '腾讯云CDN': ['x-cdn', 'x-daa-tunnel', 'x-tencent-cdn'],
        '华为云CDN': ['x-hw-cdn', 'hw-cdn'],
        '网宿CDN': ['ws-cdn', 'x-cache-ws'],
    }


class PortChecker:
    """端口检测工具类"""
    
    @staticmethod
    def is_open(host: str, port: int, timeout: float = 2.0) -> bool:
        """检测端口是否开放
        
        Args:
            host: 主机名或IP
            port: 端口号
            timeout: 超时时间
        
        Returns:
            端口是否开放
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    @staticmethod
    def get_banner(host: str, port: int, timeout: float = 5.0) -> Optional[str]:
        """获取服务Banner
        
        Args:
            host: 主机名或IP
            port: 端口号
            timeout: 超时时间
        
        Returns:
            Banner字符串或None
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.send(b'\r\n')
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            sock.close()
            return banner
        except:
            return None
    
    @staticmethod
    def scan_ports(host: str, ports: List[int], timeout: float = 2.0, threads: int = 10) -> Dict[int, dict]:
        """批量扫描端口
        
        Args:
            host: 主机名或IP
            ports: 端口列表
            timeout: 超时时间
            threads: 线程数
        
        Returns:
            开放端口信息字典
        """
        results = {}
        lock = threading.Lock()
        
        def scan_port(port):
            if PortChecker.is_open(host, port, timeout):
                banner = PortChecker.get_banner(host, port, timeout)
                with lock:
                    results[port] = {
                        'open': True,
                        'banner': banner
                    }
        
        # 多线程扫描
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=threads) as executor:
            executor.map(scan_port, ports)
        
        return results


class CDNDetector:
    """CDN检测器 - 支持40+主流CDN厂商"""
    
    # 使用从 cdn_signatures.py 导入的特征
    CDN_IP_RANGES = CDN_IP_RANGES
    CDN_HEADERS = CDN_HEADERS
    
    @classmethod
    def detect_from_ip(cls, ip: str) -> Optional[str]:
        """从IP地址检测CDN
        
        Args:
            ip: IP地址
        
        Returns:
            CDN名称或None
        """
        for cdn, ranges in cls.CDN_IP_RANGES.items():
            for r in ranges:
                if ip.startswith(r):
                    return cdn
        return None
    
    @classmethod
    def detect_from_headers(cls, headers: Dict[str, str]) -> Optional[str]:
        """从响应头检测CDN
        
        Args:
            headers: HTTP响应头字典
        
        Returns:
            CDN名称或None
        """
        headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
        
        for cdn, indicators in cls.CDN_HEADERS.items():
            for ind in indicators:
                for h, v in headers_lower.items():
                    if ind in h or ind in v:
                        return cdn
        return None
    
    @classmethod
    def detect_from_cname(cls, domain: str) -> Optional[str]:
        """从CNAME检测CDN
        
        Args:
            domain: 域名
        
        Returns:
            CDN名称或None
        """
        # CDN CNAME特征
        cdn_cnames = {
            'CloudFlare': ['.cdn.cloudflare.net', '.cloudflare.net'],
            'Akamai': ['.akamaized.net', '.akamai.net', '.edgekey.net'],
            'Fastly': ['.fastly.net', '.fastlycdn.com'],
            'CloudFront': ['.cloudfront.net'],
            '阿里云CDN': ['.kunlun', '.alikunlun.net', '.alicdn.com'],
            '腾讯云CDN': ['.cdn.dnsv1.com', '.cdn.dnsv2.com', '.cdn.dnsv3.com'],
            '百度云CDN': ['.bj.bcebos.com', '.bcebos.com'],
            '华为云CDN': ['.cdn.huaweicloud.com', '.huaweicloud.com'],
            '网宿CDN': ['.wscdns.com', '.ourwebpic.com', '.chinanetcenter.com'],
        }
        
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'CNAME')
            cname = str(answers[0].target).lower()
            
            for cdn, patterns in cdn_cnames.items():
                for pattern in patterns:
                    if pattern in cname:
                        return cdn
        except:
            pass
        
        return None
    
    @classmethod
    def detect(cls, domain: str, headers: Dict[str, str] = None) -> Dict:
        """综合检测CDN
        
        Args:
            domain: 域名
            headers: HTTP响应头（可选）
        
        Returns:
            检测结果字典
        """
        result = {
            'domain': domain,
            'cdn': None,
            'methods': []
        }
        
        # 从IP检测
        ips = DNSResolver.resolve_all(domain)
        for ip in ips:
            cdn = cls.detect_from_ip(ip)
            if cdn:
                result['cdn'] = cdn
                result['methods'].append({'method': 'ip', 'cdn': cdn, 'ip': ip})
                break
        
        # 从CNAME检测
        cdn_cname = cls.detect_from_cname(domain)
        if cdn_cname:
            if result['cdn'] and result['cdn'] != cdn_cname:
                result['cdn'] = f"{result['cdn']}/{cdn_cname}"
            else:
                result['cdn'] = cdn_cname
            result['methods'].append({'method': 'cname', 'cdn': cdn_cname})
        
        # 从响应头检测
        if headers:
            cdn_header = cls.detect_from_headers(headers)
            if cdn_header:
                if result['cdn'] and result['cdn'] != cdn_header:
                    result['cdn'] = f"{result['cdn']}/{cdn_header}"
                else:
                    result['cdn'] = cdn_header
                result['methods'].append({'method': 'header', 'cdn': cdn_header})
        
        result['ips'] = ips
        result['has_cdn'] = result['cdn'] is not None
        
        return result


class SensitiveDetector:
    """敏感信息检测器"""
    
    # 敏感信息正则模式
    PATTERNS = {
        'AWS Access Key': r'AKIA[0-9A-Z]{16}',
        'AWS Secret Key': r'aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{40}',
        'GitHub Token': r'ghp_[A-Za-z0-9]{36}',
        'GitHub OAuth': r'gho_[A-Za-z0-9]{36}',
        'Google API Key': r'AIza[0-9A-Za-z-_]{35}',
        'Slack Token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24}',
        'Stripe Key': r'sk_live_[0-9a-zA-Z]{24}',
        'Private Key': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
        'SSH Public Key': r'ssh-rsa\s+[A-Za-z0-9+/=]+',
        'Database URL': r'(mysql|postgres|postgresql|mongodb|redis|redis)://[^\s<"\']+',
        'API Key': r'[aA][pP][iI][_\-]?[kK][eE][yY]\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}["\']?',
        'Password': r'[pP][aA][sS][sS][wW][oO][rR][dD]\s*[=:]\s*["\']?[^\s<"\']{6,}["\']?',
        'Secret': r'[sS][eE][cC][rR][eE][tT]\s*[=:]\s*["\']?[A-Za-z0-9_\-]{8,}["\']?',
        'JWT Token': r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*',
        'IP Address': r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        'Email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'Phone (CN)': r'1[3-9]\d{9}',
        'ID Card (CN)': r'\d{17}[\dXx]',
        'Bank Card': r'[1-9]\d{15,18}',
    }
    
    # 编译后的正则
    _compiled_patterns = None
    
    @classmethod
    def _get_compiled_patterns(cls):
        """获取编译后的正则表达式"""
        if cls._compiled_patterns is None:
            cls._compiled_patterns = {
                name: re.compile(pattern) 
                for name, pattern in cls.PATTERNS.items()
            }
        return cls._compiled_patterns
    
    @classmethod
    def scan(cls, content: str) -> List[Dict]:
        """扫描内容中的敏感信息
        
        Args:
            content: 要扫描的内容
        
        Returns:
            发现的敏感信息列表
        """
        findings = []
        patterns = cls._get_compiled_patterns()
        
        for name, pattern in patterns.items():
            matches = pattern.findall(content)
            if matches:
                findings.append({
                    'type': name,
                    'count': len(matches),
                    'samples': matches[:3]  # 只显示前3个样本
                })
        
        return findings
    
    @classmethod
    def scan_url(cls, url: str, client=None) -> Dict:
        """扫描URL响应中的敏感信息
        
        Args:
            url: URL地址
            client: HTTPClient实例
        
        Returns:
            扫描结果字典
        """
        from .http import HTTPClient
        client = client or HTTPClient()
        
        result = {
            'url': url,
            'findings': [],
            'status': None
        }
        
        response = client.get(url)
        result['status'] = response.get('status', 0)
        
        if response.get('status') == 200:
            result['findings'] = cls.scan(response.get('body', ''))
        
        return result
    
    @classmethod
    def add_pattern(cls, name: str, pattern: str):
        """添加自定义检测模式
        
        Args:
            name: 模式名称
            pattern: 正则表达式
        """
        cls.PATTERNS[name] = pattern
        cls._compiled_patterns = None  # 清除缓存
