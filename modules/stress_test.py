#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 网站压力测试模块（深度优化版）
高并发测试、抗压等级评估、性能瓶颈分析

优化要点：
- 内存管理：限制结果列表大小，防止内存泄漏
- 资源管理：确保 aiohttp session 正确关闭
- 并发控制：信号量控制，任务取消优化
- 错误处理：健壮的异常处理和重试机制
- 性能优化：批量更新指标，使用 deque
"""

import asyncio
import time
import statistics
import json
import random
import ssl
import weakref
from collections import deque
from typing import Dict, List, Optional, Any, Callable, AsyncContextManager
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from contextlib import asynccontextmanager
import aiohttp
import logging

# 配置日志
logger = logging.getLogger(__name__)


# ============ 常量配置 ============

# 最大保留结果数（防止内存泄漏）
MAX_RESULTS_COUNT = 10000
MAX_RESPONSE_TIMES_COUNT = 50000

# 默认配置
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_CONCURRENT = 200
DEFAULT_CONNECTOR_LIMIT = 1000

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 0.1


class StressLevel(Enum):
    """抗压等级"""
    EXCELLENT = "优秀"      # > 1000 QPS, 响应时间 < 100ms
    GOOD = "良好"           # 500-1000 QPS, 响应时间 < 200ms
    NORMAL = "一般"         # 100-500 QPS, 响应时间 < 500ms
    POOR = "较差"           # 50-100 QPS, 响应时间 < 1000ms
    CRITICAL = "危险"       # < 50 QPS, 响应时间 > 1000ms


@dataclass
class RequestResult:
    """单次请求结果（轻量级）"""
    status_code: int
    response_time: float  # ms
    success: bool
    error: str = ""
    size: int = 0  # bytes


@dataclass
class TestMetrics:
    """测试指标（线程安全计数器）"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0
    total_bytes: int = 0
    
    # 响应时间统计（使用固定大小队列）
    min_response_time: float = float('inf')
    max_response_time: float = 0
    
    # 错误统计
    status_codes: Dict[int, int] = field(default_factory=dict)
    error_types: Dict[str, int] = field(default_factory=dict)
    
    # 计算值
    avg_response_time: float = 0
    p50_response_time: float = 0
    p90_response_time: float = 0
    p95_response_time: float = 0
    p99_response_time: float = 0
    qps: float = 0
    throughput_mbps: float = 0
    error_rate: float = 0
    stress_level: str = ""
    concurrent_users: int = 0
    
    def update_from_result(self, result: RequestResult):
        """原子更新（线程安全）"""
        self.total_requests += 1
        
        if result.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            error_key = result.error if result.error else str(result.status_code)
            self.error_types[error_key] = self.error_types.get(error_key, 0) + 1
        
        self.status_codes[result.status_code] = self.status_codes.get(result.status_code, 0) + 1
        
        if result.response_time > 0:
            self.min_response_time = min(self.min_response_time, result.response_time)
            self.max_response_time = max(self.max_response_time, result.response_time)
        
        self.total_bytes += result.size
    
    def calculate_final(self, response_times: List[float], total_time: float):
        """计算最终指标"""
        self.total_time = total_time
        
        if total_time > 0:
            self.qps = self.total_requests / total_time
            self.throughput_mbps = (self.total_bytes / 1024 / 1024) / total_time
        
        if self.total_requests > 0:
            self.error_rate = self.failed_requests / self.total_requests * 100
        
        if response_times:
            self.avg_response_time = statistics.mean(response_times)
            sorted_times = sorted(response_times)
            n = len(sorted_times)
            
            self.p50_response_time = sorted_times[int(n * 0.50)]
            self.p90_response_time = sorted_times[int(n * 0.90)]
            self.p95_response_time = sorted_times[int(n * 0.95)]
            self.p99_response_time = sorted_times[int(n * 0.99)]
        
        self.stress_level = self._calculate_stress_level()
    
    def _calculate_stress_level(self) -> str:
        """计算抗压等级"""
        if self.error_rate > 50 or self.avg_response_time > 1000:
            return StressLevel.CRITICAL.value
        
        score = 0
        
        # QPS 评分
        if self.qps >= 1000:
            score += 40
        elif self.qps >= 500:
            score += 30
        elif self.qps >= 100:
            score += 20
        elif self.qps >= 50:
            score += 10
        
        # 响应时间评分
        if self.avg_response_time <= 100:
            score += 30
        elif self.avg_response_time <= 200:
            score += 25
        elif self.avg_response_time <= 500:
            score += 15
        elif self.avg_response_time <= 1000:
            score += 5
        
        # 错误率评分
        if self.error_rate <= 0.1:
            score += 30
        elif self.error_rate <= 1:
            score += 25
        elif self.error_rate <= 5:
            score += 15
        elif self.error_rate <= 10:
            score += 5
        
        if score >= 80:
            return StressLevel.EXCELLENT.value
        elif score >= 60:
            return StressLevel.GOOD.value
        elif score >= 40:
            return StressLevel.NORMAL.value
        elif score >= 20:
            return StressLevel.POOR.value
        else:
            return StressLevel.CRITICAL.value
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_time": round(self.total_time, 2),
            "total_bytes": self.total_bytes,
            "response_time": {
                "min": round(self.min_response_time, 2) if self.min_response_time != float('inf') else 0,
                "max": round(self.max_response_time, 2),
                "avg": round(self.avg_response_time, 2),
                "p50": round(self.p50_response_time, 2),
                "p90": round(self.p90_response_time, 2),
                "p95": round(self.p95_response_time, 2),
                "p99": round(self.p99_response_time, 2),
            },
            "throughput": {
                "qps": round(self.qps, 2),
                "throughput_mbps": round(self.throughput_mbps, 2),
            },
            "errors": {
                "error_rate": round(self.error_rate, 2),
                "status_codes": dict(self.status_codes),
                "error_types": dict(self.error_types),
            },
            "stress_level": self.stress_level,
            "concurrent_users": self.concurrent_users,
        }


@dataclass
class StressTestConfig:
    """压力测试配置"""
    target_url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    body: Optional[str] = None
    
    concurrent_users: int = 10
    max_concurrent: int = 200
    ramp_up_time: int = 5
    duration: int = 10
    
    timeout: int = DEFAULT_TIMEOUT
    think_time: float = 0
    think_time_random: float = 0
    
    test_mode: str = "concurrent"
    target_qps: int = 0
    spike_duration: int = 10
    spike_multiplier: float = 3.0
    
    verify_ssl: bool = False
    follow_redirects: bool = True
    max_redirects: int = 5
    
    stop_on_error: bool = False
    max_error_rate: float = 50.0
    max_response_time: float = 30000
    
    # 重试配置
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY


class StressTester:
    """网站压力测试器（深度优化版）"""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        
        # 使用固定大小的 deque 防止内存泄漏
        self.response_times: deque = deque(maxlen=MAX_RESPONSE_TIMES_COUNT)
        
        # 指标（线程安全）
        self.metrics = TestMetrics()
        
        # 控制标志
        self._running = False
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        
        # 活跃任务追踪
        self._active_tasks: weakref.WeakSet = weakref.WeakSet()
        
        # 回调
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        
        # Session（每个测试实例独立）
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _make_request(
        self, 
        session: aiohttp.ClientSession,
        retry_count: int = 0
    ) -> RequestResult:
        """发起单个请求（带重试）"""
        start = time.perf_counter()
        
        try:
            async with session.request(
                method=self.config.method,
                url=self.config.target_url,
                data=self.config.body,
                allow_redirects=self.config.follow_redirects,
                max_redirects=self.config.max_redirects,
                ssl=self.config.verify_ssl
            ) as response:
                try:
                    body = await asyncio.wait_for(
                        response.read(),
                        timeout=self.config.timeout
                    )
                except asyncio.TimeoutError:
                    body = b''
                
                elapsed = (time.perf_counter() - start) * 1000
                
                return RequestResult(
                    status_code=response.status,
                    response_time=elapsed,
                    success=200 <= response.status < 400,
                    size=len(body)
                )
        
        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            return RequestResult(
                status_code=0,
                response_time=elapsed,
                success=False,
                error="Timeout"
            )
        
        except aiohttp.ClientError as e:
            elapsed = (time.perf_counter() - start) * 1000
            error_msg = type(e).__name__
            
            # 重试逻辑
            if retry_count < self.config.max_retries and "Timeout" not in error_msg:
                await asyncio.sleep(self.config.retry_delay)
                return await self._make_request(session, retry_count + 1)
            
            return RequestResult(
                status_code=0,
                response_time=elapsed,
                success=False,
                error=error_msg
            )
        
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return RequestResult(
                status_code=0,
                response_time=elapsed,
                success=False,
                error=type(e).__name__[:50]
            )
    
    async def _worker(self, session: aiohttp.ClientSession, worker_id: int, semaphore: asyncio.Semaphore):
        """工作协程"""
        while self._running:
            async with semaphore:
                if not self._running:
                    break
                
                # 思考时间
                if self.config.think_time > 0:
                    think = self.config.think_time
                    if self.config.think_time_random > 0:
                        think += random.uniform(0, self.config.think_time_random)
                    await asyncio.sleep(think)
                
                # 发起请求
                result = await self._make_request(session)
                
                # 原子更新指标
                self.metrics.update_from_result(result)
                self.response_times.append(result.response_time)
                
                # 检查停止条件
                if self.config.stop_on_error and not result.success:
                    self._running = False
                    break
                
                if self.metrics.error_rate > self.config.max_error_rate:
                    self._running = False
                    break
    
    async def _run_concurrent_test(self, session: aiohttp.ClientSession):
        """并发测试"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        # 爬坡阶段
        step_interval = self.config.ramp_up_time / 10 if self.config.ramp_up_time > 0 else 0
        users_per_step = max(1, self.config.concurrent_users // 10) if step_interval > 0 else self.config.concurrent_users
        
        workers = []
        
        for step in range(10):
            if not self._running:
                break
            
            # 添加这一步的用户
            for _ in range(users_per_step):
                if len(workers) >= self.config.concurrent_users:
                    break
                
                task = asyncio.create_task(
                    self._worker(session, len(workers), semaphore)
                )
                self._active_tasks.add(task)
                workers.append(task)
            
            self.metrics.concurrent_users = len(workers)
            
            if self.on_progress:
                await self.on_progress("ramp_up", len(workers), self.config.concurrent_users)
            
            if step_interval > 0:
                await asyncio.sleep(step_interval)
        
        # 持续阶段
        elapsed = 0
        check_interval = 0.5
        
        while elapsed < self.config.duration and self._running:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if self.on_progress and int(elapsed) != int(elapsed - check_interval):
                await self.on_progress("sustained", elapsed, self.config.duration)
        
        # 停止所有工作协程
        self._running = False
        
        # 等待任务完成（带超时）
        if workers:
            done, pending = await asyncio.wait(
                workers,
                timeout=5.0,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # 取消未完成的任务
            for task in pending:
                task.cancel()
            
            # 等待取消完成
            if pending:
                await asyncio.wait(pending, timeout=2.0)
    
    async def _run_throughput_test(self, session: aiohttp.ClientSession):
        """吞吐量测试"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        start_time = time.perf_counter()
        last_report_time = start_time
        
        while self._running:
            elapsed = time.perf_counter() - start_time
            
            if elapsed >= self.config.duration:
                break
            
            # 批量发起请求
            batch_size = min(self.config.target_qps, self.config.max_concurrent)
            
            async def limited_request():
                async with semaphore:
                    if self._running:
                        result = await self._make_request(session)
                        self.metrics.update_from_result(result)
                        self.response_times.append(result.response_time)
            
            tasks = [asyncio.create_task(limited_request()) for _ in range(batch_size)]
            
            # 等待这一批完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 速率控制
            batch_time = time.perf_counter() - start_time - elapsed
            sleep_time = 1.0 - batch_time
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            
            # 定期报告进度
            if time.perf_counter() - last_report_time >= 1.0:
                if self.on_progress:
                    await self.on_progress("throughput", elapsed, self.config.duration)
                last_report_time = time.perf_counter()
        
        self._running = False
    
    async def run(self) -> TestMetrics:
        """运行压力测试"""
        self._running = True
        self._start_time = time.perf_counter()
        
        # 重置指标
        self.metrics = TestMetrics()
        self.response_times.clear()
        
        try:
            # 创建 session
            ssl_context = None
            if not self.config.verify_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(
                limit=DEFAULT_CONNECTOR_LIMIT,
                limit_per_host=self.config.max_concurrent,
                ttl_dns_cache=300,
                ssl=ssl_context
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers=self.config.headers
            )
            
            try:
                # 运行测试
                if self.config.test_mode == "throughput":
                    await self._run_throughput_test(self._session)
                else:
                    await self._run_concurrent_test(self._session)
            
            finally:
                # 确保 session 关闭
                if self._session and not self._session.closed:
                    await self._session.close()
                    self._session = None
        
        except Exception as e:
            logger.error(f"压力测试异常: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self._running = False
            self._end_time = time.perf_counter()
            
            # 计算最终指标
            self.metrics.calculate_final(
                list(self.response_times),
                self._end_time - self._start_time
            )
            
            # 回调
            if self.on_complete:
                try:
                    await self.on_complete(self.metrics)
                except Exception as e:
                    logger.error(f"回调异常: {e}")
        
        return self.metrics
    
    def stop(self):
        """停止测试"""
        self._running = False
    
    def get_results(self) -> Dict:
        """获取测试结果"""
        return {
            "config": {
                "target_url": self.config.target_url,
                "test_mode": self.config.test_mode,
                "concurrent_users": self.config.concurrent_users,
                "duration": self.config.duration,
            },
            "metrics": self.metrics.to_dict(),
        }


class QuickStressTest:
    """快速压力测试 - 简化接口"""
    
    @staticmethod
    async def test_url(
        url: str,
        concurrent: int = 10,
        duration: int = 10,
        timeout: int = 30
    ) -> Dict:
        """快速测试 URL"""
        config = StressTestConfig(
            target_url=url,
            concurrent_users=concurrent,
            duration=duration,
            timeout=timeout
        )
        
        tester = StressTester(config)
        await tester.run()
        
        return tester.get_results()
    
    @staticmethod
    async def benchmark(url: str, max_concurrent: int = 100) -> Dict:
        """性能基准测试"""
        results = []
        
        for concurrent in [1, 5, 10, 20, 50, 100]:
            if concurrent > max_concurrent:
                break
            
            config = StressTestConfig(
                target_url=url,
                concurrent_users=concurrent,
                duration=10
            )
            
            tester = StressTester(config)
            metrics = await tester.run()
            
            results.append({
                "concurrent": concurrent,
                "qps": metrics.qps,
                "avg_response_time": metrics.avg_response_time,
                "error_rate": metrics.error_rate,
                "stress_level": metrics.stress_level
            })
            
            # 如果错误率超过 20%，停止
            if metrics.error_rate > 20:
                break
            
            # 如果响应时间超过 5 秒，停止
            if metrics.avg_response_time > 5000:
                break
        
        # 找到最佳并发数
        valid_results = [r for r in results if r["error_rate"] < 10]
        best = max(valid_results, key=lambda x: x["qps"]) if valid_results else results[-1]
        
        return {
            "url": url,
            "benchmark_results": results,
            "best_concurrent": best["concurrent"],
            "max_qps": best["qps"],
            "recommendation": f"建议并发数: {best['concurrent']}, 预期 QPS: {best['qps']:.0f}"
        }


# 导出
__all__ = [
    'StressTester',
    'StressTestConfig',
    'TestMetrics',
    'QuickStressTest',
    'StressLevel',
]
