#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DNS解析模块

⚠️ 已废弃警告 ⚠
--------------
此模块已废弃，建议使用异步版本：
    from core.async_engine import AsyncDNSResolver

原因：
    1. 使用同步 socket 调用，阻塞事件循环
    2. 异常处理过宽：`except: return None`
    3. 不符合项目异步架构

迁移示例：
    # 旧代码
    ip = DNSResolver.resolve(hostname)
    
    # 新代码
    resolver = AsyncDNSResolver()
    ip = await resolver.resolve(hostname)

废弃版本: v3.3.0
移除版本: v4.0.0
"""

import warnings

# 显示废弃警告
warnings.warn(
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️  DNSResolver 已废弃\n"
    "请使用: from core.async_engine import AsyncDNSResolver\n"
    "原因: 同步方式、异常处理过宽、阻塞事件循环\n"
    "废弃版本: v3.3.0 | 移除版本: v4.0.0\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    DeprecationWarning,
    stacklevel=2
)

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
        except (socket.gaierror, socket.herror, OSError) as e:
            logger.debug(f"DNS解析失败: {hostname} - {e}")
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
        except (socket.gaierror, socket.herror, OSError) as e:
            logger.debug(f"DNS解析失败: {hostname} - {e}")
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
        except (socket.gaierror, socket.herror, OSError) as e:
            logger.debug(f"反向DNS解析失败: {ip} - {e}")
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
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, ImportError) as e:
            logger.debug(f"获取MX记录失败: {domain} - {e}")
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
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, ImportError) as e:
            logger.debug(f"获取TXT记录失败: {domain} - {e}")
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
        except (OSError, socket.error):
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
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, ImportError) as e:
            logger.debug(f"获取CNAME记录失败: {domain} - {e}")
            return None
