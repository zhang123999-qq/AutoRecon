#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSRF 防护测试
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.async_engine import is_ip_blocked, BLOCKED_IP_RANGES


class TestSSRFProtection:
    """SSRF 防护测试类"""
    
    def test_block_private_ip_class_a(self):
        """测试 A 类私有地址 (10.0.0.0/8)"""
        assert is_ip_blocked("10.0.0.1") == True
        assert is_ip_blocked("10.255.255.255") == True
        assert is_ip_blocked("10.123.45.67") == True
    
    def test_block_private_ip_class_b(self):
        """测试 B 类私有地址 (172.16.0.0/12)"""
        assert is_ip_blocked("172.16.0.1") == True
        assert is_ip_blocked("172.31.255.255") == True
        assert is_ip_blocked("172.20.100.50") == True
    
    def test_block_private_ip_class_c(self):
        """测试 C 类私有地址 (192.168.0.0/16)"""
        assert is_ip_blocked("192.168.0.1") == True
        assert is_ip_blocked("192.168.255.255") == True
        assert is_ip_blocked("192.168.100.50") == True
    
    def test_block_localhost(self):
        """测试本地回环地址 (127.0.0.0/8)"""
        assert is_ip_blocked("127.0.0.1") == True
        assert is_ip_blocked("127.255.255.255") == True
        assert is_ip_blocked("127.0.0.53") == True  # systemd-resolved
    
    def test_block_link_local(self):
        """测试链路本地地址 (169.254.0.0/16)"""
        assert is_ip_blocked("169.254.0.1") == True
        assert is_ip_blocked("169.254.169.254") == True  # AWS metadata
    
    def test_block_multicast(self):
        """测试多播地址 (224.0.0.0/4)"""
        assert is_ip_blocked("224.0.0.1") == True
        assert is_ip_blocked("239.255.255.255") == True
    
    def test_block_reserved(self):
        """测试保留地址 (240.0.0.0/4)"""
        assert is_ip_blocked("240.0.0.1") == True
        assert is_ip_blocked("255.255.255.255") == True
    
    def test_block_current_network(self):
        """测试当前网络地址 (0.0.0.0/8)"""
        assert is_ip_blocked("0.0.0.0") == True
        assert is_ip_blocked("0.0.0.1") == True
    
    def test_allow_public_ip(self):
        """测试公网 IP 应该被允许"""
        assert is_ip_blocked("8.8.8.8") == False  # Google DNS
        assert is_ip_blocked("1.1.1.1") == False  # Cloudflare DNS
        assert is_ip_blocked("208.67.222.222") == False  # OpenDNS
    
    def test_allow_public_ip_ranges(self):
        """测试更多公网 IP"""
        # 确保不在禁止范围内的 IP 通过
        test_ips = [
            "93.184.216.34",   # example.com
            "140.82.121.4",    # github.com
            "151.101.1.69",    # reddit.com
        ]
        for ip in test_ips:
            assert is_ip_blocked(ip) == False
    
    def test_invalid_ip(self):
        """测试无效 IP 应该被阻止"""
        assert is_ip_blocked("invalid") == True
        assert is_ip_blocked("256.256.256.256") == True
        assert is_ip_blocked("") == True
    
    def test_ipv6_localhost(self):
        """测试 IPv6 本地回环"""
        assert is_ip_blocked("::1") == True
        assert is_ip_blocked("0000:0000:0000:0000:0000:0000:0000:0001") == True
    
    def test_ipv6_ula(self):
        """测试 IPv6 唯一本地地址"""
        assert is_ip_blocked("fc00::1") == True
        assert is_ip_blocked("fd00::1") == True
    
    def test_ipv6_link_local(self):
        """测试 IPv6 链路本地地址"""
        assert is_ip_blocked("fe80::1") == True
    
    def test_ipv6_multicast(self):
        """测试 IPv6 多播地址"""
        assert is_ip_blocked("ff00::1") == True
    
    def test_ipv6_unspecified(self):
        """测试 IPv6 未指定地址"""
        assert is_ip_blocked("::") == True
    
    def test_ipv4_mapped_ipv6(self):
        """测试 IPv4 映射的 IPv6 地址"""
        # 127.0.0.1 映射到 IPv6
        assert is_ip_blocked("::ffff:127.0.0.1") == True
        # 10.0.0.1 映射到 IPv6
        assert is_ip_blocked("::ffff:10.0.0.1") == True
    
    def test_allow_public_ipv6(self):
        """测试公网 IPv6 应该被允许"""
        # Google DNS IPv6
        assert is_ip_blocked("2001:4860:4860::8888") == False
        # Cloudflare DNS IPv6
        assert is_ip_blocked("2606:4700:4700::1111") == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
