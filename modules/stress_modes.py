#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.2 - 高级压力测试模式
阶梯测试、浸泡测试、混合负载测试
"""

import asyncio
import time
import logging
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import statistics

from modules.stress_test import StressTester, StressTestConfig, TestMetrics

logger = logging.getLogger(__name__)


# ============ 测试模式枚举 ============

class TestMode(Enum):
    """测试模式"""
    CONCURRENT = "concurrent"     # 并发用户测试
    THROUGHPUT = "throughput"     # 吞吐量测试
    STAIRCASE = "staircase"       # 阶梯测试
    SPIKE = "spike"               # 峰值测试
    SOAK = "soak"                 # 浸泡测试
    MIXED = "mixed"               # 混合负载测试


# ============ 配置类 ============

@dataclass
class StaircaseConfig:
    """阶梯测试配置"""
    start_concurrent: int = 10
    step_size: int = 10
    step_duration: int = 60        # 每阶持续秒数
    max_concurrent: int = 500
    stop_on_failure: bool = True
    failure_threshold: float = 10.0  # 错误率阈值 %


@dataclass
class SoakConfig:
    """浸泡测试配置"""
    concurrent: int = 50
    duration: int = 3600           # 总时长（秒）
    sample_interval: int = 60      # 采样间隔
    alert_threshold: float = 5.0   # 错误率报警阈值
    degradation_threshold: float = 20.0  # 性能衰减阈值 %


@dataclass
class SpikeConfig:
    """峰值测试配置"""
    base_concurrent: int = 50
    spike_concurrent: int = 200
    spike_duration: int = 30
    recovery_duration: int = 60


@dataclass
class MixedLoadConfig:
    """混合负载配置"""
    read_weight: float = 0.7
    write_weight: float = 0.2
    delete_weight: float = 0.1
    read_url: str = ""
    write_url: str = ""
    delete_url: str = ""


@dataclass
class TestPhaseResult:
    """测试阶段结果"""
    phase: str
    concurrent: int
    duration: float
    qps: float
    avg_response_time: float
    p99_response_time: float
    error_rate: float
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


# ============ 阶梯测试 ============

class StaircaseTest:
    """
    阶梯测试
    
    逐步增加并发用户，绘制性能曲线，找到最优并发点
    适用于：性能容量评估、瓶颈定位
    """
    
    def __init__(self, url: str, config: StaircaseConfig = None):
        self.url = url
        self.config = config or StaircaseConfig()
        self.results: List[TestPhaseResult] = []
        self.on_phase_complete: Optional[Callable] = None
    
    async def run(self) -> Dict[str, Any]:
        """执行阶梯测试"""
        logger.info(f"========== 开始阶梯测试: {self.url} ==========")
        logger.info(f"起始并发: {self.config.start_concurrent}, 步长: {self.config.step_size}, 最大: {self.config.max_concurrent}")
        
        current_concurrent = self.config.start_concurrent
        optimal_result = None
        breaking_result = None
        
        while current_concurrent <= self.config.max_concurrent:
            logger.info(f"[阶梯] 并发: {current_concurrent}")
            
            # 执行测试
            test_config = StressTestConfig(
                target_url=self.url,
                concurrent_users=current_concurrent,
                duration=self.config.step_duration
            )
            
            tester = StressTester(test_config)
            metrics = await tester.run()
            
            # 记录结果
            phase_result = TestPhaseResult(
                phase="staircase",
                concurrent=current_concurrent,
                duration=metrics.total_time,
                qps=metrics.qps,
                avg_response_time=metrics.avg_response_time,
                p99_response_time=metrics.p99_response_time,
                error_rate=metrics.error_rate,
                success=metrics.error_rate < self.config.failure_threshold
            )
            
            self.results.append(phase_result)
            
            # 回调
            if self.on_phase_complete:
                await self.on_phase_complete(phase_result)
            
            # 检查是否达到崩溃点
            if metrics.error_rate > self.config.failure_threshold:
                breaking_result = phase_result
                logger.warning(f"[阶梯] 错误率 {metrics.error_rate:.1f}% 超过阈值，停止测试")
                break
            
            # 记录最优结果
            if phase_result.success and (optimal_result is None or metrics.qps > optimal_result.qps):
                optimal_result = phase_result
            
            # 增加并发
            current_concurrent += self.config.step_size
        
        # 分析结果
        analysis = self._analyze_results()
        
        logger.info(f"========== 阶梯测试完成 ==========")
        
        return {
            "mode": "staircase",
            "url": self.url,
            "config": {
                "start_concurrent": self.config.start_concurrent,
                "step_size": self.config.step_size,
                "max_concurrent": self.config.max_concurrent,
            },
            "results": [r.__dict__ for r in self.results],
            "optimal": optimal_result.__dict__ if optimal_result else None,
            "breaking_point": breaking_result.__dict__ if breaking_result else None,
            "analysis": analysis
        }
    
    def _analyze_results(self) -> Dict[str, Any]:
        """分析测试结果"""
        if not self.results:
            return {}
        
        successful = [r for r in self.results if r.success]
        
        # 最优并发
        optimal = max(successful, key=lambda x: x.qps) if successful else None
        
        # 性能曲线
        qps_trend = [r.qps for r in self.results]
        response_trend = [r.avg_response_time for r in self.results]
        
        # 找到性能开始下降的点
        degradation_point = None
        for i in range(1, len(qps_trend)):
            if qps_trend[i] < qps_trend[i-1] * 0.9:  # QPS 下降 10%
                degradation_point = self.results[i].concurrent
                break
        
        return {
            "optimal_concurrent": optimal.concurrent if optimal else 0,
            "max_qps": max(qps_trend) if qps_trend else 0,
            "max_sustainable_concurrent": successful[-1].concurrent if successful else 0,
            "degradation_point": degradation_point,
            "recommendation": self._generate_recommendation(optimal, degradation_point)
        }
    
    def _generate_recommendation(self, optimal: TestPhaseResult, degradation_point: int) -> str:
        """生成建议"""
        if not optimal:
            return "系统无法承受测试负载，建议进行性能优化"
        
        safe_concurrent = int(optimal.concurrent * 0.7)
        
        rec = f"建议日常并发: {safe_concurrent} (最优的 70%)\n"
        rec += f"预期 QPS: {optimal.qps * 0.7:.0f}\n"
        
        if degradation_point:
            rec += f"性能下降点: {degradation_point} 并发\n"
        
        return rec


# ============ 浸泡测试 ============

class SoakTest:
    """
    浸泡测试 (耐久性测试)
    
    长时间稳定负载，检测内存泄漏、性能衰减
    适用于：稳定性验证、资源泄漏检测
    """
    
    def __init__(self, url: str, config: SoakConfig = None):
        self.url = url
        self.config = config or SoakConfig()
        self.samples: List[Dict[str, Any]] = []
        self.on_sample: Optional[Callable] = None
    
    async def run(self) -> Dict[str, Any]:
        """执行浸泡测试"""
        logger.info(f"========== 开始浸泡测试: {self.url} ==========")
        logger.info(f"并发: {self.config.concurrent}, 持续: {self.config.duration}s")
        
        start_time = time.time()
        elapsed = 0
        alerts = []
        
        while elapsed < self.config.duration:
            # 执行采样周期
            test_config = StressTestConfig(
                target_url=self.url,
                concurrent_users=self.config.concurrent,
                duration=self.config.sample_interval
            )
            
            tester = StressTester(test_config)
            metrics = await tester.run()
            
            # 记录采样
            sample = {
                "elapsed": elapsed,
                "timestamp": time.time() - start_time,
                "qps": metrics.qps,
                "avg_time": metrics.avg_response_time,
                "p99_time": metrics.p99_response_time,
                "error_rate": metrics.error_rate,
                "total_requests": metrics.total_requests
            }
            
            self.samples.append(sample)
            
            # 检查告警条件
            if metrics.error_rate > self.config.alert_threshold:
                alert = f"[警告] 错误率 {metrics.error_rate:.1f}% 超过阈值"
                alerts.append({"elapsed": elapsed, "message": alert})
                logger.warning(alert)
            
            # 回调
            if self.on_sample:
                await self.on_sample(sample)
            
            elapsed = time.time() - start_time
        
        # 分析性能趋势
        analysis = self._analyze_trend()
        
        logger.info(f"========== 浸泡测试完成 ==========")
        
        return {
            "mode": "soak",
            "url": self.url,
            "config": {
                "concurrent": self.config.concurrent,
                "duration": self.config.duration,
                "sample_interval": self.config.sample_interval
            },
            "samples": self.samples,
            "alerts": alerts,
            "analysis": analysis,
            "summary": {
                "total_duration": elapsed,
                "total_requests": sum(s["total_requests"] for s in self.samples),
                "avg_qps": statistics.mean(s["qps"] for s in self.samples) if self.samples else 0,
                "degradation_detected": analysis["degradation_detected"],
                "memory_leak_suspected": analysis["degradation_rate"] > 10
            }
        }
    
    def _analyze_trend(self) -> Dict[str, Any]:
        """分析性能趋势"""
        if len(self.samples) < 3:
            return {"degradation_detected": False, "degradation_rate": 0}
        
        # 取前 1/3 和后 1/3 对比
        n = len(self.samples)
        early_samples = self.samples[:n//3]
        late_samples = self.samples[-n//3:]
        
        early_avg_time = statistics.mean(s["avg_time"] for s in early_samples)
        late_avg_time = statistics.mean(s["avg_time"] for s in late_samples)
        
        early_qps = statistics.mean(s["qps"] for s in early_samples)
        late_qps = statistics.mean(s["qps"] for s in late_samples)
        
        # 计算衰减率
        time_increase = (late_avg_time - early_avg_time) / early_avg_time * 100 if early_avg_time > 0 else 0
        qps_decrease = (early_qps - late_qps) / early_qps * 100 if early_qps > 0 else 0
        
        degradation_detected = time_increase > self.config.degradation_threshold
        
        return {
            "degradation_detected": degradation_detected,
            "degradation_rate": time_increase,
            "early_avg_time": early_avg_time,
            "late_avg_time": late_avg_time,
            "early_qps": early_qps,
            "late_qps": late_qps,
            "time_increase_percent": time_increase,
            "qps_decrease_percent": qps_decrease,
            "trend": "degrading" if degradation_detected else "stable"
        }


# ============ 峰值测试 ============

class SpikeTest:
    """
    峰值测试 (突发流量测试)
    
    模拟突发流量，测试系统恢复能力
    适用于：弹性伸缩验证、熔断测试
    """
    
    def __init__(self, url: str, config: SpikeConfig = None):
        self.url = url
        self.config = config or SpikeConfig()
    
    async def run(self) -> Dict[str, Any]:
        """执行峰值测试"""
        logger.info(f"========== 开始峰值测试: {self.url} ==========")
        
        results = {}
        
        # 1. 基准负载
        logger.info(f"[峰值] 基准负载: {self.config.base_concurrent}")
        results["baseline"] = await self._run_phase(
            concurrent=self.config.base_concurrent,
            duration=30
        )
        
        # 2. 突发峰值
        logger.info(f"[峰值] 突发峰值: {self.config.spike_concurrent}")
        results["spike"] = await self._run_phase(
            concurrent=self.config.spike_concurrent,
            duration=self.config.spike_duration
        )
        
        # 3. 等待恢复
        logger.info(f"[峰值] 等待恢复...")
        await asyncio.sleep(5)
        
        # 4. 恢复后测试
        logger.info(f"[峰值] 恢复测试: {self.config.base_concurrent}")
        results["recovery"] = await self._run_phase(
            concurrent=self.config.base_concurrent,
            duration=self.config.recovery_duration
        )
        
        # 分析
        analysis = self._analyze_spike(results)
        
        logger.info(f"========== 峰值测试完成 ==========")
        
        return {
            "mode": "spike",
            "url": self.url,
            "config": {
                "base_concurrent": self.config.base_concurrent,
                "spike_concurrent": self.config.spike_concurrent,
                "spike_duration": self.config.spike_duration
            },
            "results": results,
            "analysis": analysis,
            "assessment": analysis["assessment"]
        }
    
    async def _run_phase(self, concurrent: int, duration: int) -> Dict[str, Any]:
        """执行测试阶段"""
        test_config = StressTestConfig(
            target_url=self.url,
            concurrent_users=concurrent,
            duration=duration
        )
        
        tester = StressTester(test_config)
        metrics = await tester.run()
        
        return {
            "concurrent": concurrent,
            "duration": duration,
            "qps": metrics.qps,
            "avg_time": metrics.avg_response_time,
            "p99_time": metrics.p99_response_time,
            "error_rate": metrics.error_rate,
            "success": metrics.error_rate < 10
        }
    
    def _analyze_spike(self, results: Dict) -> Dict[str, Any]:
        """分析峰值测试结果"""
        baseline = results["baseline"]
        spike = results["spike"]
        recovery = results["recovery"]
        
        # QPS 衰减
        expected_spike_qps = baseline["qps"] * (self.config.spike_concurrent / self.config.base_concurrent)
        qps_efficiency = (spike["qps"] / expected_spike_qps * 100) if expected_spike_qps > 0 else 0
        
        # 恢复比例
        recovery_ratio = (recovery["qps"] / baseline["qps"] * 100) if baseline["qps"] > 0 else 0
        
        # 错误率变化
        error_increase = spike["error_rate"] - baseline["error_rate"]
        
        # 评估
        if recovery_ratio > 95 and error_increase < 5:
            assessment = "优秀 - 系统弹性良好"
        elif recovery_ratio > 90 and error_increase < 10:
            assessment = "良好 - 系统基本恢复"
        elif recovery_ratio > 80:
            assessment = "一般 - 系统恢复较慢"
        else:
            assessment = "较差 - 系统恢复能力不足"
        
        return {
            "qps_efficiency": qps_efficiency,
            "recovery_ratio": recovery_ratio,
            "error_increase": error_increase,
            "assessment": assessment,
            "recovery_ok": recovery_ratio > 90 and error_increase < 10
        }


# ============ 混合负载测试 ============

class MixedLoadTest:
    """
    混合负载测试
    
    模拟真实用户行为：读多写少
    适用于：API 性能测试、真实场景模拟
    """
    
    def __init__(self, config: MixedLoadConfig):
        self.config = config
        self.read_results = []
        self.write_results = []
        self.delete_results = []
    
    async def run(self, duration: int = 60, total_users: int = 50) -> Dict[str, Any]:
        """执行混合负载测试"""
        logger.info(f"========== 开始混合负载测试 ==========")
        logger.info(f"读:写:删 = {self.config.read_weight}:{self.config.write_weight}:{self.config.delete_weight}")
        
        # 计算各类型用户数
        read_users = int(total_users * self.config.read_weight)
        write_users = int(total_users * self.config.write_weight)
        delete_users = total_users - read_users - write_users
        
        tasks = []
        
        # 启动读用户
        for _ in range(read_users):
            tasks.append(self._run_user_loop(self.config.read_url, "read", duration))
        
        # 启动写用户
        for _ in range(write_users):
            tasks.append(self._run_user_loop(self.config.write_url, "write", duration))
        
        # 启动删除用户
        for _ in range(delete_users):
            tasks.append(self._run_user_loop(self.config.delete_url, "delete", duration))
        
        # 执行
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "mode": "mixed",
            "duration": duration,
            "total_users": total_users,
            "read_users": read_users,
            "write_users": write_users,
            "delete_users": delete_users,
            "results": {
                "read": self._aggregate_results(self.read_results),
                "write": self._aggregate_results(self.write_results),
                "delete": self._aggregate_results(self.delete_results)
            }
        }
    
    async def _run_user_loop(self, url: str, operation: str, duration: int):
        """用户循环"""
        import aiohttp
        
        start_time = time.time()
        results = []
        
        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < duration:
                try:
                    async with session.get(url) as resp:
                        elapsed = time.time() - start_time
                        results.append({
                            "elapsed": elapsed,
                            "status": resp.status,
                            "success": resp.status < 400
                        })
                        
                        await asyncio.sleep(random.uniform(0.5, 2.0))
                
                except Exception as e:
                    results.append({
                        "elapsed": time.time() - start_time,
                        "error": str(e),
                        "success": False
                    })
        
        # 归类结果
        if operation == "read":
            self.read_results.extend(results)
        elif operation == "write":
            self.write_results.extend(results)
        else:
            self.delete_results.extend(results)
    
    def _aggregate_results(self, results: List[Dict]) -> Dict[str, Any]:
        """聚合结果"""
        if not results:
            return {"total": 0}
        
        success = sum(1 for r in results if r.get("success"))
        
        return {
            "total": len(results),
            "successful": success,
            "failed": len(results) - success,
            "success_rate": success / len(results) * 100
        }


# ============ 统一入口 ============

async def run_advanced_test(
    url: str,
    mode: str,
    config: Dict = None
) -> Dict[str, Any]:
    """
    运行高级测试
    
    Args:
        url: 目标 URL
        mode: 测试模式 (staircase/soak/spike/mixed)
        config: 测试配置
    
    Returns:
        测试结果
    """
    if mode == "staircase":
        test = StaircaseTest(url, StaircaseConfig(**(config or {})))
        return await test.run()
    
    elif mode == "soak":
        test = SoakTest(url, SoakConfig(**(config or {})))
        return await test.run()
    
    elif mode == "spike":
        test = SpikeTest(url, SpikeConfig(**(config or {})))
        return await test.run()
    
    elif mode == "mixed":
        test = MixedLoadTest(MixedLoadConfig(**(config or {})))
        return await test.run()
    
    else:
        raise ValueError(f"未知测试模式: {mode}")


# 导出
__all__ = [
    'TestMode',
    'StaircaseConfig',
    'SoakConfig',
    'SpikeConfig',
    'MixedLoadConfig',
    'TestPhaseResult',
    'StaircaseTest',
    'SoakTest',
    'SpikeTest',
    'MixedLoadTest',
    'run_advanced_test',
]
