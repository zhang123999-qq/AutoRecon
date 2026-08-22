#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 压力测试内存优化
使用水库采样和流式统计算法，实现 O(1) 内存的精确统计
"""

import random
import time
import math
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from threading import Lock


@dataclass
class ReservoirSampler:
    """水库采样器 - 固定内存维护流式数据的统计特性
    
    算法: Algorithm R (Knuth)
    时间复杂度: O(1) per sample
    空间复杂度: O(k) where k = reservoir size
    """
    
    max_size: int
    reservoir: List[float] = field(default_factory=list)
    count: int = 0
    _lock: Lock = field(default_factory=Lock)
    
    def add(self, value: float):
        """添加样本"""
        with self._lock:
            self.count += 1
            if len(self.reservoir) < self.max_size:
                # 填充阶段
                self.reservoir.append(value)
            else:
                # 替换阶段: 以 k/n 概率替换
                idx = random.randint(0, self.count - 1)
                if idx < self.max_size:
                    self.reservoir[idx] = value
    
    def add_batch(self, values: List[float]):
        """批量添加样本"""
        for v in values:
            self.add(v)
    
    def get_samples(self) -> List[float]:
        """获取采样副本"""
        with self._lock:
            return self.reservoir.copy()
    
    def get_percentiles(self, percentiles: List[float] = None) -> Dict[str, float]:
        """计算百分位数"""
        if percentiles is None:
            percentiles = [0.50, 0.90, 0.95, 0.99]
        
        with self._lock:
            if not self.reservoir:
                return {f"p{int(p*100)}": 0.0 for p in percentiles}
            
            sorted_samples = sorted(self.reservoir)
            n = len(sorted_samples)
            result = {}
            
            for p in percentiles:
                idx = min(int(n * p), n - 1)
                result[f"p{int(p*100)}"] = sorted_samples[idx]
            
            return result
    
    def get_basic_stats(self) -> Dict[str, float]:
        """获取基本统计量"""
        with self._lock:
            if not self.reservoir:
                return {"min": 0, "max": 0, "mean": 0, "count": 0}
            
            return {
                "min": min(self.reservoir),
                "max": max(self.reservoir),
                "mean": statistics.mean(self.reservoir),
                "count": self.count,
                "sample_size": len(self.reservoir),
            }
    
    def clear(self):
        """清空采样器"""
        with self._lock:
            self.reservoir.clear()
            self.count = 0


@dataclass
class StreamingStats:
    """流式统计计算器 - Welford 算法
    
    在线计算均值、方差、标准差，无需存储所有数据
    数值稳定，适合大规模流式数据
    
    References:
        - Welford, B. P. (1962). "Note on a method for calculating corrected sums of squares and products"
        - Knuth, D. E. (1998). "The Art of Computer Programming, Volume 2"
    """
    
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0  # Sum of squares of differences from the mean
    min_val: float = float('inf')
    max_val: float = float('-inf')
    sum_val: float = 0.0
    _lock: Lock = field(default_factory=Lock)
    
    def update(self, value: float):
        """更新统计量 (Welford 算法)"""
        with self._lock:
            self.count += 1
            self.sum_val += value
            
            # 更新最小/最大值
            if value < self.min_val:
                self.min_val = value
            if value > self.max_val:
                self.max_val = value
            
            # Welford 算法更新均值和方差
            delta = value - self.mean
            self.mean += delta / self.count
            delta2 = value - self.mean
            self.m2 += delta * delta2
    
    def update_batch(self, values: List[float]):
        """批量更新"""
        for v in values:
            self.update(v)
    
    @property
    def variance(self) -> float:
        """样本方差"""
        with self._lock:
            if self.count < 2:
                return 0.0
            return self.m2 / (self.count - 1)
    
    @property
    def std_dev(self) -> float:
        """标准差"""
        return math.sqrt(self.variance)
    
    @property
    def std_error(self) -> float:
        """标准误"""
        with self._lock:
            if self.count == 0:
                return 0.0
            return self.std_dev / math.sqrt(self.count)
    
    def get_percentiles_approx(self, percentiles: List[float] = None) -> Dict[str, float]:
        """基于正态分布近似的百分位数
        
        适用于大样本 (count > 30)，利用均值和标准差估算
        """
        if percentiles is None:
            percentiles = [0.50, 0.90, 0.95, 0.99]
        
        with self._lock:
            if self.count < 30:
                return {f"p{int(p*100)}": 0.0 for p in percentiles}
            
            # 正态分布 Z-scores
            z_scores = {
                0.50: 0.0,
                0.75: 0.674,
                0.90: 1.282,
                0.95: 1.645,
                0.975: 1.960,
                0.99: 2.326,
                0.999: 3.090,
            }
            
            result = {}
            for p in percentiles:
                z = z_scores.get(p, 0.0)
                result[f"p{int(p*100)}"] = self.mean + z * self.std_dev
            
            return result
    
    def get_confidence_interval(self, confidence: float = 0.95) -> tuple:
        """获取均值置信区间"""
        with self._lock:
            if self.count < 2:
                return (self.mean, self.mean)
            
            # t 分布临界值 (近似用正态分布)
            z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
            margin = z * self.std_error
            return (self.mean - margin, self.mean + margin)
    
    def merge(self, other: "StreamingStats"):
        """合并另一个 StreamingStats (用于分布式聚合)"""
        with self._lock:
            if other.count == 0:
                return
            if self.count == 0:
                self.count = other.count
                self.mean = other.mean
                self.m2 = other.m2
                self.min_val = other.min_val
                self.max_val = other.max_val
                self.sum_val = other.sum_val
                return
            
            # Chan 等人 (1979) 并行方差算法
            delta = other.mean - self.mean
            new_count = self.count + other.count
            
            self.mean = (self.count * self.mean + other.count * other.mean) / new_count
            self.m2 = self.m2 + other.m2 + delta * delta * self.count * other.count / new_count
            self.min_val = min(self.min_val, other.min_val)
            self.max_val = max(self.max_val, other.max_val)
            self.sum_val += other.sum_val
            self.count = new_count
    
    def get_summary(self) -> Dict[str, Any]:
        """获取完整统计摘要"""
        with self._lock:
            return {
                "count": self.count,
                "sum": self.sum_val,
                "min": self.min_val if self.min_val != float('inf') else 0,
                "max": self.max_val if self.max_val != float('-inf') else 0,
                "mean": self.mean,
                "variance": self.variance,
                "std_dev": self.std_dev,
                "std_error": self.std_error,
                "ci_95": self.get_confidence_interval(0.95),
                "percentiles": self.get_percentiles_approx(),
            }
    
    def clear(self):
        """重置统计量"""
        with self._lock:
            self.count = 0
            self.mean = 0.0
            self.m2 = 0.0
            self.min_val = float('inf')
            self.max_val = float('-inf')
            self.sum_val = 0.0


@dataclass
class SlidingWindowStats:
    """滑动窗口统计 - 最近 N 个样本的统计"""
    
    window_size: int
    window: deque = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)
    
    def add(self, value: float):
        with self._lock:
            self.window.append(value)
            if len(self.window) > self.window_size:
                self.window.popleft()
    
    def get_stats(self) -> Dict[str, float]:
        with self._lock:
            if not self.window:
                return {"count": 0, "mean": 0, "min": 0, "max": 0}
            
            return {
                "count": len(self.window),
                "mean": statistics.mean(self.window),
                "min": min(self.window),
                "max": max(self.window),
                "stdev": statistics.stdev(self.window) if len(self.window) > 1 else 0,
            }
    
    def clear(self):
        with self._lock:
            self.window.clear()


@dataclass
class HistogramBuckets:
    """直方图桶 - 用于延迟分布分析"""
    
    # 默认桶边界 (毫秒)
    boundaries: List[float] = field(default_factory=lambda: [
        1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, float('inf')
    ])
    counts: List[int] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)
    
    def __post_init__(self):
        self.counts = [0] * (len(self.boundaries) + 1)
    
    def add(self, value: float):
        """添加观测值到对应桶"""
        with self._lock:
            for i, boundary in enumerate(self.boundaries):
                if value <= boundary:
                    self.counts[i] += 1
                    return
            # 超过最大边界
            self.counts[-1] += 1
    
    def get_percentile(self, p: float) -> float:
        """估算百分位数"""
        with self._lock:
            total = sum(self.counts)
            if total == 0:
                return 0.0
            
            target = total * p
            cumulative = 0
            
            for i, count in enumerate(self.counts):
                cumulative += count
                if cumulative >= target:
                    if i == 0:
                        return self.boundaries[0] * 0.5
                    elif i >= len(self.boundaries):
                        return self.boundaries[-1] * 1.5
                    else:
                        # 线性插值
                        prev_boundary = self.boundaries[i - 1] if i > 0 else 0
                        return prev_boundary + (self.boundaries[i] - prev_boundary) * \
                               (target - (cumulative - count)) / count
            
            return self.boundaries[-1]
    
    def get_distribution(self) -> List[Dict[str, Any]]:
        """获取分布详情"""
        with self._lock:
            total = sum(self.counts)
            if total == 0:
                return []
            
            result = []
            cumulative = 0
            for i, (count, boundary) in enumerate(zip(self.counts, self.boundaries)):
                cumulative += count
                result.append({
                    "bucket_upper": boundary,
                    "count": count,
                    "percentage": count / total * 100,
                    "cumulative_percentage": cumulative / total * 100,
                })
            
            # 最后一个桶
            if self.counts[-1] > 0:
                cumulative += self.counts[-1]
                result.append({
                    "bucket_upper": float('inf'),
                    "count": self.counts[-1],
                    "percentage": self.counts[-1] / total * 100,
                    "cumulative_percentage": cumulative / total * 100,
                })
            
            return result
    
    def clear(self):
        with self._lock:
            self.counts = [0] * len(self.counts)


class StressTestMetrics:
    """压力测试指标聚合器 - 组合多种统计器"""
    
    def __init__(self, reservoir_size: int = 10000, sliding_window: int = 1000):
        self.reservoir = ReservoirSampler(max_size=reservoir_size)
        self.streaming = StreamingStats()
        self.sliding = SlidingWindowStats(window_size=sliding_window)
        self.histogram = HistogramBuckets()
        
        # 计数器
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_bytes = 0
        self.status_codes: Dict[int, int] = {}
        self.error_types: Dict[str, int] = {}
        
        # 时间
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        self._lock = Lock()
    
    def record_request(
        self, 
        response_time: float, 
        success: bool, 
        status_code: int = 0, 
        error: str = "", 
        size: int = 0
    ):
        """记录单次请求结果"""
        with self._lock:
            self.total_requests += 1
            self.total_bytes += size
            
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                if error:
                    self.error_types[error] = self.error_types.get(error, 0) + 1
                else:
                    self.error_types[f"HTTP_{status_code}"] = self.error_types.get(f"HTTP_{status_code}", 0) + 1
            
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
            
            # 更新统计器
            if response_time > 0:
                self.reservoir.add(response_time)
                self.streaming.update(response_time)
                self.sliding.add(response_time)
                self.histogram.add(response_time)
    
    def start_timer(self):
        with self._lock:
            self.start_time = time.time()
    
    def stop_timer(self):
        with self._lock:
            self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        with self._lock:
            if self.start_time is None:
                return 0.0
            end = self.end_time or time.time()
            return end - self.start_time
    
    @property
    def qps(self) -> float:
        with self._lock:
            elapsed = self.elapsed
            if elapsed > 0:
                return self.total_requests / elapsed
            return 0.0
    
    @property
    def throughput_mbps(self) -> float:
        with self._lock:
            elapsed = self.elapsed
            if elapsed > 0:
                return (self.total_bytes / 1024 / 1024) / elapsed
            return 0.0
    
    @property
    def error_rate(self) -> float:
        with self._lock:
            if self.total_requests > 0:
                return self.failed_requests / self.total_requests * 100
            return 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """获取完整指标摘要"""
        with self._lock:
            # 响应时间统计
            rt_summary = self.streaming.get_summary()
            rt_summary.update(self.reservoir.get_percentiles())
            
            # 滑动窗口 (最近 1000 请求)
            sliding_stats = self.sliding.get_stats()
            
            # 直方图分布
            histogram_dist = self.histogram.get_distribution()
            
            return {
                "requests": {
                    "total": self.total_requests,
                    "successful": self.successful_requests,
                    "failed": self.failed_requests,
                },
                "time": {
                    "elapsed": round(self.elapsed, 2),
                    "qps": round(self.qps, 2),
                    "throughput_mbps": round(self.throughput_mbps, 2),
                },
                "response_time": {
                    "min": round(rt_summary.get("min", 0), 2),
                    "max": round(rt_summary.get("max", 0), 2),
                    "mean": round(rt_summary.get("mean", 0), 2),
                    "std_dev": round(rt_summary.get("std_dev", 0), 2),
                    "p50": round(rt_summary.get("p50", 0), 2),
                    "p90": round(rt_summary.get("p90", 0), 2),
                    "p95": round(rt_summary.get("p95", 0), 2),
                    "p99": round(rt_summary.get("p99", 0), 2),
                    "recent_mean": round(sliding_stats.get("mean", 0), 2),
                },
                "errors": {
                    "error_rate": round(self.error_rate, 2),
                    "status_codes": dict(self.status_codes),
                    "error_types": dict(self.error_types),
                },
                "histogram": histogram_dist,
            }
    
    def reset(self):
        with self._lock:
            self.reservoir.clear()
            self.streaming.clear()
            self.sliding.clear()
            self.histogram.clear()
            self.total_requests = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.total_bytes = 0
            self.status_codes.clear()
            self.error_types.clear()
            self.start_time = None
            self.end_time = None


# ============ 内存监控 ============

class MemoryMonitor:
    """内存监控 - 监控 Python 进程内存使用"""
    
    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self.samples: List[Dict] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = Lock()
    
    def start(self):
        """开始监控"""
        import psutil
        import os
        
        self._running = True
        self.samples.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> List[Dict]:
        """停止监控并返回样本"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._lock:
            return self.samples.copy()
    
    def _monitor_loop(self):
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        while self._running:
            try:
                mem_info = process.memory_info()
                self.samples.append({
                    "timestamp": time.time(),
                    "rss_mb": mem_info.rss / 1024 / 1024,
                    "vms_mb": mem_info.vms / 1024 / 1024,
                })
            except Exception:
                pass
            time.sleep(self.check_interval)
    
    def get_summary(self) -> Dict[str, float]:
        with self._lock:
            if not self.samples:
                return {}
            
            rss_values = [s["rss_mb"] for s in self.samples]
            return {
                "min_mb": min(rss_values),
                "max_mb": max(rss_values),
                "mean_mb": statistics.mean(rss_values),
                "final_mb": rss_values[-1],
                "samples": len(self.samples),
            }


# ============ 优化后的 StressTester 集成示例 ============

"""
# 在 modules/stress_test.py 中集成:

from core.memory_optimizer import StressTestMetrics, MemoryMonitor

class StressTester:
    def __init__(self, config: StressTestConfig):
        # ...
        self.metrics = StressTestMetrics(
            reservoir_size=10000,  # 固定 10k 样本
            sliding_window=1000    # 最近 1k 请求
        )
        self.memory_monitor = MemoryMonitor(check_interval=0.5)
    
    async def run(self):
        self.metrics.start_timer()
        self.memory_monitor.start()
        
        try:
            # ... 运行测试 ...
            # 在 worker 中记录:
            self.metrics.record_request(
                response_time=elapsed_ms,
                success=success,
                status_code=status_code,
                error=error_msg,
                size=body_size
            )
        finally:
            self.metrics.stop_timer()
            memory_summary = self.memory_monitor.stop()
        
        return self.metrics.get_summary()
"""


if __name__ == "__main__":
    # 测试水库采样
    print("=== 水库采样测试 ===")
    sampler = ReservoirSampler(max_size=100)
    for i in range(10000):
        sampler.add(random.gauss(100, 20))  # 正态分布
    
    stats = sampler.get_basic_stats()
    percentiles = sampler.get_percentiles()
    print(f"样本数: {stats['count']}, 采样池: {stats['sample_size']}")
    print(f"均值: {stats['mean']:.2f}, 真实均值: 100")
    print(f"P50: {percentiles['p50']:.2f}, P95: {percentiles['p95']:.2f}, P99: {percentiles['p99']:.2f}")
    
    # 测试流式统计
    print("\n=== 流式统计测试 ===")
    streaming = StreamingStats()
    for i in range(10000):
        streaming.update(random.gauss(100, 20))
    
    summary = streaming.get_summary()
    print(f"计数: {summary['count']}")
    print(f"均值: {summary['mean']:.2f}, 标准差: {summary['std_dev']:.2f}")
    print(f"95% CI: {summary['ci_95']}")
    print(f"P95 近似: {summary['percentiles']['p95']:.2f}")
    
    # 测试合并
    print("\n=== 合并测试 ===")
    s1 = StreamingStats()
    s2 = StreamingStats()
    for _ in range(5000):
        s1.update(random.gauss(100, 20))
    for _ in range(5000):
        s2.update(random.gauss(100, 20))
    
    s1.merge(s2)
    merged = s1.get_summary()
    print(f"合并后计数: {merged['count']}, 均值: {merged['mean']:.2f}")
    
    # 测试完整指标
    print("\n=== 完整指标测试 ===")
    metrics = StressTestMetrics()
    metrics.start_timer()
    
    for i in range(1000):
        rt = random.gauss(100, 30)
        metrics.record_request(rt, success=rt < 200, status_code=200 if rt < 200 else 500, size=1024)
    
    time.sleep(0.01)
    metrics.stop_timer()
    
    summary = metrics.get_summary()
    print(f"QPS: {summary['time']['qps']:.2f}")
    print(f"错误率: {summary['errors']['error_rate']:.2f}%")
    print(f"P99: {summary['response_time']['p99']:.2f}ms")