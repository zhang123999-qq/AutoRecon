#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 插件系统
支持自定义扫描模块，动态加载扩展
"""

import os
import sys
import importlib
import inspect
from typing import Dict, List, Type, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from pathlib import Path


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    author: str
    description: str
    module_name: str
    enabled: bool = True
    priority: int = 100  # 执行优先级，数字越小越优先
    tags: List[str] = field(default_factory=list)


class BasePlugin(ABC):
    """插件基类 - 所有插件必须继承此类"""
    
    # 插件元信息（子类必须覆盖）
    NAME: str = "base_plugin"
    VERSION: str = "1.0.0"
    AUTHOR: str = ""
    DESCRIPTION: str = "基础插件"
    TAGS: List[str] = []
    PRIORITY: int = 100
    
    def __init__(self, target: str, **kwargs):
        self.target = target
        self.config = kwargs
        self.results: Dict[str, Any] = {}
    
    @abstractmethod
    async def run(self) -> Dict[str, Any]:
        """
        执行插件逻辑（必须实现）
        
        Returns:
            Dict[str, Any]: 扫描结果
        """
        pass
    
    def get_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            name=self.NAME,
            version=self.VERSION,
            author=self.AUTHOR,
            description=self.DESCRIPTION,
            module_name=self.__class__.__module__,
            enabled=True,
            priority=self.PRIORITY,
            tags=self.TAGS,
        )


class PluginManager:
    """
    插件管理器
    
    功能：
    - 自动发现并加载插件
    - 插件启用/禁用
    - 按优先级执行
    - 结果聚合
    """
    
    def __init__(self, plugin_dirs: List[str] = None):
        """
        初始化插件管理器
        
        Args:
            plugin_dirs: 插件目录列表，默认为 ['plugins/']
        """
        self.plugin_dirs = plugin_dirs or ['plugins']
        self.plugins: Dict[str, Type[BasePlugin]] = {}
        self.enabled_plugins: Dict[str, bool] = {}
        
        # 自动发现插件
        self.discover()
    
    def discover(self) -> int:
        """
        自动发现插件
        
        Returns:
            int: 发现的插件数量
        """
        count = 0
        
        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir)
            
            if not plugin_path.exists():
                plugin_path.mkdir(parents=True, exist_ok=True)
                # 创建 __init__.py
                (plugin_path / '__init__.py').write_text(
                    '# AutoRecon Plugin Directory\n'
                )
                continue
            
            # 遍历插件目录
            for py_file in plugin_path.glob('*.py'):
                if py_file.name.startswith('_'):
                    continue
                
                module_name = py_file.stem
                
                try:
                    # 动态导入模块
                    if plugin_dir not in sys.path:
                        sys.path.insert(0, str(plugin_path.parent))
                    
                    module = importlib.import_module(f"{plugin_path.name}.{module_name}")
                    
                    # 查找 BasePlugin 子类
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BasePlugin) and 
                            obj is not BasePlugin and
                            obj.__module__ == module.__name__
                        ):
                            plugin_name = obj.NAME
                            self.plugins[plugin_name] = obj
                            self.enabled_plugins[plugin_name] = True
                            count += 1
                            
                except Exception as e:
                    print(f"[!] 加载插件 {module_name} 失败: {e}")
        
        return count
    
    def register(self, plugin_class: Type[BasePlugin]) -> bool:
        """
        手动注册插件
        
        Args:
            plugin_class: 插件类
            
        Returns:
            bool: 注册是否成功
        """
        try:
            if not issubclass(plugin_class, BasePlugin):
                raise TypeError(f"{plugin_class} 不是 BasePlugin 的子类")
            
            plugin_name = plugin_class.NAME
            self.plugins[plugin_name] = plugin_class
            self.enabled_plugins[plugin_name] = True
            return True
            
        except Exception as e:
            print(f"[!] 注册插件失败: {e}")
            return False
    
    def enable(self, plugin_name: str) -> bool:
        """启用插件"""
        if plugin_name in self.plugins:
            self.enabled_plugins[plugin_name] = True
            return True
        return False
    
    def disable(self, plugin_name: str) -> bool:
        """禁用插件"""
        if plugin_name in self.plugins:
            self.enabled_plugins[plugin_name] = False
            return True
        return False
    
    def get_plugin(self, plugin_name: str) -> Optional[Type[BasePlugin]]:
        """获取插件类"""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """列出所有插件"""
        plugins = []
        
        for name, plugin_class in self.plugins.items():
            info = PluginInfo(
                name=name,
                version=plugin_class.VERSION,
                author=plugin_class.AUTHOR,
                description=plugin_class.DESCRIPTION,
                module_name=plugin_class.__module__,
                enabled=self.enabled_plugins.get(name, True),
                priority=plugin_class.PRIORITY,
                tags=plugin_class.TAGS,
            )
            plugins.append(info)
        
        # 按优先级排序
        plugins.sort(key=lambda p: p.priority)
        return plugins
    
    def get_enabled_plugins(self) -> List[Type[BasePlugin]]:
        """获取已启用的插件（按优先级排序）"""
        enabled = [
            plugin for name, plugin in self.plugins.items()
            if self.enabled_plugins.get(name, True)
        ]
        return sorted(enabled, key=lambda p: p.PRIORITY)
    
    async def run_plugin(
        self, 
        plugin_name: str, 
        target: str, 
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        运行单个插件
        
        Args:
            plugin_name: 插件名称
            target: 目标
            **kwargs: 插件参数
            
        Returns:
            Optional[Dict]: 扫描结果
        """
        plugin_class = self.plugins.get(plugin_name)
        if not plugin_class:
            return None
        
        if not self.enabled_plugins.get(plugin_name, True):
            return None
        
        try:
            plugin = plugin_class(target, **kwargs)
            return await plugin.run()
        except Exception as e:
            print(f"[!] 插件 {plugin_name} 执行失败: {e}")
            return {"error": str(e)}
    
    async def run_all(
        self, 
        target: str, 
        tags: List[str] = None,
        **kwargs
    ) -> Dict[str, Dict[str, Any]]:
        """
        运行所有已启用的插件
        
        Args:
            target: 目标
            tags: 只运行包含指定标签的插件
            **kwargs: 插件参数
            
        Returns:
            Dict[str, Dict]: 插件名 -> 结果
        """
        results = {}
        
        for plugin_class in self.get_enabled_plugins():
            # 标签过滤
            if tags:
                if not any(tag in plugin_class.TAGS for tag in tags):
                    continue
            
            plugin_name = plugin_class.NAME
            result = await self.run_plugin(plugin_name, target, **kwargs)
            
            if result:
                results[plugin_name] = result
        
        return results


# ============== 示例插件 ==============

class ExamplePlugin(BasePlugin):
    """示例插件 - 检测 robots.txt"""
    
    NAME = "robots_checker"
    VERSION = "1.0.0"
    AUTHOR = "AutoRecon Team"
    DESCRIPTION = "检测 robots.txt 文件内容"
    TAGS = ["info", "seo"]
    PRIORITY = 10  # 高优先级
    
    async def run(self) -> Dict[str, Any]:
        """执行检测"""
        import aiohttp
        
        result = {
            "found": False,
            "url": f"http://{self.target}/robots.txt",
            "content": None,
            "disallows": [],
            "allows": [],
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(result["url"], timeout=10) as resp:
                    if resp.status == 200:
                        result["found"] = True
                        content = await resp.text()
                        result["content"] = content[:1000]  # 限制大小
                        
                        # 解析 Disallow/Allow
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.lower().startswith('disallow:'):
                                result["disallows"].append(line.split(':', 1)[1].strip())
                            elif line.lower().startswith('allow:'):
                                result["allows"].append(line.split(':', 1)[1].strip())
        
        except Exception as e:
            result["error"] = str(e)
        
        return result


# ============== 使用示例 ==============

async def main():
    """示例：插件系统使用"""
    
    # 创建插件管理器
    manager = PluginManager(plugin_dirs=['plugins'])
    
    # 手动注册示例插件
    manager.register(ExamplePlugin)
    
    # 列出所有插件
    print("\n已加载插件:")
    for info in manager.list_plugins():
        status = "✓" if info.enabled else "✗"
        print(f"  [{status}] {info.name} v{info.version} - {info.description}")
    
    # 运行插件
    print("\n运行插件...")
    results = await manager.run_all("example.com")
    
    for plugin_name, result in results.items():
        print(f"\n[{plugin_name}] 结果:")
        print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
