#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块基类 - 所有扫描模块的父类
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from .logger import Logger


class BaseModule(ABC):
    """扫描模块基类
    
    所有扫描模块都应继承此类并实现 run() 方法
    """
    
    # 模块元信息（子类可覆盖）
    MODULE_NAME = "Base Module"
    MODULE_DESCRIPTION = "Base module description"
    MODULE_VERSION = "1.0"
    
    def __init__(self, target: str, config: Optional[Dict] = None):
        """初始化模块
        
        Args:
            target: 扫描目标（域名、IP或URL）
            config: 配置字典
        """
        self.target = target
        self.config = config or {}
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.start_time = None
        self.end_time = None
    
    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """执行扫描（子类必须实现）
        
        Returns:
            扫描结果字典
        """
        raise NotImplementedError("子类必须实现 run() 方法")
    
    def pre_run(self):
        """扫描前执行（可覆盖）"""
        self.start_time = time.time()
        Logger.module_header(self.MODULE_NAME)
    
    def post_run(self):
        """扫描后执行（可覆盖）"""
        self.end_time = time.time()
        if self.errors:
            Logger.warn(f"模块执行过程中发生 {len(self.errors)} 个错误")
    
    def execute(self) -> Dict[str, Any]:
        """执行完整扫描流程
        
        包含：pre_run -> run -> post_run
        
        Returns:
            扫描结果字典
        """
        self.pre_run()
        try:
            self.results = self.run()
        except Exception as e:
            self.errors.append(str(e))
            Logger.error(f"模块执行失败: {e}")
            self.results = {'error': str(e)}
        self.post_run()
        return self.get_results()
    
    def get_results(self) -> Dict[str, Any]:
        """获取扫描结果"""
        return {
            'module': self.MODULE_NAME,
            'version': self.MODULE_VERSION,
            'target': self.target,
            'results': self.results,
            'errors': self.errors,
            'duration': self.get_duration()
        }
    
    def get_duration(self) -> Optional[float]:
        """获取执行耗时（秒）"""
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 2)
        return None
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
        Logger.error(error)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)


class ModuleRegistry:
    """模块注册表"""
    
    _modules: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, module_class: type):
        """注册模块"""
        cls._modules[name] = module_class
    
    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """获取模块类"""
        return cls._modules.get(name)
    
    @classmethod
    def list_modules(cls) -> List[str]:
        """列出所有已注册模块"""
        return list(cls._modules.keys())
    
    @classmethod
    def create(cls, name: str, target: str, config: Optional[Dict] = None) -> Optional[BaseModule]:
        """创建模块实例"""
        module_class = cls.get(name)
        if module_class:
            return module_class(target, config)
        return None


def register_module(name: str):
    """模块注册装饰器
    
    用法:
        @register_module('subdomain')
        class SubdomainCollector(BaseModule):
            ...
    """
    def decorator(cls):
        ModuleRegistry.register(name, cls)
        return cls
    return decorator