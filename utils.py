#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信息收集自动化工具 - 工具类 (兼容层)
v2.3 重构: 此文件保留用于向后兼容，实际实现已移至 core/ 模块
"""

# 从 core 模块导入所有工具类
from core import (
    # 日志
    Logger, get_logger,
    
    # HTTP
    HTTPClient, RateLimiter,
    
    # DNS
    DNSResolver,
    
    # 扫描工具
    PortChecker, CDNDetector, SensitiveDetector,
    
    # 报告
    ReportGenerator,
    
    # 基类
    BaseModule,
    
    # 工具
    ProgressBar, Timer, RetryHelper, CommandRunner
)

# 向后兼容：保留原有的工具类名
__all__ = [
    'Logger', 'get_logger',
    'HTTPClient', 'RateLimiter', 
    'DNSResolver',
    'PortChecker', 'CDNDetector', 'SensitiveDetector',
    'ReportGenerator',
    'BaseModule',
    'ProgressBar', 'Timer', 'RetryHelper', 'CommandRunner'
]
