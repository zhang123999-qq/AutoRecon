#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.1 - 单元测试
核心模块测试覆盖
"""

import pytest
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============== 持久化缓存测试 ==============

class TestSQLiteCache:
    """SQLite 缓存测试"""
    
    @pytest.fixture
    def cache(self, tmp_path):
        """创建测试缓存"""
        from core.persistent_cache import SQLiteCache
        db_path = tmp_path / "test_cache.db"
        return SQLiteCache(str(db_path), default_ttl=3600)
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试设置和获取"""
        # 设置
        result = cache.set("test_key", {"data": "test_value"})
        assert result is True
        
        # 获取
        value = cache.get("test_key")
        assert value == {"data": "test_value"}
    
    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """测试删除"""
        cache.set("test_key", "test_value")
        
        # 删除
        result = await cache.delete("test_key")
        assert result is True
        
        # 验证删除
        value = cache.get("test_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_exists(self, cache):
        """测试存在性检查"""
        cache.set("test_key", "test_value")
        
        assert await cache.exists("test_key") is True
        assert await cache.exists("nonexistent") is False
    
    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """测试清空"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        await cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache):
        """测试过期"""
        # 设置 1 秒过期
        cache.set("test_key", "test_value", ttl=1)
        
        # 立即获取应该有值
        value = cache.get("test_key")
        assert value == "test_value"
        
        # 等待过期
        await asyncio.sleep(1.5)
        
        # 过期后应该无值
        value = cache.get("test_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_get_stats(self, cache):
        """测试统计"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        stats = await cache.get_stats()
        
        assert stats['total_entries'] == 2
        assert stats['total_size_bytes'] > 0


# ============== 自适应并发测试 ==============

class TestAdaptiveConcurrency:
    """自适应并发测试"""
    
    @pytest.fixture
    def controller(self):
        """创建测试控制器"""
        from core.adaptive_concurrency import AdaptiveConcurrency, ConcurrencyConfig
        
        config = ConcurrencyConfig(
            initial=50,
            min_concurrency=10,
            max_concurrency=200,
        )
        return AdaptiveConcurrency(config)
    
    def test_initial_concurrency(self, controller):
        """测试初始并发数"""
        assert controller.concurrency == 50
    
    def test_record_request(self, controller):
        """测试记录请求"""
        controller.start()
        
        # 记录成功请求
        controller.record_request(0.5, success=True)
        controller.record_request(0.3, success=True)
        
        metrics = controller.metrics
        
        assert metrics.total_requests == 2
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 0
    
    def test_record_failed_request(self, controller):
        """测试记录失败请求"""
        controller.start()
        
        controller.record_request(1.0, success=False)
        
        metrics = controller.metrics
        
        assert metrics.failed_requests == 1
        assert metrics.error_rate == 1.0
    
    def test_adjust_increase(self, controller):
        """测试增加并发"""
        controller.start()
        
        # 模拟快速响应（达到预热数量）
        for _ in range(150):
            controller.record_request(0.3, success=True)
        
        # 允许调整
        controller._last_adjustment = 0
        new_concurrency = controller.adjust()
        
        # 响应快时应该尝试增加
        assert new_concurrency >= controller.config.initial
    
    def test_adjust_decrease(self, controller):
        """测试减少并发"""
        controller.start()
        
        # 模拟慢速响应（达到预热数量）
        for _ in range(150):
            controller.record_request(2.0, success=True)
        
        # 允许调整
        controller._last_adjustment = 0
        new_concurrency = controller.adjust()
        
        # 响应慢时应该尝试减少
        assert new_concurrency <= controller.config.initial
    
    def test_pause_on_high_error_rate(self, controller):
        """测试高错误率暂停"""
        controller.start()
        
        # 模拟高错误率（达到预热数量）
        for _ in range(150):
            controller.record_request(0.5, success=False)
        
        # 直接调用内部方法
        controller._handle_high_error_rate()
        
        # 错误率高时应该暂停
        assert controller.state.value == "paused"
    
    def test_get_status(self, controller):
        """测试状态获取"""
        controller.start()
        controller.record_request(0.5, success=True)
        
        status = controller.get_status()
        
        assert 'concurrency' in status
        assert 'state' in status
        assert 'metrics' in status


# ============== 插件系统测试 ==============

class TestPluginSystem:
    """插件系统测试"""
    
    @pytest.fixture
    def manager(self, tmp_path):
        """创建测试管理器"""
        from core.plugin_system import PluginManager
        
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        
        return PluginManager(plugin_dirs=[str(plugin_dir)])
    
    def test_list_plugins(self, manager):
        """测试列出插件"""
        plugins = manager.list_plugins()
        
        assert isinstance(plugins, list)
    
    def test_register_plugin(self, manager):
        """测试注册插件"""
        from core.plugin_system import BasePlugin
        
        class TestPlugin(BasePlugin):
            NAME = "test_plugin"
            async def run(self):
                return {"status": "ok"}
        
        result = manager.register(TestPlugin)
        
        assert result is True
        assert "test_plugin" in manager.plugins
    
    def test_enable_disable(self, manager):
        """测试启用/禁用"""
        from core.plugin_system import BasePlugin
        
        class TestPlugin(BasePlugin):
            NAME = "test_plugin"
            async def run(self):
                return {}
        
        manager.register(TestPlugin)
        
        # 禁用
        manager.disable("test_plugin")
        assert manager.enabled_plugins["test_plugin"] is False
        
        # 启用
        manager.enable("test_plugin")
        assert manager.enabled_plugins["test_plugin"] is True
    
    @pytest.mark.asyncio
    async def test_run_plugin(self, manager):
        """测试运行插件"""
        from core.plugin_system import BasePlugin
        
        class TestPlugin(BasePlugin):
            NAME = "test_plugin"
            async def run(self):
                return {"domain": self.target, "status": "ok"}
        
        manager.register(TestPlugin)
        
        result = await manager.run_plugin("test_plugin", "example.com")
        
        assert result["domain"] == "example.com"
        assert result["status"] == "ok"


# ============== JS 分析测试 ==============

class TestJSAnalyzer:
    """JS 分析器测试"""
    
    @pytest.fixture
    def analyzer(self):
        """创建测试分析器"""
        from modules.js_analyzer import JavaScriptAnalyzer
        return JavaScriptAnalyzer("https://example.com", timeout=5)
    
    def test_extract_urls_from_js(self, analyzer):
        """测试 URL 提取"""
        js_content = """
        const apiUrl = 'https://api.example.com/v1/users';
        fetch('/api/data.json');
        """
        
        urls = analyzer._extract_urls_from_js(js_content)
        
        assert "https://api.example.com/v1/users" in urls
    
    def test_extract_secrets(self, analyzer):
        """测试敏感信息提取"""
        js_content = """
        const apiKey = 'AKIAIOSFODNN7EXAMPLE';
        const token = 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx';
        """
        
        secrets = analyzer._extract_secrets(js_content)
        
        assert len(secrets) >= 1
    
    def test_identify_technologies(self, analyzer):
        """测试技术栈识别"""
        js_content = """
        React.createElement('div', null, 'Hello');
        Vue.component('app', {});
        """
        
        techs = analyzer._identify_technologies(js_content)
        
        assert 'React' in techs or 'Vue.js' in techs


# ============== 运行测试 ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
