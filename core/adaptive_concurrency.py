#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.1 - 自适应并发控制
根据目标响应动态调整并发数，优化扫描效率
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import threading


class ConcurrencyState(Enum):
    """并发状态"""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    PAUSED = "paused"


@dataclass
class RequestMetrics:
    """请求指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    error_rate: float = 0.0
    qps: float = 0.0


@dataclass
class ConcurrencyConfig:
    """并发配置"""
    initial: int = 50
    min_concurrency: int = 10
    max_concurrency: int = 500
    increase_threshold: float = 0.5    # 响应时间 < 0.5s 时增加
    decrease_threshold: float = 1.0    # 响应时间 > 1.0s 时减少
    error_threshold: float = 0.1       # 错误率 > 10% 时减少
    increase_factor: float = 1.2       # 增加倍数
    decrease_factor: float = 0.8       # 减少倍数
    adjustment_interval: float = 5.0   # 调整间隔（秒）
    warmup_requests: int = 100         # 预热请求数
    cooldown_time: float = 2.0         # 错误后冷却时间


class AdaptiveConcurrency:
    """
    自适应并发控制器
    
    功能：
    - 根据响应时间动态调整并发数
    - 错误率过高时自动降速
    - 支持 QPS 统计
    - 线程安全
    """
    
    def __init__(self, config: ConcurrencyConfig = None):
        """
        初始化控制器
        
        Args:
            config: 并发配置
        """
        self.config = config or ConcurrencyConfig()
        
        # 当前并发数
        self._concurrency = self.config.initial
        self._state = ConcurrencyState.STABLE
        
        # 指标统计
        self._metrics = RequestMetrics()
        self._recent_times: List[float] = []
        self._recent_errors: List[bool] = []
        
        # 时间戳
        self._start_time: Optional[float] = None
        self._last_adjustment: Optional[float] = None
        
        # 锁
        self._lock = threading.Lock()
        
        # 暂停标志
        self._paused = False
        self._pause_until: Optional[float] = None
    
    @property
    def concurrency(self) -> int:
        """当前并发数"""
        return self._concurrency
    
    @property
    def state(self) -> ConcurrencyState:
        """当前状态"""
        return self._state
    
    @property
    def metrics(self) -> RequestMetrics:
        """获取指标副本"""
        with self._lock:
            return RequestMetrics(
                total_requests=self._metrics.total_requests,
                successful_requests=self._metrics.successful_requests,
                failed_requests=self._metrics.failed_requests,
                total_time=self._metrics.total_time,
                avg_response_time=self._metrics.avg_response_time,
                min_response_time=self._metrics.min_response_time,
                max_response_time=self._metrics.max_response_time,
                error_rate=self._metrics.error_rate,
                qps=self._metrics.qps,
            )
    
    def start(self):
        """开始计时"""
        self._start_time = time.time()
        self._last_adjustment = self._start_time
    
    def record_request(self, response_time: float, success: bool = True):
        """
        记录请求结果
        
        Args:
            response_time: 响应时间（秒）
            success: 是否成功
        """
        with self._lock:
            # 更新基础统计
            self._metrics.total_requests += 1
            self._metrics.total_time += response_time
            
            if success:
                self._metrics.successful_requests += 1
            else:
                self._metrics.failed_requests += 1
            
            # 更新响应时间统计
            self._recent_times.append(response_time)
            if len(self._recent_times) > 100:  # 保留最近100个
                self._recent_times.pop(0)
            
            self._metrics.avg_response_time = sum(self._recent_times) / len(self._recent_times)
            self._metrics.min_response_time = min(self._metrics.min_response_time, response_time)
            self._metrics.max_response_time = max(self._metrics.max_response_time, response_time)
            
            # 更新错误率
            self._recent_errors.append(not success)
            if len(self._recent_errors) > 100:
                self._recent_errors.pop(0)
            
            if self._recent_errors:
                self._metrics.error_rate = sum(self._recent_errors) / len(self._recent_errors)
            
            # 更新 QPS
            if self._start_time:
                elapsed = time.time() - self._start_time
                if elapsed > 0:
                    self._metrics.qps = self._metrics.total_requests / elapsed
    
    def should_adjust(self) -> bool:
        """是否应该调整并发数"""
        if self._paused:
            # 检查是否恢复
            if self._pause_until and time.time() > self._pause_until:
                self._paused = False
                self._pause_until = None
                self._state = ConcurrencyState.STABLE
                return False
            return False
        
        if not self._last_adjustment:
            return False
        
        # 预热阶段不调整
        if self._metrics.total_requests < self.config.warmup_requests:
            return False
        
        # 检查间隔
        elapsed = time.time() - self._last_adjustment
        return elapsed >= self.config.adjustment_interval
    
    def adjust(self) -> int:
        """
        调整并发数
        
        Returns:
            int: 新的并发数
        """
        with self._lock:
            if not self.should_adjust():
                return self._concurrency
            
            self._last_adjustment = time.time()
            
            # 错误率过高 - 暂停或降速
            if self._metrics.error_rate > self.config.error_threshold:
                self._handle_high_error_rate()
                return self._concurrency
            
            # 根据响应时间调整
            avg_time = self._metrics.avg_response_time
            
            if avg_time < self.config.increase_threshold:
                # 响应快，增加并发
                self._increase()
            elif avg_time > self.config.decrease_threshold:
                # 响应慢，减少并发
                self._decrease()
            else:
                # 保持稳定
                self._state = ConcurrencyState.STABLE
            
            return self._concurrency
    
    def _increase(self):
        """增加并发"""
        new_concurrency = min(
            int(self._concurrency * self.config.increase_factor),
            self.config.max_concurrency
        )
        
        if new_concurrency > self._concurrency:
            self._concurrency = new_concurrency
            self._state = ConcurrencyState.INCREASING
    
    def _decrease(self):
        """减少并发"""
        new_concurrency = max(
            int(self._concurrency * self.config.decrease_factor),
            self.config.min_concurrency
        )
        
        if new_concurrency < self._concurrency:
            self._concurrency = new_concurrency
            self._state = ConcurrencyState.DECREASING
    
    def _handle_high_error_rate(self):
        """处理高错误率"""
        if self._metrics.error_rate > 0.3:  # 错误率 > 30%
            # 暂停
            self._paused = True
            self._pause_until = time.time() + self.config.cooldown_time
            self._state = ConcurrencyState.PAUSED
        else:
            # 大幅降速
            self._concurrency = max(
                int(self._concurrency * 0.5),
                self.config.min_concurrency
            )
            self._state = ConcurrencyState.DECREASING
    
    def pause(self, duration: float = None):
        """暂停"""
        self._paused = True
        if duration:
            self._pause_until = time.time() + duration
        self._state = ConcurrencyState.PAUSED
    
    def resume(self):
        """恢复"""
        self._paused = False
        self._pause_until = None
        self._state = ConcurrencyState.STABLE
    
    def reset(self):
        """重置"""
        with self._lock:
            self._concurrency = self.config.initial
            self._state = ConcurrencyState.STABLE
            self._metrics = RequestMetrics()
            self._recent_times.clear()
            self._recent_errors.clear()
            self._start_time = None
            self._last_adjustment = None
            self._paused = False
            self._pause_until = None
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        m = self.metrics
        return {
            "concurrency": self._concurrency,
            "state": self._state.value,
            "paused": self._paused,
            "metrics": {
                "total_requests": m.total_requests,
                "successful": m.successful_requests,
                "failed": m.failed_requests,
                "avg_response_time": f"{m.avg_response_time:.3f}s",
                "error_rate": f"{m.error_rate * 100:.1f}%",
                "qps": f"{m.qps:.1f}",
            },
        }


class AdaptiveSemaphore:
    """
    自适应信号量
    
    配合 AdaptiveConcurrency 使用，支持动态调整并发数
    """
    
    def __init__(self, controller: AdaptiveConcurrency):
        """
        初始化信号量
        
        Args:
            controller: 并发控制器
        """
        self.controller = controller
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    async def __aenter__(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.controller.concurrency)
        
        # 动态调整
        self._adjust_semaphore()
        
        await self._semaphore.acquire()
        return self
    
    async def __aexit__(self, *args):
        if self._semaphore:
            self._semaphore.release()
    
    def _adjust_semaphore(self):
        """调整信号量"""
        target = self.controller.concurrency
        current = self._semaphore._value if self._semaphore else 0
        
        # 需要增加
        if target > current:
            for _ in range(target - current):
                self._semaphore.release()
        
        # 需要减少（通过 acquire 实现，不立即生效）
        # 这里简化处理，信号量会在使用中逐渐调整


# ============== 使用示例 ==============

async def example_usage():
    """示例：自适应并发"""
    
    import aiohttp
    
    # 创建控制器
    config = ConcurrencyConfig(
        initial=50,
        min_concurrency=10,
        max_concurrency=200,
    )
    controller = AdaptiveConcurrency(config)
    controller.start()
    
    # 创建自适应信号量
    semaphore = AdaptiveSemaphore(controller)
    
    # 模拟请求
    async def fetch(url: str, session: aiohttp.ClientSession):
        start = time.time()
        
        async with semaphore:
            try:
                async with session.get(url, timeout=10) as resp:
                    elapsed = time.time() - start
                    success = resp.status < 400
                    
                    # 记录结果
                    controller.record_request(elapsed, success)
                    
                    # 调整并发
                    controller.adjust()
                    
                    return {"url": url, "status": resp.status, "time": elapsed}
            
            except Exception as e:
                elapsed = time.time() - start
                controller.record_request(elapsed, False)
                return {"url": url, "error": str(e)}
    
    # 批量请求
    urls = [f"https://httpbin.org/delay/{i % 3}" for i in range(100)]
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        results = await asyncio.gather(*tasks)
    
    # 打印统计
    print("\n扫描统计:")
    status = controller.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(example_usage())
