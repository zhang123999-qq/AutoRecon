#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 统一异常体系
定义项目标准异常类，提供结构化错误信息
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class ErrorCode(Enum):
    """标准错误码"""
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    
    # 验证错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    INVALID_IP = "INVALID_IP"
    INVALID_URL = "INVALID_URL"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    
    # 安全错误
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    SHELL_INJECTION_BLOCKED = "SHELL_INJECTION_BLOCKED"
    SQL_INJECTION_BLOCKED = "SQL_INJECTION_BLOCKED"
    XSS_BLOCKED = "XSS_BLOCKED"
    PRIVATE_IP_BLOCKED = "PRIVATE_IP_BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    
    # 网络错误
    NETWORK_ERROR = "NETWORK_ERROR"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    DNS_RESOLUTION_FAILED = "DNS_RESOLUTION_FAILED"
    SSL_ERROR = "SSL_ERROR"
    PROXY_ERROR = "PROXY_ERROR"
    
    # 扫描器错误
    SCANNER_ERROR = "SCANNER_ERROR"
    SCANNER_TIMEOUT = "SCANNER_TIMEOUT"
    SCANNER_CANCELLED = "SCANNER_CANCELLED"
    MODULE_NOT_FOUND = "MODULE_NOT_FOUND"
    
    # 外部工具错误
    EXTERNAL_TOOL_ERROR = "EXTERNAL_TOOL_ERROR"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    
    # 存储错误
    STORAGE_ERROR = "STORAGE_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    DISK_FULL = "DISK_FULL"
    
    # 认证授权错误
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    INVALID_API_KEY = "INVALID_API_KEY"
    API_KEY_MISSING = "API_KEY_MISSING"


class AutoReconError(Exception):
    """AutoRecon 基础异常类
    
    所有项目异常都应继承此类，提供统一的错误处理接口。
    
    Attributes:
        message: 用户友好的错误消息
        code: 标准错误码
        details: 结构化错误详情
        cause: 原始异常（用于异常链）
    """
    
    def __init__(
        self, 
        message: str, 
        code: str = ErrorCode.UNKNOWN_ERROR.value,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于API响应）"""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None
        }
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(AutoReconError):
    """输入验证错误"""
    
    def __init__(
        self, 
        message: str, 
        field: str = "", 
        violation_type: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        all_details = details or {}
        if field:
            all_details["field"] = field
        if violation_type:
            all_details["violation_type"] = violation_type
        super().__init__(
            message, 
            code=ErrorCode.VALIDATION_ERROR.value,
            details=all_details
        )


class SecurityError(AutoReconError):
    """安全违规错误"""
    
    def __init__(
        self, 
        message: str, 
        violation_type: str,
        blocked_value: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        all_details = details or {}
        all_details["violation_type"] = violation_type
        if blocked_value:
            # 脱敏显示
            all_details["blocked_value"] = blocked_value[:50] + "..." if len(blocked_value) > 50 else blocked_value
        super().__init__(
            message,
            code=ErrorCode.SECURITY_VIOLATION.value,
            details=all_details
        )


class SSRFError(SecurityError):
    """SSRF 防护拦截错误"""
    
    def __init__(self, message: str, blocked_ip: str = "", blocked_url: str = ""):
        details = {}
        if blocked_ip:
            details["blocked_ip"] = blocked_ip
        if blocked_url:
            details["blocked_url"] = blocked_url
        super().__init__(
            message,
            violation_type="SSRF_BLOCKED",
            details=details
        )
        self.code = ErrorCode.SSRF_BLOCKED.value


class ShellInjectionError(SecurityError):
    """Shell 注入拦截错误"""
    
    def __init__(self, message: str, blocked_command: str = ""):
        super().__init__(
            message,
            violation_type="SHELL_INJECTION",
            blocked_value=blocked_command
        )
        self.code = ErrorCode.SHELL_INJECTION_BLOCKED.value


class RateLimitError(AutoReconError):
    """速率限制错误"""
    
    def __init__(self, message: str, retry_after: float = 0, limit: int = 0, current: int = 0):
        super().__init__(
            message,
            code=ErrorCode.RATE_LIMITED.value,
            details={
                "retry_after": retry_after,
                "limit": limit,
                "current": current
            }
        )


class ScannerError(AutoReconError):
    """扫描器错误"""
    
    def __init__(
        self, 
        message: str, 
        scanner_name: str = "",
        module: str = "",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        all_details = details or {}
        if scanner_name:
            all_details["scanner"] = scanner_name
        if module:
            all_details["module"] = module
        super().__init__(
            message,
            code=ErrorCode.SCANNER_ERROR.value,
            details=all_details,
            cause=cause
        )


class ExternalToolError(AutoReconError):
    """外部工具执行错误"""
    
    def __init__(
        self,
        message: str,
        tool: str,
        exit_code: int = -1,
        stderr: str = "",
        stdout: str = "",
        command: str = ""
    ):
        super().__init__(
            message,
            code=ErrorCode.EXTERNAL_TOOL_ERROR.value,
            details={
                "tool": tool,
                "exit_code": exit_code,
                "stderr": stderr[-500:] if stderr else "",  # 限制长度
                "stdout": stdout[-500:] if stdout else "",
                "command": command
            }
        )


class ConfigurationError(AutoReconError):
    """配置错误"""
    
    def __init__(self, message: str, config_key: str = "", config_file: str = ""):
        super().__init__(
            message,
            code=ErrorCode.CONFIGURATION_ERROR.value,
            details={
                "config_key": config_key,
                "config_file": config_file
            }
        )


class AuthenticationError(AutoReconError):
    """认证错误"""
    
    def __init__(self, message: str, auth_type: str = "", details: Optional[Dict] = None):
        super().__init__(
            message,
            code=ErrorCode.AUTHENTICATION_FAILED.value,
            details={"auth_type": auth_type, **(details or {})}
        )


class AuthorizationError(AutoReconError):
    """授权错误"""
    
    def __init__(self, message: str, required_permission: str = "", details: Optional[Dict] = None):
        super().__init__(
            message,
            code=ErrorCode.AUTHORIZATION_FAILED.value,
            details={"required_permission": required_permission, **(details or {})}
        )


# 便捷函数
def wrap_exception(
    e: Exception, 
    default_message: str = "操作失败",
    default_code: str = ErrorCode.INTERNAL_ERROR.value,
    **extra_details
) -> AutoReconError:
    """包装任意异常为 AutoReconError
    
    Args:
        e: 原始异常
        default_message: 默认错误消息
        default_code: 默认错误码
        extra_details: 额外详情
        
    Returns:
        AutoReconError 实例
    """
    if isinstance(e, AutoReconError):
        # 已经是标准异常，合并详情
        e.details.update(extra_details)
        return e
    
    # 常见异常类型映射
    error_mapping = {
        asyncio.TimeoutError: (ErrorCode.CONNECTION_TIMEOUT.value, "连接超时"),
        ConnectionRefusedError: (ErrorCode.CONNECTION_REFUSED.value, "连接被拒绝"),
        ConnectionResetError: (ErrorCode.NETWORK_ERROR.value, "连接被重置"),
        FileNotFoundError: (ErrorCode.FILE_NOT_FOUND.value, "文件未找到"),
        PermissionError: (ErrorCode.PERMISSION_DENIED.value, "权限不足"),
        OSError: (ErrorCode.NETWORK_ERROR.value, "系统错误"),
    }
    
    for exc_type, (code, msg) in error_mapping.items():
        if isinstance(e, exc_type):
            return AutoReconError(
                f"{default_message}: {msg}",
                code=code,
                details={"original_error": str(e), **extra_details},
                cause=e
            )
    
    # 默认情况
    return AutoReconError(
        f"{default_message}: {str(e)}",
        code=default_code,
        details={"original_error": str(e), **extra_details},
        cause=e
    )


# 导入 asyncio 用于异常映射
import asyncio


@dataclass
class ErrorContext:
    """错误上下文 - 用于错误收集和报告"""
    errors: List[AutoReconError] = field(default_factory=list)
    warnings: List[AutoReconError] = field(default_factory=list)
    
    def add_error(self, error: AutoReconError):
        self.errors.append(error)
    
    def add_warning(self, warning: AutoReconError):
        self.warnings.append(warning)
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }
    
    def clear(self):
        self.errors.clear()
        self.warnings.clear()


if __name__ == "__main__":
    # 测试异常体系
    print("异常体系测试:")
    
    # 测试基础异常
    try:
        raise AutoReconError("测试错误", ErrorCode.VALIDATION_ERROR.value, {"field": "test"})
    except AutoReconError as e:
        print(f"  基础异常: {e}")
        print(f"  字典格式: {e.to_dict()}")
    
    # 测试验证错误
    try:
        raise ValidationError("域名无效", field="domain", violation_type="INVALID_FORMAT")
    except ValidationError as e:
        print(f"  验证错误: {e}")
        print(f"  详情: {e.details}")
    
    # 测试安全错误
    try:
        raise SSRFError("SSRF拦截", blocked_ip="192.168.1.1")
    except SSRFError as e:
        print(f"  SSRF错误: {e}")
        print(f"  详情: {e.details}")
    
    # 测试包装函数
    try:
        raise ConnectionRefusedError("Connection refused")
    except Exception as e:
        wrapped = wrap_exception(e, "扫描失败", scanner="subdomain")
        print(f"  包装异常: {wrapped}")
        print(f"  详情: {wrapped.details}")