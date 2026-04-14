#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.1 - 持久化缓存系统
支持 SQLite / Redis 后端，避免重复扫描
"""

import asyncio
import json
import time
import hashlib
import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    expire_at: float
    ttl: int
    size: int = 0


class BaseCache(ABC):
    """缓存基类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass
    
    @staticmethod
    def hash_key(key: str) -> str:
        """生成缓存键哈希"""
        return hashlib.md5(key.encode()).hexdigest()


class SQLiteCache(BaseCache):
    """
    SQLite 持久化缓存
    
    特点：
    - 数据持久化到文件
    - 支持过期清理
    - 线程安全
    - 零依赖
    """
    
    def __init__(self, db_path: str = "cache/autorecon.db", default_ttl: int = 86400):
        """
        初始化 SQLite 缓存
        
        Args:
            db_path: 数据库文件路径
            default_ttl: 默认过期时间（秒）
        """
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        
        # 创建目录
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expire_at REAL NOT NULL,
                    ttl INTEGER NOT NULL,
                    size INTEGER DEFAULT 0
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expire_at ON cache(expire_at)
            """)
            
            conn.commit()
    
    def _serialize(self, value: Any) -> str:
        """序列化值"""
        return json.dumps(value, ensure_ascii=False, default=str)
    
    def _deserialize(self, value: str) -> Any:
        """反序列化值"""
        try:
            return json.loads(value)
        except:
            return value
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        hkey = self.hash_key(key)
        
        def _get():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value, expire_at FROM cache WHERE key = ?",
                    (hkey,)
                )
                row = cursor.fetchone()
                
                if row:
                    value, expire_at = row
                    if time.time() < expire_at:
                        return self._deserialize(value)
                    else:
                        # 过期，删除
                        conn.execute("DELETE FROM cache WHERE key = ?", (hkey,))
                        conn.commit()
                
                return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存"""
        hkey = self.hash_key(key)
        ttl = ttl or self.default_ttl
        now = time.time()
        expire_at = now + ttl
        serialized = self._serialize(value)
        size = len(serialized.encode())
        
        def _set():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache (key, value, created_at, expire_at, ttl, size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (hkey, serialized, now, expire_at, ttl, size))
                conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _set)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        hkey = self.hash_key(key)
        
        def _delete():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (hkey,))
                conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _delete)
    
    async def clear(self) -> bool:
        """清空缓存"""
        def _clear():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache")
                conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _clear)
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        value = await self.get(key)
        return value is not None
    
    async def cleanup_expired(self) -> int:
        """清理过期缓存"""
        def _cleanup():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE expire_at < ?",
                    (time.time(),)
                )
                conn.commit()
                return cursor.rowcount
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _cleanup)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        def _stats():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(size) as total_size,
                        AVG(ttl) as avg_ttl
                    FROM cache
                    WHERE expire_at > ?
                """, (time.time(),))
                
                row = cursor.fetchone()
                
                return {
                    "total_entries": row[0] or 0,
                    "total_size_bytes": row[1] or 0,
                    "total_size_mb": round((row[1] or 0) / 1024 / 1024, 2),
                    "avg_ttl": round(row[2] or 0, 0),
                }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _stats)


class RedisCache(BaseCache):
    """
    Redis 缓存（可选）
    
    需要安装: pip install redis
    """
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        db: int = 0,
        password: str = None,
        default_ttl: int = 86400,
        prefix: str = "autorecon:"
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self.prefix = prefix
        self._client = None
    
    def _get_client(self):
        """获取 Redis 客户端"""
        if self._client is None:
            try:
                import redis
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True
                )
            except ImportError:
                raise ImportError("请安装 redis: pip install redis")
        
        return self._client
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            client = self._get_client()
            hkey = self.prefix + self.hash_key(key)
            value = client.get(hkey)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"[!] Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存"""
        try:
            client = self._get_client()
            hkey = self.prefix + self.hash_key(key)
            ttl = ttl or self.default_ttl
            
            return client.setex(
                hkey, 
                ttl, 
                json.dumps(value, ensure_ascii=False, default=str)
            )
        except Exception as e:
            print(f"[!] Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            client = self._get_client()
            hkey = self.prefix + self.hash_key(key)
            return client.delete(hkey) > 0
        except Exception as e:
            return False
    
    async def clear(self) -> bool:
        """清空缓存（仅清除前缀匹配的键）"""
        try:
            client = self._get_client()
            keys = client.keys(self.prefix + "*")
            if keys:
                return client.delete(*keys) > 0
            return True
        except Exception as e:
            return False
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        try:
            client = self._get_client()
            hkey = self.prefix + self.hash_key(key)
            return client.exists(hkey) > 0
        except:
            return False


class HybridCache(BaseCache):
    """
    混合缓存
    
    L1: 内存缓存（快，容量小）
    L2: 持久化缓存（慢，容量大）
    """
    
    def __init__(
        self, 
        memory_size: int = 1000,
        persistent_path: str = "cache/autorecon.db",
        default_ttl: int = 86400
    ):
        self.memory_cache: Dict[str, tuple] = {}  # key -> (value, expire_at)
        self.memory_size = memory_size
        self.persistent = SQLiteCache(persistent_path, default_ttl)
        self.default_ttl = default_ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存（先查内存，再查持久化）"""
        hkey = self.hash_key(key)
        
        # L1: 内存
        if hkey in self.memory_cache:
            value, expire_at = self.memory_cache[hkey]
            if time.time() < expire_at:
                return value
            else:
                del self.memory_cache[hkey]
        
        # L2: 持久化
        value = await self.persistent.get(key)
        
        if value is not None:
            # 回填 L1
            self.memory_cache[hkey] = (value, time.time() + 300)  # 5分钟
        
        return value
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存（写入两级）"""
        hkey = self.hash_key(key)
        ttl = ttl or self.default_ttl
        expire_at = time.time() + ttl
        
        # L1: 内存
        if len(self.memory_cache) >= self.memory_size:
            # 简单 LRU：清理过期
            now = time.time()
            expired = [k for k, (v, e) in self.memory_cache.items() if e < now]
            for k in expired:
                del self.memory_cache[k]
        
        self.memory_cache[hkey] = (value, expire_at)
        
        # L2: 持久化
        return await self.persistent.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        hkey = self.hash_key(key)
        
        if hkey in self.memory_cache:
            del self.memory_cache[hkey]
        
        return await self.persistent.delete(key)
    
    async def clear(self) -> bool:
        """清空缓存"""
        self.memory_cache.clear()
        return await self.persistent.clear()
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        value = await self.get(key)
        return value is not None


# ============== 使用示例 ==============

async def example_usage():
    """示例：缓存使用"""
    
    # SQLite 缓存
    cache = SQLiteCache("cache/test.db", default_ttl=3600)
    
    # 设置
    await cache.set("subdomain:example.com", ["www", "api", "mail"])
    
    # 获取
    subdomains = await cache.get("subdomain:example.com")
    print(f"子域名: {subdomains}")
    
    # 统计
    stats = await cache.get_stats()
    print(f"缓存统计: {stats}")
    
    # 清理过期
    expired = await cache.cleanup_expired()
    print(f"清理过期: {expired}")


if __name__ == "__main__":
    asyncio.run(example_usage())
