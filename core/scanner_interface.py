#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 扫描器插件接口
定义标准扫描器契约，支持动态插件加载
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Type, Callable
from enum import Enum
from contextlib import asynccontextmanager
import importlib
import importlib.util
from pathlib import Path

from core.exceptions import AutoReconError, ScannerError, wrap_exception
from core.config_v2 import get_settings

logger = logging.getLogger(__name__)


class ScanStatus(Enum):
    """扫描状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScanResult:
    """扫描结果标准格式"""
    module: str
    target: str
    status: ScanStatus = ScanStatus.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "target": self.target,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "duration": self.duration,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ScanProgress:
    """扫描进度"""
    module: str
    target: str
    current: int = 0
    total: int = 0
    message: str = ""
    
    @property
    def percentage(self) -> int:
        if self.total == 0:
            return 0
        return int((self.current / self.total) * 100)


class IScanner(ABC):
    """扫描器标准接口
    
    所有扫描器必须实现此接口，确保统一的调用方式。
    """
    
    # 扫描器元数据（类属性）
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "general"  # general, recon, attack, stress, etc.
    dependencies: List[str] = field(default_factory=list)
    requires_auth: bool = False
    is_intrusive: bool = False
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.settings = get_settings()
        self._cancelled = False
        self._progress_callback: Optional[Callable[[ScanProgress], None]] = None
    
    @property
    @abstractmethod
    def supported_targets(self) -> List[str]:
        """支持的目标类型: domain, ip, url, cidr"""
        pass
    
    @abstractmethod
    async def validate_target(self, target: str) -> bool:
        """验证目标是否适用此扫描器"""
        pass
    
    @abstractmethod
    async def scan(self, target: str, options: Optional[Dict[str, Any]] = None) -> ScanResult:
        """执行扫描
        
        Args:
            target: 扫描目标
            options: 扫描选项
            
        Returns:
            ScanResult 对象
        """
        pass
    
    async def initialize(self) -> bool:
        """初始化扫描器（可选重写）
        
        Returns:
            是否初始化成功
        """
        return True
    
    async def cleanup(self):
        """清理资源（可选重写）"""
        pass
    
    def set_progress_callback(self, callback: Callable[[ScanProgress], None]):
        """设置进度回调"""
        self._progress_callback = callback
    
    def _report_progress(self, current: int, total: int, message: str = ""):
        """报告进度"""
        if self._progress_callback:
            progress = ScanProgress(
                module=self.name,
                target=getattr(self, '_current_target', ''),
                current=current,
                total=total,
                message=message
            )
            try:
                self._progress_callback(progress)
            except Exception as e:
                logger.warning(f"进度回调异常: {e}")
    
    def cancel(self):
        """取消扫描"""
        self._cancelled = True
    
    def is_cancelled(self) -> bool:
        return self._cancelled


class ScannerRegistry:
    """扫描器注册中心
    
    管理所有已注册的扫描器，支持：
    - 自动发现和注册
    - 依赖检查
    - 按名称/分类查找
    - 插件动态加载
    """
    
    _scanners: Dict[str, Type[IScanner]] = {}
    _instances: Dict[str, IScanner] = {}
    _categories: Dict[str, List[str]] = {}
    
    @classmethod
    def register(cls, scanner_class: Type[IScanner]) -> bool:
        """注册扫描器类
        
        Args:
            scanner_class: 扫描器类
            
        Returns:
            是否注册成功
        """
        if not scanner_class.name:
            logger.error(f"扫描器缺少名称: {scanner_class}")
            return False
        
        if scanner_class.name in cls._scanners:
            logger.warning(f"扫描器已存在，覆盖: {scanner_class.name}")
        
        cls._scanners[scanner_class.name] = scanner_class
        
        # 更新分类索引
        category = scanner_class.category
        if category not in cls._categories:
            cls._categories[category] = []
        if scanner_class.name not in cls._categories[category]:
            cls._categories[category].append(scanner_class.name)
        
        logger.info(f"注册扫描器: {scanner_class.name} (v{scanner_class.version})")
        return True
    
    @classmethod
    def unregister(cls, name: str) -> bool:
        """注销扫描器"""
        if name in cls._scanners:
            del cls._scanners[name]
            # 从分类中移除
            for cat, scanners in cls._categories.items():
                if name in scanners:
                    scanners.remove(name)
            return True
        return False
    
    @classmethod
    def get(cls, name: str) -> Optional[Type[IScanner]]:
        """获取扫描器类"""
        return cls._scanners.get(name)
    
    @classmethod
    def get_instance(cls, name: str, config: Optional[Dict] = None) -> Optional[IScanner]:
        """获取或创建扫描器实例（单例模式）"""
        if name not in cls._instances:
            scanner_class = cls.get(name)
            if not scanner_class:
                return None
            instance = scanner_class(config)
            cls._instances[name] = instance
        return cls._instances[name]
    
    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        """列出所有扫描器"""
        return [
            {
                "name": s.name,
                "version": s.version,
                "description": s.description,
                "author": s.author,
                "category": s.category,
                "dependencies": s.dependencies,
                "requires_auth": s.requires_auth,
                "is_intrusive": s.is_intrusive,
                "supported_targets": s.supported_targets,
            }
            for s in cls._scanners.values()
        ]
    
    @classmethod
    def list_by_category(cls, category: str) -> List[str]:
        """按分类列出扫描器"""
        return cls._categories.get(category, [])
    
    @classmethod
    def list_categories(cls) -> List[str]:
        """列出所有分类"""
        return list(cls._categories.keys())
    
    @classmethod
    def check_dependencies(cls, name: str) -> tuple[bool, List[str]]:
        """检查扫描器依赖
        
        Returns:
            (是否满足, 缺失的依赖列表)
        """
        scanner_class = cls.get(name)
        if not scanner_class:
            return False, ["扫描器不存在"]
        
        missing = []
        for dep in scanner_class.dependencies:
            try:
                importlib.import_module(dep)
            except ImportError:
                missing.append(dep)
        
        return len(missing) == 0, missing


def scanner_plugin(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    category: str = "general",
    dependencies: List[str] = None,
    requires_auth: bool = False,
    is_intrusive: bool = False,
    supported_targets: List[str] = None
):
    """扫描器装饰器 - 自动注册
    
    使用示例:
        @scanner_plugin("subdomain", category="recon", description="子域名收集")
        class SubdomainScanner(IScanner):
            ...
    """
    def decorator(cls: Type[IScanner]) -> Type[IScanner]:
        # 设置类属性
        cls.name = name
        cls.version = version
        cls.description = description
        cls.author = author
        cls.category = category
        cls.dependencies = dependencies or []
        cls.requires_auth = requires_auth
        cls.is_intrusive = is_intrusive
        cls.supported_targets = supported_targets or ["domain"]
        
        # 自动注册
        ScannerRegistry.register(cls)
        return cls
    
    return decorator


class PluginLoader:
    """插件加载器 - 支持从目录动态加载插件"""
    
    def __init__(self, plugin_dirs: List[str] = None):
        self.plugin_dirs = plugin_dirs or ["plugins", "modules"]
        self.loaded_modules: Dict[str, Any] = {}
    
    def load_all(self, config: Optional[Dict] = None) -> Dict[str, bool]:
        """加载所有插件目录"""
        results = {}
        for plugin_dir in self.plugin_dirs:
            results.update(self.load_from_directory(plugin_dir, config))
        return results
    
    def load_from_directory(self, directory: str, config: Optional[Dict] = None) -> Dict[str, bool]:
        """从目录加载插件"""
        results = {}
        path = Path(directory)
        if not path.exists():
            logger.warning(f"插件目录不存在: {directory}")
            return results
        
        for py_file in path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            try:
                result = self._load_plugin_module(py_file, config)
                results[py_file.stem] = result
            except Exception as e:
                logger.error(f"加载插件失败 {py_file}: {e}")
                results[py_file.stem] = False
        
        return results
    
    def _load_plugin_module(self, file_path: Path, config: Optional[Dict] = None) -> bool:
        """加载单个插件模块"""
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if not spec or not spec.loader:
            return False
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 查找并注册扫描器类
        registered = False
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, IScanner) and 
                attr is not IScanner):
                
                # 实例化以触发注册（如果使用了装饰器）
                # 或者检查是否已通过装饰器注册
                if attr.name and attr.name in ScannerRegistry._scanners:
                    registered = True
        
        self.loaded_modules[file_path.stem] = module
        return registered
    
    def unload_all(self):
        """卸载所有插件"""
        self.loaded_modules.clear()


class ScanOrchestrator:
    """扫描编排器 - 管理多扫描器协同工作"""
    
    def __init__(
        self, 
        max_concurrent: int = 5,
        default_timeout: float = 300.0,
        config: Optional[Dict] = None
    ):
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.config = config or {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results: Dict[str, ScanResult] = {}
        self._progress_callback: Optional[Callable[[ScanProgress], None]] = None
    
    def set_progress_callback(self, callback: Callable[[ScanProgress], None]):
        self._progress_callback = callback
    
    async def run_scan(
        self, 
        target: str, 
        modules: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ScanResult]:
        """运行多模块扫描
        
        Args:
            target: 扫描目标
            modules: 模块名称列表
            options: 全局选项
            
        Returns:
            模块名 -> 扫描结果 映射
        """
        options = options or {}
        self.results = {}
        
        # 验证模块
        valid_modules = []
        for module_name in modules:
            scanner_class = ScannerRegistry.get(module_name)
            if not scanner_class:
                logger.warning(f"未知扫描模块: {module_name}")
                self.results[module_name] = ScanResult(
                    module=module_name,
                    target=target,
                    status=ScanStatus.FAILED,
                    error=f"未知扫描模块: {module_name}"
                )
                continue
            
            # 检查依赖
            ok, missing = ScannerRegistry.check_dependencies(module_name)
            if not ok:
                logger.warning(f"模块 {module_name} 缺少依赖: {missing}")
                self.results[module_name] = ScanResult(
                    module=module_name,
                    target=target,
                    status=ScanStatus.FAILED,
                    error=f"缺少依赖: {missing}"
                )
                continue
            
            # 验证目标
            instance = ScannerRegistry.get_instance(module_name, self.config.get(module_name))
            if instance:
                instance.set_progress_callback(self._on_progress)
                try:
                    valid = await instance.validate_target(target)
                    if not valid:
                        self.results[module_name] = ScanResult(
                            module=module_name,
                            target=target,
                            status=ScanStatus.FAILED,
                            error=f"目标不适用于此模块: {target}"
                        )
                        continue
                except Exception as e:
                    logger.error(f"目标验证失败 {module_name}: {e}")
                    self.results[module_name] = ScanResult(
                        module=module_name,
                        target=target,
                        status=ScanStatus.FAILED,
                        error=f"目标验证异常: {e}"
                    )
                    continue
            
            valid_modules.append(module_name)
        
        # 并发执行
        tasks = [
            self._run_single_scan(module_name, target, options.get(module_name, {}))
            for module_name in valid_modules
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return self.results
    
    async def _run_single_scan(
        self, 
        module_name: str, 
        target: str, 
        module_options: Dict[str, Any]
    ):
        """运行单个扫描"""
        async with self.semaphore:
            if self._is_cancelled():
                return
            
            scanner_class = ScannerRegistry.get(module_name)
            if not scanner_class:
                return
            
            instance = ScannerRegistry.get_instance(module_name, self.config.get(module_name))
            if not instance:
                return
            
            instance.set_progress_callback(self._on_progress)
            instance._current_target = target
            
            result = ScanResult(module=module_name, target=target)
            result.status = ScanStatus.RUNNING
            import time
            result.started_at = time.time()
            self.results[module_name] = result
            
            try:
                scan_result = await asyncio.wait_for(
                    instance.scan(target, module_options),
                    timeout=self.default_timeout
                )
                result.status = scan_result.status
                result.data = scan_result.data
                result.error = scan_result.error
            except asyncio.TimeoutError:
                result.status = ScanStatus.FAILED
                result.error = f"扫描超时 ({self.default_timeout}s)"
            except asyncio.CancelledError:
                result.status = ScanStatus.CANCELLED
                result.error = "扫描被取消"
            except Exception as e:
                result.status = ScanStatus.FAILED
                result.error = str(e)
                logger.error(f"扫描异常 {module_name}: {e}")
            finally:
                result.completed_at = time.time()
                result.duration = result.completed_at - result.started_at
                self.results[module_name] = result
    
    def _on_progress(self, progress: ScanProgress):
        """内部进度处理"""
        if self._progress_callback:
            try:
                self._progress_callback(progress)
            except Exception:
                pass
    
    def _is_cancelled(self) -> bool:
        return False  # 可以扩展支持全局取消
    
    def cancel_all(self):
        """取消所有扫描"""
        for instance in ScannerRegistry._instances.values():
            instance.cancel()
    
    def get_summary(self) -> Dict[str, Any]:
        """获取扫描摘要"""
        total = len(self.results)
        completed = sum(1 for r in self.results.values() if r.status == ScanStatus.COMPLETED)
        failed = sum(1 for r in self.results.values() if r.status == ScanStatus.FAILED)
        cancelled = sum(1 for r in self.results.values() if r.status == ScanStatus.CANCELLED)
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "results": {k: v.to_dict() for k, v in self.results.items()},
        }


# 使用示例
@scanner_plugin(
    name="example",
    version="1.0.0",
    description="示例扫描器",
    category="recon",
    supported_targets=["domain", "ip"]
)
class ExampleScanner(IScanner):
    """示例扫描器实现"""
    
    @property
    def supported_targets(self) -> List[str]:
        return ["domain", "ip"]
    
    async def validate_target(self, target: str) -> bool:
        return True
    
    async def scan(self, target: str, options: Dict = None) -> ScanResult:
        result = ScanResult(module=self.name, target=target)
        result.status = ScanStatus.RUNNING
        
        # 模拟扫描
        await asyncio.sleep(0.1)
        
        result.data = {"example": "data"}
        result.status = ScanStatus.COMPLETED
        return result


if __name__ == "__main__":
    # 测试注册表
    print("扫描器注册表测试:")
    for info in ScannerRegistry.list_all():
        print(f"  {info['name']} (v{info['version']}) - {info['category']}")
    
    print(f"\n分类: {ScannerRegistry.list_categories()}")
    
    # 测试实例化
    instance = ScannerRegistry.get_instance("example")
    if instance:
        print(f"\n实例化成功: {instance.name}")