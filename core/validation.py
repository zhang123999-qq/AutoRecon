#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 统一输入验证库
提供域名、IP、URL、参数等统一验证，防止注入攻击
"""

import re
import ipaddress
from urllib.parse import urlparse
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


class ValidationError(Exception):
    """验证异常"""
    def __init__(self, message: str, field: str = "", code: str = "VALIDATION_ERROR"):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


class ViolationType(Enum):
    """违规类型"""
    SHELL_INJECTION = "SHELL_INJECTION"
    SQL_INJECTION = "SQL_INJECTION"
    XSS = "XSS"
    SSRF = "SSRF"
    INVALID_FORMAT = "INVALID_FORMAT"
    RESERVED_DOMAIN = "RESERVED_DOMAIN"
    PRIVATE_IP = "PRIVATE_IP"


class InputValidator:
    """统一输入验证器"""
    
    # 预编译正则
    DOMAIN_PATTERN = re.compile(
        r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )
    
    # Shell 元字符
    SHELL_META_CHARS = re.compile(r'[;&|`$\\<>\(\)\{\}\[\]\n\r]')
    
    # SQL 注入特征
    SQL_META_CHARS = re.compile(
        r'\b(union|select|insert|update|delete|drop|alter|create|exec|execute)\b',
        re.IGNORECASE
    )
    
    # XSS 特征模式
    XSS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'expression\s*\(', re.IGNORECASE),
    ]
    
    # 保留域名后缀
    RESERVED_TLDS = {
        'localhost', 'local', 'test', 'example', 'invalid', 
        'internal', 'corp', 'home', 'lan', 'private'
    }
    
    # 危险协议
    DANGEROUS_SCHEMES = {'file', 'ftp', 'gopher', 'dict', 'ldap', 'tftp'}

    @classmethod
    def validate_domain(
        cls, 
        domain: str, 
        allow_wildcard: bool = False,
        allow_subdomain: bool = True
    ) -> str:
        """验证并规范化域名
        
        Args:
            domain: 域名字符串
            allow_wildcard: 是否允许通配符 (*.example.com)
            allow_subdomain: 是否允许子域名
            
        Returns:
            规范化后的域名
            
        Raises:
            ValidationError: 验证失败
        """
        if not domain or not isinstance(domain, str):
            raise ValidationError("域名不能为空", "domain")
        
        domain = domain.strip().lower().rstrip('.')
        
        # 移除协议前缀
        if domain.startswith(('http://', 'https://')):
            domain = domain.split('://', 1)[1]
        
        # 移除路径
        domain = domain.split('/')[0]
        
        # 处理端口
        if ':' in domain and not domain.startswith('['):
            domain = domain.rsplit(':', 1)[0]
        
        # 处理 IPv6 地址格式 [::1]:8080
        if domain.startswith('[') and ']' in domain:
            domain = domain.split(']')[0][1:]
        
        # 验证通配符
        if allow_wildcard and domain.startswith('*.'):
            domain = domain[2:]
        elif domain.startswith('*.'):
            raise ValidationError("不支持通配符域名", "domain", ViolationType.INVALID_FORMAT.value)
        
        # 验证格式
        if not cls.DOMAIN_PATTERN.match(domain):
            raise ValidationError(f"无效的域名格式: {domain}", "domain", ViolationType.INVALID_FORMAT.value)
        
        # 检查保留域名
        tld = domain.split('.')[-1]
        if tld in cls.RESERVED_TLDS:
            raise ValidationError(
                f"不允许扫描保留域名: {domain}", 
                "domain", 
                ViolationType.RESERVED_DOMAIN.value
            )
        
        # 检查是否为 IP 地址
        try:
            ipaddress.ip_address(domain)
            raise ValidationError(f"请使用 IP 验证函数: {domain}", "domain", ViolationType.INVALID_FORMAT.value)
        except ValueError:
            pass  # 不是 IP，继续
        
        return domain
    
    @classmethod
    def validate_ip(cls, ip: str, allow_private: bool = False, allow_loopback: bool = False) -> str:
        """验证IP地址
        
        Args:
            ip: IP地址字符串
            allow_private: 是否允许私有IP
            allow_loopback: 是否允许回环地址
            
        Returns:
            规范化后的IP地址
            
        Raises:
            ValidationError: 验证失败
        """
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            raise ValidationError(f"无效的IP地址: {ip}", "ip", ViolationType.INVALID_FORMAT.value)
        
        # 检查私有IP
        if ip_obj.is_private and not allow_private:
            raise ValidationError(
                f"不允许扫描私有IP: {ip} (需启用 ALLOW_PRIVATE_IPS)", 
                "ip", 
                ViolationType.PRIVATE_IP.value
            )
        
        # 检查回环地址
        if ip_obj.is_loopback and not allow_loopback:
            raise ValidationError(f"不允许扫描回环地址: {ip}", "ip", ViolationType.PRIVATE_IP.value)
        
        # 检查链路本地地址
        if ip_obj.is_link_local:
            raise ValidationError(f"不允许扫描链路本地地址: {ip}", "ip", ViolationType.PRIVATE_IP.value)
        
        # 检查多播地址
        if ip_obj.is_multicast:
            raise ValidationError(f"不允许扫描多播地址: {ip}", "ip", ViolationType.PRIVATE_IP.value)
        
        # 检查未指定地址
        if ip_obj.is_unspecified:
            raise ValidationError(f"无效的未指定地址: {ip}", "ip", ViolationType.INVALID_FORMAT.value)
        
        return str(ip_obj)
    
    @classmethod
    def validate_url(
        cls, 
        url: str, 
        allowed_schemes: Optional[List[str]] = None,
        allow_private_ips: bool = False
    ) -> str:
        """验证URL
        
        Args:
            url: URL字符串
            allowed_schemes: 允许的协议列表
            allow_private_ips: 是否允许私有IP
            
        Returns:
            验证后的URL
            
        Raises:
            ValidationError: 验证失败
        """
        allowed_schemes = allowed_schemes or ['http', 'https']
        
        if not url:
            raise ValidationError("URL不能为空", "url")
        
        # 检查 Shell 元字符
        if cls.SHELL_META_CHARS.search(url):
            raise ValidationError(
                "URL包含Shell元字符", 
                "url", 
                ViolationType.SHELL_INJECTION.value
            )
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"URL解析失败: {e}", "url", ViolationType.INVALID_FORMAT.value)
        
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(
                f"不支持的协议: {parsed.scheme}，仅允许: {allowed_schemes}", 
                "url", 
                ViolationType.INVALID_FORMAT.value
            )
        
        # 检查危险协议
        if parsed.scheme in cls.DANGEROUS_SCHEMES:
            raise ValidationError(
                f"危险协议被禁止: {parsed.scheme}", 
                "url", 
                ViolationType.SSRF.value
            )
        
        if not parsed.netloc:
            raise ValidationError("URL缺少主机名", "url", ViolationType.INVALID_FORMAT.value)
        
        # 验证主机部分
        host = parsed.hostname or ''
        port = parsed.port
        
        if host:
            try:
                cls.validate_domain(host)
            except ValidationError:
                try:
                    cls.validate_ip(host, allow_private=allow_private_ips)
                except ValidationError as e:
                    raise ValidationError(f"URL主机名无效: {e.message}", "url", e.code)
        
        # 检查端口
        if port is not None and (port < 1 or port > 65535):
            raise ValidationError(f"无效端口号: {port}", "url", ViolationType.INVALID_FORMAT.value)
        
        return url
    
    @classmethod
    def validate_parameter(cls, param: str, param_type: str = "generic") -> str:
        """验证参数名/值
        
        Args:
            param: 参数字符串
            param_type: 参数类型 (name, value, generic)
            
        Returns:
            验证后的参数
            
        Raises:
            ValidationError: 验证失败
        """
        if not param:
            raise ValidationError("参数不能为空", "parameter")
        
        if param_type == "name":
            # 参数名只允许字母数字下划线连字符
            if not re.match(r'^[a-zA-Z0-9_-]+$', param):
                raise ValidationError(
                    f"无效的参数名: {param}", 
                    "parameter", 
                    ViolationType.INVALID_FORMAT.value
                )
        elif param_type == "value":
            # 值检查 SQL 注入特征
            if cls.SQL_META_CHARS.search(param):
                raise ValidationError(
                    "参数值疑似SQL注入", 
                    "parameter", 
                    ViolationType.SQL_INJECTION.value
                )
            # 值检查 XSS 特征
            for pattern in cls.XSS_PATTERNS:
                if pattern.search(param):
                    raise ValidationError(
                        "参数值疑似XSS攻击", 
                        "parameter", 
                        ViolationType.XSS.value
                    )
            # 值检查 Shell 注入
            if cls.SHELL_META_CHARS.search(param):
                raise ValidationError(
                    "参数值包含Shell元字符", 
                    "parameter", 
                    ViolationType.SHELL_INJECTION.value
                )
        
        return param
    
    @classmethod
    def sanitize_for_log(cls, data: str, max_len: int = 100) -> str:
        """日志脱敏处理
        
        Args:
            data: 原始数据
            max_len: 最大长度
            
        Returns:
            脱敏后的字符串
        """
        if not data:
            return ""
        
        # 截断
        if len(data) > max_len:
            data = data[:max_len] + "..."
        
        # 脱敏模式
        patterns = [
            (re.compile(r'(password|passwd|pwd)\s*[=:]\s*\S+', re.IGNORECASE), r'\1=***'),
            (re.compile(r'(api[_-]?key|apikey)\s*[=:]\s*\S+', re.IGNORECASE), r'\1=***'),
            (re.compile(r'(token|secret|auth)\s*[=:]\s*\S+', re.IGNORECASE), r'\1=***'),
            (re.compile(r'AKIA[0-9A-Z]{16}'), 'AKIA***'),
            (re.compile(r'ghp_[A-Za-z0-9]{36}'), 'ghp_***' ),
            (re.compile(r'eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'), 'JWT_***' ),
            (re.compile(r'sk_live_[0-9a-zA-Z]{24}'), 'sk_live_***' ),
            (re.compile(r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24}'), 'SLACK_TOKEN_***' ),
        ]
        
        for pattern, repl in patterns:
            data = pattern.sub(repl, data)
        
        return data
    
    @classmethod
    def validate_scan_target(cls, target: str) -> str:
        """验证扫描目标（域名或IP）
        
        Args:
            target: 扫描目标
            
        Returns:
            验证后的目标
        """
        target = target.strip()
        
        # 尝试作为 IP 验证
        try:
            return cls.validate_ip(target)
        except ValidationError:
            pass
        
        # 尝试作为域名验证
        try:
            return cls.validate_domain(target)
        except ValidationError as e:
            raise ValidationError(f"无效的扫描目标: {target} - {e.message}", "target", e.code)


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    value: str = ""
    error: str = ""
    code: str = ""


def validate_and_sanitize(target: str) -> ValidationResult:
    """验证并清理目标，返回结构化结果"""
    try:
        value = InputValidator.validate_scan_target(target)
        return ValidationResult(valid=True, value=value)
    except ValidationError as e:
        return ValidationResult(valid=False, error=e.message, code=e.code)


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ("example.com", True),
        ("sub.example.com", True),
        ("*.example.com", False),  # 不允许通配符
        ("192.168.1.1", True),  # IP 验证
        ("10.0.0.1", False),  # 私有IP默认拒绝
        ("http://example.com", True),
        ("http://example.com; rm -rf /", False),  # Shell注入
        ("http://127.0.0.1", True),  # 回环地址
        ("javascript:alert(1)", False),  # 危险协议
        ("example.com' OR '1'='1", False),  # SQL注入
    ]
    
    print("验证测试:")
    for target, expected in test_cases:
        result = validate_and_sanitize(target)
        status = "✅" if result.valid == expected else "❌"
        print(f"  {status} {target}: valid={result.valid}, code={result.code}")