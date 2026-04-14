#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输入验证测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入验证函数，如果 validators 模块不存在则跳过相关测试
try:
    from recon_v3 import validate_target, validate_url, validate_parameter
    HAS_VALIDATORS = True
except ImportError:
    HAS_VALIDATORS = False


@pytest.mark.skipif(not HAS_VALIDATORS, reason="validators module not installed")
class TestValidateTarget:
    """目标验证测试"""
    
    def test_valid_domain(self):
        """测试有效域名"""
        assert validate_target("example.com") == "example.com"
        assert validate_target("sub.example.com") == "sub.example.com"
        assert validate_target("test-site.org") == "test-site.org"
    
    def test_valid_ipv4(self):
        """测试有效 IPv4"""
        assert validate_target("8.8.8.8") == "8.8.8.8"
        assert validate_target("192.168.1.1") == "192.168.1.1"
    
    def test_valid_ipv6(self):
        """测试有效 IPv6"""
        assert validate_target("::1") == "::1"
        assert validate_target("2001:4860:4860::8888") == "2001:4860:4860::8888"
    
    def test_strip_protocol(self):
        """测试移除协议前缀"""
        assert validate_target("http://example.com") == "example.com"
        assert validate_target("https://example.com") == "example.com"
    
    def test_strip_path(self):
        """测试移除路径"""
        assert validate_target("example.com/path") == "example.com"
        assert validate_target("example.com:8080") == "example.com"
    
    def test_invalid_target(self):
        """测试无效目标"""
        with pytest.raises(ValueError):
            validate_target("")
        
        with pytest.raises(ValueError):
            validate_target("invalid domain with spaces")
    
    def test_empty_target(self):
        """测试空目标"""
        with pytest.raises(ValueError):
            validate_target(None)


@pytest.mark.skipif(not HAS_VALIDATORS, reason="validators module not installed")
class TestValidateUrl:
    """URL 验证测试"""
    
    def test_valid_http_url(self):
        """测试有效 HTTP URL"""
        assert validate_url("http://example.com") == "http://example.com"
        assert validate_url("http://example.com/path?query=1") == "http://example.com/path?query=1"
    
    def test_valid_https_url(self):
        """测试有效 HTTPS URL"""
        assert validate_url("https://example.com") == "https://example.com"
    
    def test_reject_ftp_protocol(self):
        """测试拒绝 FTP 协议"""
        with pytest.raises(ValueError):
            validate_url("ftp://example.com")
    
    def test_reject_file_protocol(self):
        """测试拒绝 file 协议"""
        with pytest.raises(ValueError):
            validate_url("file:///etc/passwd")
    
    def test_reject_command_injection_chars(self):
        """测试拒绝命令注入字符"""
        dangerous_urls = [
            "http://example.com;cat /etc/passwd",
            "http://example.com|whoami",
            "http://example.com&ls",
            "http://example.com$(whoami)",
            "http://example.com`id`",
        ]
        for url in dangerous_urls:
            with pytest.raises(ValueError):
                validate_url(url)
    
    def test_reject_newline_injection(self):
        """测试拒绝换行注入"""
        with pytest.raises(ValueError):
            validate_url("http://example.com\nHost: evil.com")
    
    def test_empty_url(self):
        """测试空 URL"""
        with pytest.raises(ValueError):
            validate_url("")
    
    def test_invalid_url_format(self):
        """测试无效 URL 格式"""
        with pytest.raises(ValueError):
            validate_url("not a valid url")


@pytest.mark.skipif(not HAS_VALIDATORS, reason="validators module not installed")
class TestValidateParameter:
    """参数名验证测试"""
    
    def test_valid_parameter(self):
        """测试有效参数名"""
        assert validate_parameter("id") == "id"
        assert validate_parameter("user_name") == "user_name"
        assert validate_parameter("user-id") == "user-id"
        assert validate_parameter("param123") == "param123"
    
    def test_reject_special_chars(self):
        """测试拒绝特殊字符"""
        with pytest.raises(ValueError):
            validate_parameter("id; DROP TABLE users")
        
        with pytest.raises(ValueError):
            validate_parameter("param|whoami")
    
    def test_reject_empty(self):
        """测试拒绝空参数"""
        with pytest.raises(ValueError):
            validate_parameter("")
        
        with pytest.raises(ValueError):
            validate_parameter(None)
    
    def test_reject_spaces(self):
        """测试拒绝空格"""
        with pytest.raises(ValueError):
            validate_parameter("param name")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
