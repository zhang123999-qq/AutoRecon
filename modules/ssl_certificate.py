#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - SSL 证书分析模块
从证书透明度日志和历史证书中发现子域名
"""

import asyncio
import ssl
import socket
import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp


@dataclass
class CertificateInfo:
    """证书信息"""
    domain: str
    issuer: str
    subject: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    is_expired: bool = False
    is_self_signed: bool = False
    san_domains: List[str] = field(default_factory=list)
    fingerprint: str = ""


@dataclass
class SSLScanResult:
    """SSL 扫描结果"""
    target: str
    certificates: List[CertificateInfo] = field(default_factory=list)
    subdomains: Set[str] = field(default_factory=set)
    total_domains: int = 0
    errors: List[str] = field(default_factory=list)


class SSLCertificateScanner:
    """
    SSL 证书分析扫描器
    
    功能：
    - 获取服务器证书信息
    - 从 SAN (Subject Alternative Name) 提取域名
    - 查询证书透明度日志 (CT Log)
    - 检测证书安全问题
    """
    
    # CT Log 查询 API
    CT_LOG_APIS = [
        "https://crt.sh/?q={domain}&output=json",
        # 可以添加更多 CT Log API
    ]
    
    def __init__(self, target: str, timeout: int = 10):
        """
        初始化扫描器
        
        Args:
            target: 目标域名
            timeout: 超时时间（秒）
        """
        self.target = target
        self.timeout = timeout
        self.result = SSLScanResult(target=target)
    
    async def get_certificate(self, domain: str, port: int = 443) -> Optional[CertificateInfo]:
        """
        获取域名的 SSL 证书信息
        
        Args:
            domain: 域名
            port: 端口
            
        Returns:
            Optional[CertificateInfo]: 证书信息
        """
        try:
            # 创建 SSL context
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # 连接并获取证书
            loop = asyncio.get_event_loop()
            
            # 使用线程池执行阻塞的 SSL 操作
            cert_der = await loop.run_in_executor(
                None,
                self._get_cert_sync,
                domain,
                port,
                context
            )
            
            if not cert_der:
                return None
            
            # 解析证书
            cert_dict = ssl._ssl._test_decode_cert(cert_der)
            
            # 提取信息
            info = CertificateInfo(
                domain=domain,
                issuer=self._format_name(cert_dict.get('issuer', {})),
                subject=self._format_name(cert_dict.get('subject', {})),
                serial_number=cert_dict.get('serialNumber', ''),
                not_before=self._parse_time(cert_dict.get('notBefore')),
                not_after=self._parse_time(cert_dict.get('notAfter')),
                fingerprint=cert_dict.get('fingerprint', ''),
                san_domains=self._extract_san(cert_dict),
            )
            
            # 检查过期
            if info.not_after:
                info.is_expired = datetime.now() > info.not_after
            
            # 检查自签名
            info.is_self_signed = info.issuer == info.subject
            
            return info
            
        except Exception as e:
            self.result.errors.append(f"{domain}: {str(e)}")
            return None
    
    def _get_cert_sync(self, domain: str, port: int, context) -> Optional[bytes]:
        """同步获取证书（在线程池中运行）"""
        try:
            with socket.create_connection((domain, port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    return ssock.getpeercert(binary_form=True)
        except Exception:
            return None
    
    def _format_name(self, name_tuple: tuple) -> str:
        """格式化证书名称"""
        if not name_tuple:
            return ""
        
        parts = []
        for rdn in name_tuple:
            for key, value in rdn:
                parts.append(f"{key}={value}")
        
        return ", ".join(parts)
    
    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """解析证书时间"""
        if not time_str:
            return None
        
        try:
            # 格式: "Mar 24 10:00:00 2026 GMT"
            return datetime.strptime(time_str, "%b %d %H:%M:%S %Y %Z")
        except:
            return None
    
    def _extract_san(self, cert_dict: Dict) -> List[str]:
        """从证书中提取 SAN 域名"""
        san_domains = []
        
        extensions = cert_dict.get('extensions', [])
        for ext in extensions:
            if ext[0] == 'subjectAltName':
                for san in ext[1]:
                    if san[0] == 'DNS':
                        san_domains.append(san[1])
        
        return san_domains
    
    async def query_ct_log(self, domain: str) -> List[str]:
        """
        查询证书透明度日志
        
        Args:
            domain: 查询域名
            
        Returns:
            List[str]: 发现的域名列表
        """
        discovered = set()
        
        async with aiohttp.ClientSession() as session:
            for api_url in self.CT_LOG_APIS:
                url = api_url.format(domain=domain)
                
                try:
                    async with session.get(url, timeout=self.timeout) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            for entry in data:
                                name = entry.get('name_value', '')
                                if name:
                                    # 可能是多个域名（换行分隔）
                                    for d in name.split('\n'):
                                        d = d.strip().lower()
                                        if d and self._is_subdomain(d, domain):
                                            discovered.add(d)
                    
                    # 避免速率限制
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    self.result.errors.append(f"CT Log 查询失败: {e}")
        
        return list(discovered)
    
    def _is_subdomain(self, subdomain: str, parent: str) -> bool:
        """检查是否为子域名"""
        # 移除通配符
        if subdomain.startswith('*.'):
            subdomain = subdomain[2:]
        
        # 检查是否为子域名或主域名
        return subdomain.endswith(f'.{parent}') or subdomain == parent
    
    async def scan(self) -> SSLScanResult:
        """
        执行完整扫描
        
        Returns:
            SSLScanResult: 扫描结果
        """
        print(f"\n[*] SSL 证书分析: {self.target}")
        
        # 1. 获取目标证书
        print("[*] 获取服务器证书...")
        cert = await self.get_certificate(self.target)
        
        if cert:
            self.result.certificates.append(cert)
            print(f"[+] 证书颁发者: {cert.issuer}")
            print(f"[+] 有效期: {cert.not_before} - {cert.not_after}")
            
            if cert.is_expired:
                print("[!] 警告: 证书已过期")
            
            if cert.is_self_signed:
                print("[!] 警告: 自签名证书")
            
            # 从 SAN 提取域名
            if cert.san_domains:
                print(f"[+] SAN 域名: {len(cert.san_domains)} 个")
                self.result.subdomains.update(cert.san_domains)
        
        # 2. 查询 CT Log
        print("[*] 查询证书透明度日志...")
        ct_domains = await self.query_ct_log(self.target)
        
        if ct_domains:
            print(f"[+] CT Log 发现域名: {len(ct_domains)} 个")
            self.result.subdomains.update(ct_domains)
        
        # 3. 统计
        self.result.total_domains = len(self.result.subdomains)
        
        print(f"\n[+] 扫描完成:")
        print(f"    证书数: {len(self.result.certificates)}")
        print(f"    发现域名: {self.result.total_domains}")
        
        return self.result
    
    def print_results(self):
        """打印结果"""
        print("\n" + "=" * 60)
        print("SSL 证书分析报告")
        print("=" * 60)
        
        # 证书信息
        if self.result.certificates:
            print("\n[+] 证书信息:")
            for cert in self.result.certificates:
                print(f"  域名: {cert.domain}")
                print(f"  颁发者: {cert.issuer}")
                print(f"  有效期: {cert.not_before} - {cert.not_after}")
                print(f"  过期: {'是' if cert.is_expired else '否'}")
                print(f"  自签名: {'是' if cert.is_self_signed else '否'}")
                
                if cert.san_domains:
                    print(f"  SAN 域名: {len(cert.san_domains)} 个")
        
        # 发现的域名
        if self.result.subdomains:
            print(f"\n[+] 发现域名 ({len(self.result.subdomains)} 个):")
            for domain in sorted(self.result.subdomains)[:20]:  # 只显示前 20 个
                print(f"  - {domain}")
            
            if len(self.result.subdomains) > 20:
                print(f"  ... 还有 {len(self.result.subdomains) - 20} 个")
        
        # 错误
        if self.result.errors:
            print(f"\n[!] 错误 ({len(self.result.errors)} 个):")
            for error in self.result.errors[:5]:
                print(f"  - {error}")


# ============== 使用示例 ==============

async def main():
    """示例：SSL 证书分析"""
    
    scanner = SSLCertificateScanner("github.com")
    result = await scanner.scan()
    scanner.print_results()


if __name__ == "__main__":
    asyncio.run(main())
