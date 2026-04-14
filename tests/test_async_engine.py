#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.2 - 异步引擎单元测试
测试核心异步组件的功能
"""

import pytest
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.async_engine import AsyncCache, AsyncHTTPClient, AsyncDNSResolver, AsyncRateLimiter


class TestAsyncCache:
    """AsyncCache 测试"""
    
    def test_set_and_get(self):
        """测试基本设置和获取"""
        cache = AsyncCache(ttl=10)
        
        # 设置值
        cache.set("key1", "value1")
        cache.set("key2", {"data": "value2"})
        cache.set("key3", [1, 2, 3])
        
        # 获取值
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == {"data": "value2"}
        assert cache.get("key3") == [1, 2, 3]
        
        # 不存在的键
        assert cache.get("nonexistent") is None
    
    def test_ttl_expiry(self):
        """测试 TTL 过期"""
        import time
        cache = AsyncCache(ttl=1)  # 1秒过期
        
        cache.set("key", "value")
        assert cache.get("key") == "value"
        
        # 等待过期
        time.sleep(1.1)
        assert cache.get("key") is None
    
    def test_max_size(self):
        """测试最大容量限制"""
        cache = AsyncCache(max_size=3)
        
        # 添加3个值
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # 添加第4个值应该触发清理
        cache.set("key4", "value4")
        
        # 检查是否有值被清理（取决于清理策略）
        # 至少应该能获取新值
        assert cache.get("key4") == "value4"
    
    def test_clear(self):
        """测试清空缓存"""
        cache = AsyncCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # 清空
        asyncio.run(cache.clear())
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestAsyncHTTPClient:
    """AsyncHTTPClient 测试"""
    
    @pytest.mark.asyncio
    async def test_https_request(self):
        """测试 HTTPS 请求"""
        async with AsyncHTTPClient(verify_ssl=True) as client:
            resp = await client.get("https://httpbin.org/get")
            
            assert resp["status"] == 200
            assert "headers" in resp
            assert "body" in resp
            assert "url" in resp
    
    @pytest.mark.asyncio
    async def test_http_request(self):
        """测试 HTTP 请求"""
        async with AsyncHTTPClient(verify_ssl=False) as client:
            resp = await client.get("http://httpbin.org/get")
            
            assert resp["status"] == 200
    
    @pytest.mark.asyncio
    async def test_cache(self):
        """测试缓存功能"""
        from core.async_engine import AsyncCache
        
        cache = AsyncCache(ttl=300)
        async with AsyncHTTPClient(cache=cache) as client:
            # 第一次请求
            resp1 = await client.get("https://httpbin.org/get")
            
            # 第二次请求应该使用缓存
            resp2 = await client.get("https://httpbin.org/get")
            
            # 验证缓存工作
            assert resp1 == resp2


class TestAsyncRateLimiter:
    """AsyncRateLimiter 测试"""
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """测试速率限制"""
        import time
        
        # 每秒10个请求，突发20个
        limiter = AsyncRateLimiter(rate=10.0, burst=20)
        
        # 立即获取20个令牌（突发）
        start = time.time()
        for _ in range(20):
            await limiter.acquire()
        burst_time = time.time() - start
        
        # 突发应该很快
        assert burst_time < 0.1
        
        # 第21个请求应该被限制
        start = time.time()
        await limiter.acquire()
        limited_time = time.time() - start
        
        # 应该有延迟
        assert limited_time > 0.05


class TestAsyncDNSResolver:
    """AsyncDNSResolver 测试"""
    
    @pytest.mark.asyncio
    async def test_resolve(self):
        """测试 DNS 解析"""
        resolver = AsyncDNSResolver()
        
        # 测试解析 Google DNS
        ips = await resolver.resolve("dns.google.com", "A")
        assert len(ips) > 0
        assert "8.8.8.8" in ips or "8.8.4.4" in ips
    
    @pytest.mark.asyncio
    async def test_cache(self):
        """测试 DNS 缓存"""
        from core.async_engine import AsyncCache
        
        cache = AsyncCache(ttl=300)
        resolver = AsyncDNSResolver(cache=cache)
        
        # 第一次解析
        ips1 = await resolver.resolve("dns.google.com", "A")
        
        # 第二次解析应该使用缓存
        ips2 = await resolver.resolve("dns.google.com", "A")
        
        assert ips1 == ips2
    
    @pytest.mark.asyncio
    async def test_nonexistent_domain(self):
        """测试不存在的域名"""
        resolver = AsyncDNSResolver()
        
        # 不存在的域名应该返回空列表
        ips = await resolver.resolve("nonexistent-domain-12345.com", "A")
        assert ips == []


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
