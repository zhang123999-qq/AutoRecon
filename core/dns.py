#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DNS解析模块
"""

import socket
from typing import List, Optional


class DNSResolver:
    """DNS解析工具类"""
    
    @staticmethod
    def resolve(hostname: str) -> Optional[str]:
        """解析域名为IP
        
        Args:
            hostname: 主机名
        
        Returns:
            IP地址或None
        """
        try:
            return socket.gethostbyname(hostname)
        except:
            return None
    
    @staticmethod
    def resolve_all(hostname: str) -> List[str]:
        """解析所有IP地址
        
        Args:
            hostname: 主机名
        
        Returns:
            IP地址列表
        """
        try:
            results = socket.getaddrinfo(hostname, None)
            ips = set()
            for r in results:
                ips.add(r[4][0])
            return list(ips)
        except:
            return []
    
    @staticmethod
    def reverse_resolve(ip: str) -> Optional[str]:
        """反向DNS解析
        
        Args:
            ip: IP地址
        
        Returns:
            主机名或None
        """
        try:
            result = socket.gethostbyaddr(ip)
            return result[0]
        except:
            return None
    
    @staticmethod
    def get_mx_records(domain: str) -> List[str]:
        """获取MX记录（简化实现）
        
        Args:
            domain: 域名
        
        Returns:
            MX记录列表
        """
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            return [str(r.exchange) for r in answers]
        except:
            return []
    
    @staticmethod
    def get_txt_records(domain: str) -> List[str]:
        """获取TXT记录（简化实现）
        
        Args:
            domain: 域名
        
        Returns:
            TXT记录列表
        """
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'TXT')
            return [str(r) for r in answers]
        except:
            return []
    
    @staticmethod
    def is_valid_domain(domain: str) -> bool:
        """验证域名格式
        
        Args:
            domain: 域名
        
        Returns:
            是否有效
        """
        import re
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """验证IP格式
        
        Args:
            ip: IP地址
        
        Returns:
            是否有效
        """
        try:
            socket.inet_aton(ip)
            return True
        except:
            return False
    
    @staticmethod
    def get_cname(domain: str) -> Optional[str]:
        """获取CNAME记录
        
        Args:
            domain: 域名
        
        Returns:
            CNAME目标或None
        """
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'CNAME')
            return str(answers[0].target)
        except:
            return None
