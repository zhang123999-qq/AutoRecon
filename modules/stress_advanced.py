#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 高级压力测试模块（深度优化版 v2）
智能测试场景、自动瓶颈分析、容量极限探测、无上限配置
"""

import asyncio
import time
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

from modules.stress_test import (
    StressTester, StressTestConfig, TestMetrics,
    QuickStressTest, StressLevel
)

logger = logging.getLogger(__name__)


class BottleneckType(Enum):
    """瓶颈类型"""
    CPU = "CPU 瓶颈"
    MEMORY = "内存瓶颈"
    NETWORK = "网络瓶颈"
    DATABASE = "数据库瓶颈"
    BANDWIDTH = "带宽瓶颈"
    CONNECTION = "连接数瓶颈"
    DISK = "磁盘 I/O 瓶颈"
    APP_LOGIC = "应用逻辑瓶颈"
    UNKNOWN = "未知"


class TestPhase(Enum):
    """测试阶段"""
    WARMUP = "预热"
    BASELINE = "基准"
    LOAD = "负载"
    STRESS = "压力"
    SPIKE = "峰值"
    RECOVERY = "恢复"
    BREAKING = "极限"


@dataclass
class AnalysisResult:
    """分析结果"""
    bottleneck_type: BottleneckType
    confidence: float
    description: str
    suggestions: List[str]
    severity: str  # low, medium, high, critical


@dataclass
class CapacityPoint:
    """容量测试点"""
    concurrent: int
    qps: float
    avg_response_time: float
    p99_response_time: float
    error_rate: float
    cpu_estimate: float  # CPU 使用率估算
    is_breaking_point: bool = False
    is_optimal: bool = False


@dataclass
class IntelligentTestResult:
    """智能测试结果"""
    url: str
    test_time: str
    
    # 基础信息
    warmup_response_time: float
    baseline_qps: float
    baseline_response_time: float
    
    # 负载测试结果
    load_test: List[Dict]
    
    # 压力测试结果
    stress_test: Dict
    
    # 峰值测试结果
    spike_test: Optional[Dict] = None
    
    # 瓶颈分析
    analysis: Optional[AnalysisResult] = None
    
    # 容量分析
    capacity_analysis: Optional[Dict] = None
    
    # 优化建议
    recommendations: List[str] = field(default_factory=list)
    
    # 抗压等级
    stress_level: str = ""
    
    # 性能评分 (0-100)
    performance_score: int = 0


class PerformanceAnalyzer:
    """性能分析器（深度分析）"""
    
    @staticmethod
    def analyze(metrics: TestMetrics, phase: TestPhase = TestPhase.STRESS) -> AnalysisResult:
        """深度分析性能瓶颈"""
        avg_time = metrics.avg_response_time
        p99_time = metrics.p99_response_time
        p50_time = metrics.p50_response_time
        error_rate = metrics.error_rate
        qps = metrics.qps
        throughput = metrics.throughput_mbps
        
        # 计算响应时间离散度
        time_variance = (p99_time / avg_time) if avg_time > 0 else 1
        
        # 分析错误类型
        error_types = metrics.error_types or {}
        has_connection_errors = any(
            'connection' in e.lower() or 'refused' in e.lower() or 'reset' in e.lower()
            for e in error_types.keys()
        )
        has_timeout_errors = any(
            'timeout' in e.lower() for e in error_types.keys()
        )
        has_memory_errors = any(
            'memory' in e.lower() or 'oom' in e.lower() for e in error_types.keys()
        )
        
        # 1. 连接数瓶颈
        if has_connection_errors and error_rate > 5:
            return AnalysisResult(
                bottleneck_type=BottleneckType.CONNECTION,
                confidence=85,
                description=f"连接数达到上限，错误率 {error_rate:.1f}%，服务器拒绝新连接",
                suggestions=[
                    "增加服务器最大连接数配置 (如 nginx: worker_connections)",
                    "启用 TCP 连接复用 (Keep-Alive)",
                    "使用负载均衡分流请求",
                    "检查连接泄漏问题",
                    "调整系统文件描述符限制 (ulimit -n)",
                    f"当前并发 {metrics.concurrent_users}，建议控制在 {metrics.concurrent_users // 2} 以内"
                ],
                severity="high" if error_rate > 20 else "medium"
            )
        
        # 2. 超时瓶颈（网络或处理慢）
        if has_timeout_errors and avg_time > 1000:
            return AnalysisResult(
                bottleneck_type=BottleneckType.NETWORK,
                confidence=75,
                description=f"请求超时频繁，平均响应时间 {avg_time:.0f}ms",
                suggestions=[
                    "检查服务器到数据库的网络延迟",
                    "优化慢查询或慢请求",
                    "增加请求超时时间配置",
                    "检查网络带宽使用情况",
                    "考虑使用 CDN 加速静态资源"
                ],
                severity="high" if avg_time > 3000 else "medium"
            )
        
        # 3. 内存瓶颈
        if has_memory_errors:
            return AnalysisResult(
                bottleneck_type=BottleneckType.MEMORY,
                confidence=80,
                description="检测到内存相关错误，可能是内存不足或泄漏",
                suggestions=[
                    "增加服务器内存",
                    "检查并修复内存泄漏",
                    "优化数据结构，减少内存占用",
                    "启用对象池复用",
                    "调整 GC 参数 (如 Python 的 GC 阈值)"
                ],
                severity="critical"
            )
        
        # 4. 数据库瓶颈
        if time_variance > 4 and avg_time > 200:
            return AnalysisResult(
                bottleneck_type=BottleneckType.DATABASE,
                confidence=70,
                description=f"响应时间波动大 (P99/P50 = {time_variance:.1f}x)，可能是数据库查询慢",
                suggestions=[
                    "检查慢查询日志，优化 SQL",
                    "添加数据库索引",
                    "增大数据库连接池",
                    "考虑读写分离或分库分表",
                    "启用查询缓存",
                    "使用 Redis 缓存热点数据"
                ],
                severity="high" if time_variance > 6 else "medium"
            )
        
        # 5. CPU 瓶颈
        if avg_time > 500 and time_variance < 3 and error_rate < 5:
            return AnalysisResult(
                bottleneck_type=BottleneckType.CPU,
                confidence=72,
                description="响应时间稳定但较长，可能是 CPU 资源不足或计算密集",
                suggestions=[
                    "增加服务器 CPU 核心数",
                    "优化计算密集型代码",
                    "启用缓存减少重复计算",
                    "使用异步处理或消息队列",
                    "考虑使用更高效的算法",
                    "启用 JIT 编译 (如 PyPy)"
                ],
                severity="high" if avg_time > 1000 else "medium"
            )
        
        # 6. 带宽瓶颈
        if throughput > 50:
            return AnalysisResult(
                bottleneck_type=BottleneckType.BANDWIDTH,
                confidence=70,
                description=f"带宽使用 {throughput:.1f} MB/s，接近或超过上限",
                suggestions=[
                    "升级服务器带宽",
                    "启用 Gzip/Brotli 压缩",
                    "使用 CDN 分发静态资源",
                    "优化图片和资源体积",
                    "启用 HTTP/2 或 HTTP/3",
                    "实现资源懒加载"
                ],
                severity="medium"
            )
        
        # 7. 应用逻辑瓶颈
        if avg_time > 100 and qps < 100 and error_rate < 1:
            return AnalysisResult(
                bottleneck_type=BottleneckType.APP_LOGIC,
                confidence=65,
                description="低错误率但 QPS 较低，可能是应用逻辑效率问题",
                suggestions=[
                    "使用性能分析工具定位热点代码",
                    "优化业务逻辑，减少不必要的计算",
                    "减少外部 API 调用或使用缓存",
                    "优化序列化/反序列化过程",
                    "使用连接池复用资源"
                ],
                severity="low"
            )
        
        # 8. 磁盘 I/O 瓶颈
        if avg_time > 200 and time_variance > 2 and qps < 200:
            return AnalysisResult(
                bottleneck_type=BottleneckType.DISK,
                confidence=60,
                description="可能是磁盘 I/O 成为瓶颈",
                suggestions=[
                    "使用 SSD 替换 HDD",
                    "优化文件读写逻辑",
                    "增加内存缓存减少磁盘访问",
                    "使用异步 I/O",
                    "考虑使用对象存储"
                ],
                severity="medium"
            )
        
        # 默认
        return AnalysisResult(
            bottleneck_type=BottleneckType.UNKNOWN,
            confidence=30,
            description="未能确定具体瓶颈类型，建议进一步分析",
            suggestions=[
                "启用详细日志记录",
                "使用 APM 工具进行深度分析",
                "监控系统资源使用 (CPU/内存/磁盘/网络)",
                "进行代码级性能分析"
            ],
            severity="low"
        )


class IntelligentStressTest:
    """智能压力测试（全面优化版）"""
    
    def __init__(self, url: str, max_concurrent: int = 1000, max_duration: int = 300):
        self.url = url
        self.max_concurrent = max_concurrent
        self.max_duration = max_duration
        self.results = IntelligentTestResult(
            url=url,
            test_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            warmup_response_time=0,
            baseline_qps=0,
            baseline_response_time=0,
            load_test=[],
            stress_test={},
            recommendations=[]
        )
    
    async def _quick_test(self, concurrent: int, duration: int) -> Dict:
        """快速测试辅助方法"""
        return await QuickStressTest.test_url(self.url, concurrent=concurrent, duration=duration)
    
    async def warmup(self) -> float:
        """阶段 1: 预热测试"""
        logger.info(f"[预热] 测试 {self.url}")
        
        result = await self._quick_test(concurrent=1, duration=3)
        avg_time = result['metrics']['response_time']['avg']
        self.results.warmup_response_time = avg_time
        
        logger.info(f"[预热] 响应时间: {avg_time:.2f}ms")
        return avg_time
    
    async def baseline(self) -> Tuple[float, float]:
        """阶段 2: 基准测试"""
        logger.info(f"[基准] 测试 {self.url}")
        
        result = await self._quick_test(concurrent=5, duration=5)
        qps = result['metrics']['throughput']['qps']
        avg_time = result['metrics']['response_time']['avg']
        
        self.results.baseline_qps = qps
        self.results.baseline_response_time = avg_time
        
        logger.info(f"[基准] QPS: {qps:.2f}, 响应时间: {avg_time:.2f}ms")
        return qps, avg_time
    
    async def load_test(self, levels: List[int] = None) -> List[Dict]:
        """阶段 3: 负载测试（渐进增加并发）"""
        logger.info(f"[负载] 开始负载测试")
        
        if levels is None:
            # 根据基准 QPS 自动选择测试级别
            baseline_qps = self.results.baseline_qps
            if baseline_qps > 500:
                levels = [10, 20, 50, 100, 200, 500]
            elif baseline_qps > 100:
                levels = [10, 20, 50, 100, 200]
            else:
                levels = [5, 10, 20, 50, 100]
        
        results = []
        
        for concurrent in levels:
            if concurrent > self.max_concurrent:
                break
            
            logger.info(f"[负载] 并发 {concurrent}")
            
            result = await self._quick_test(concurrent=concurrent, duration=10)
            m = result['metrics']
            
            entry = {
                "concurrent": concurrent,
                "qps": m['throughput']['qps'],
                "avg_time": m['response_time']['avg'],
                "p99_time": m['response_time']['p99'],
                "error_rate": m['errors']['error_rate'],
                "stress_level": m['stress_level']
            }
            results.append(entry)
            
            # 错误率超过 20% 停止递增
            if m['errors']['error_rate'] > 20:
                logger.warning(f"[负载] 错误率 {m['errors']['error_rate']:.1f}% 过高，停止递增")
                break
            
            # 响应时间超过 5 秒停止
            if m['response_time']['avg'] > 5000:
                logger.warning(f"[负载] 响应时间 {m['response_time']['avg']:.0f}ms 过长，停止递增")
                break
        
        self.results.load_test = results
        return results
    
    async def stress_test(self, concurrent: int = None) -> Dict:
        """阶段 4: 压力测试（高并发持续测试）"""
        logger.info(f"[压力] 开始压力测试")
        
        # 根据负载测试结果选择并发数
        if concurrent is None:
            valid_results = [r for r in self.results.load_test if r['error_rate'] < 10]
            if valid_results:
                best = max(valid_results, key=lambda x: x['qps'])
                concurrent = best['concurrent']
            else:
                concurrent = 50
        
        concurrent = min(concurrent, self.max_concurrent)
        logger.info(f"[压力] 并发 {concurrent}, 持续 30 秒")
        
        result = await self._quick_test(concurrent=concurrent, duration=30)
        m = result['metrics']
        
        self.results.stress_test = {
            "concurrent": concurrent,
            "qps": m['throughput']['qps'],
            "avg_time": m['response_time']['avg'],
            "p99_time": m['response_time']['p99'],
            "error_rate": m['errors']['error_rate'],
            "stress_level": m['stress_level'],
            "total_requests": m['total_requests'],
            "successful_requests": m['successful_requests'],
            "failed_requests": m['failed_requests']
        }
        
        logger.info(f"[压力] QPS: {m['throughput']['qps']:.2f}, 错误率: {m['errors']['error_rate']:.1f}%")
        return self.results.stress_test
    
    async def spike_test(self, base_concurrent: int = 50, spike_multiplier: float = 5.0) -> Dict:
        """阶段 5: 峰值测试（突发流量）"""
        logger.info(f"[峰值] 开始峰值测试")
        
        # 基准负载
        base_result = await self._quick_test(concurrent=base_concurrent, duration=5)
        base_qps = base_result['metrics']['throughput']['qps']
        
        # 突发峰值
        spike_concurrent = int(base_concurrent * spike_multiplier)
        spike_concurrent = min(spike_concurrent, self.max_concurrent)
        
        logger.info(f"[峰值] 突发并发 {spike_concurrent}")
        
        spike_result = await self._quick_test(concurrent=spike_concurrent, duration=10)
        spike_m = spike_result['metrics']
        
        result = {
            "base_concurrent": base_concurrent,
            "base_qps": base_qps,
            "spike_concurrent": spike_concurrent,
            "spike_qps": spike_m['throughput']['qps'],
            "spike_avg_time": spike_m['response_time']['avg'],
            "spike_error_rate": spike_m['errors']['error_rate'],
            "qps_drop": round((1 - spike_m['throughput']['qps'] / base_qps / spike_multiplier) * 100, 1) if base_qps > 0 else 0,
            "recovery_ok": spike_m['errors']['error_rate'] < 10
        }
        
        self.results.spike_test = result
        logger.info(f"[峰值] QPS 衰减: {result['qps_drop']}%, 恢复状态: {'OK' if result['recovery_ok'] else 'FAILED'}")
        return result
    
    async def analyze(self) -> AnalysisResult:
        """阶段 6: 瓶颈分析"""
        logger.info(f"[分析] 开始瓶颈分析")
        
        if not self.results.stress_test:
            return None
        
        # 创建指标对象
        metrics = TestMetrics()
        m = self.results.stress_test
        metrics.avg_response_time = m['avg_time']
        metrics.p99_response_time = m['p99_time']
        metrics.p50_response_time = m.get('p50_time', m['avg_time'])
        metrics.qps = m['qps']
        metrics.error_rate = m['error_rate']
        metrics.throughput_mbps = 0
        metrics.concurrent_users = m['concurrent']
        
        analysis = PerformanceAnalyzer.analyze(metrics)
        self.results.analysis = analysis
        
        logger.info(f"[分析] 瓶颈类型: {analysis.bottleneck_type.value}, 置信度: {analysis.confidence}%")
        return analysis
    
    def calculate_score(self) -> int:
        """计算性能评分 (0-100)"""
        if not self.results.stress_test:
            return 0
        
        m = self.results.stress_test
        score = 0
        
        # QPS 评分 (40 分)
        qps = m['qps']
        if qps >= 1000:
            score += 40
        elif qps >= 500:
            score += 32
        elif qps >= 200:
            score += 24
        elif qps >= 100:
            score += 16
        elif qps >= 50:
            score += 8
        
        # 响应时间评分 (30 分)
        avg_time = m['avg_time']
        if avg_time <= 50:
            score += 30
        elif avg_time <= 100:
            score += 25
        elif avg_time <= 200:
            score += 20
        elif avg_time <= 500:
            score += 12
        elif avg_time <= 1000:
            score += 5
        
        # 错误率评分 (30 分)
        error_rate = m['error_rate']
        if error_rate <= 0.1:
            score += 30
        elif error_rate <= 1:
            score += 25
        elif error_rate <= 5:
            score += 15
        elif error_rate <= 10:
            score += 5
        
        self.results.performance_score = score
        return score
    
    def generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if self.results.analysis:
            recommendations.extend(self.results.analysis.suggestions)
        
        # 根据测试结果添加建议
        m = self.results.stress_test
        if m:
            if m['error_rate'] > 10:
                recommendations.append(f"建议日常并发控制在 {m['concurrent'] // 2} 以内，避免错误率过高")
            
            if m['avg_time'] > 500:
                recommendations.append("响应时间较长，建议进行性能优化或增加服务器资源")
            
            if m['qps'] < 50:
                recommendations.append("QPS 较低，建议检查服务器配置和代码效率")
        
        # 去重
        self.results.recommendations = list(dict.fromkeys(recommendations))
        return self.results.recommendations
    
    async def auto_test(self) -> Dict:
        """完整的智能测试流程"""
        logger.info(f"========== 开始智能压力测试: {self.url} ==========")
        
        try:
            # 1. 预热
            await self.warmup()
            
            # 2. 基准测试
            await self.baseline()
            
            # 3. 负载测试
            await self.load_test()
            
            # 4. 压力测试
            await self.stress_test()
            
            # 5. 峰值测试（可选）
            if self.results.stress_test.get('error_rate', 100) < 20:
                await self.spike_test()
            
            # 6. 分析
            await self.analyze()
            
            # 7. 计算评分
            self.calculate_score()
            
            # 8. 生成建议
            self.generate_recommendations()
            
            self.results.stress_level = self.results.stress_test.get('stress_level', '未知')
            
        except Exception as e:
            logger.error(f"智能测试异常: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info(f"========== 智能压力测试完成 ==========")
        
        return {
            "url": self.results.url,
            "test_time": self.results.test_time,
            "warmup": {"avg_response_time": self.results.warmup_response_time},
            "baseline": {
                "qps": self.results.baseline_qps,
                "avg_time": self.results.baseline_response_time
            },
            "load_test": self.results.load_test,
            "stress_test": self.results.stress_test,
            "spike_test": self.results.spike_test,
            "analysis": {
                "bottleneck_type": self.results.analysis.bottleneck_type.value if self.results.analysis else "未知",
                "confidence": self.results.analysis.confidence if self.results.analysis else 0,
                "description": self.results.analysis.description if self.results.analysis else "",
                "suggestions": self.results.analysis.suggestions if self.results.analysis else [],
                "severity": self.results.analysis.severity if self.results.analysis else "low"
            } if self.results.analysis else None,
            "recommendations": self.results.recommendations,
            "stress_level": self.results.stress_level,
            "performance_score": self.results.performance_score
        }
    
    async def find_max_capacity(self, start_concurrent: int = 5, step_multiplier: float = 1.5, max_steps: int = 20) -> Dict:
        """容量极限测试 - 寻找系统崩溃点"""
        logger.info(f"========== 开始容量极限测试: {self.url} ==========")
        
        results: List[CapacityPoint] = []
        concurrent = start_concurrent
        step = 0
        breaking_point = None
        optimal_point = None
        
        while step < max_steps and concurrent <= self.max_concurrent:
            step += 1
            logger.info(f"[容量] 步骤 {step}/{max_steps}, 并发 {concurrent}")
            
            result = await self._quick_test(concurrent=concurrent, duration=5)
            m = result['metrics']
            
            point = CapacityPoint(
                concurrent=concurrent,
                qps=m['throughput']['qps'],
                avg_response_time=m['response_time']['avg'],
                p99_response_time=m['response_time']['p99'],
                error_rate=m['errors']['error_rate'],
                cpu_estimate=min(100, concurrent * 2),  # 估算
                is_breaking_point=False,
                is_optimal=False
            )
            
            results.append(point)
            
            # 检查崩溃点
            if m['errors']['error_rate'] > 30:
                point.is_breaking_point = True
                breaking_point = point
                logger.warning(f"[容量] 发现崩溃点! 并发 {concurrent}, 错误率 {m['errors']['error_rate']:.1f}%")
                break
            
            if m['response_time']['avg'] > 10000:
                point.is_breaking_point = True
                breaking_point = point
                logger.warning(f"[容量] 响应时间过长: {m['response_time']['avg']:.0f}ms")
                break
            
            # 递增并发
            concurrent = int(concurrent * step_multiplier)
        
        # 分析结果，找到最优并发点
        valid_results = [r for r in results if r.error_rate < 10]
        if valid_results:
            optimal = max(valid_results, key=lambda x: x.qps)
            optimal.is_optimal = True
            optimal_point = optimal
        
        # 计算安全阈值
        safe_concurrent = optimal_point.concurrent // 2 if optimal_point else 10
        
        # 找到安全边界
        first_error_concurrent = next(
            (r.concurrent for r in results if r.error_rate > 5),
            results[-1].concurrent if results else 100
        )
        
        logger.info(f"[容量] 最优并发: {optimal_point.concurrent if optimal_point else 'N/A'}, 安全阈值: {safe_concurrent}")
        logger.info(f"========== 容量极限测试完成 ==========")
        
        return {
            "url": self.url,
            "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "capacity_curve": [
                {
                    "concurrent": r.concurrent,
                    "qps": r.qps,
                    "avg_time": r.avg_response_time,
                    "p99_time": r.p99_response_time,
                    "error_rate": r.error_rate,
                    "is_breaking": r.is_breaking_point,
                    "is_optimal": r.is_optimal
                }
                for r in results
            ],
            "summary": {
                "max_qps": max((r.qps for r in results), default=0),
                "max_concurrent_tested": results[-1].concurrent if results else 0,
                "optimal_concurrent": optimal_point.concurrent if optimal_point else 0,
                "optimal_qps": optimal_point.qps if optimal_point else 0,
                "breaking_concurrent": breaking_point.concurrent if breaking_point else None,
                "breaking_error_rate": breaking_point.error_rate if breaking_point else None,
                "safe_concurrent": safe_concurrent,
                "safe_qps_estimate": optimal_point.qps * 0.8 if optimal_point else 0,
                "first_error_concurrent": first_error_concurrent
            },
            "recommendations": [
                f"系统最优并发: {optimal_point.concurrent if optimal_point else 'N/A'} (QPS: {optimal_point.qps:.0f if optimal_point else 0})",
                f"安全运行并发: {safe_concurrent} (建议日常使用)",
                f"崩溃点并发: {breaking_point.concurrent if breaking_point else '未达到'}",
                f"首次出现错误并发: {first_error_concurrent}",
                f"最大测试 QPS: {max((r.qps for r in results), default=0):.0f}",
            ],
            "capacity_level": self._calculate_capacity_level(results, optimal_point, breaking_point)
        }
    
    def _calculate_capacity_level(self, results: List[CapacityPoint], optimal: Optional[CapacityPoint], breaking: Optional[CapacityPoint]) -> str:
        """计算容量等级"""
        if not results:
            return "未知"
        
        max_qps = max(r.qps for r in results)
        
        if max_qps >= 1000:
            return "高容量"
        elif max_qps >= 500:
            return "中等容量"
        elif max_qps >= 100:
            return "标准容量"
        elif max_qps >= 50:
            return "低容量"
        else:
            return "受限容量"


async def run_stress_test(
    url: str,
    mode: str = "quick",
    concurrent: int = 10,
    duration: int = 10,
    max_concurrent: int = 10000
) -> Dict:
    """运行压力测试（供 Web API 调用）"""
    if mode == "quick":
        return await QuickStressTest.test_url(url, concurrent, duration)
    
    elif mode == "intelligent":
        tester = IntelligentStressTest(url, max_concurrent=max_concurrent)
        return await tester.auto_test()
    
    elif mode == "capacity":
        tester = IntelligentStressTest(url, max_concurrent=max_concurrent)
        return await tester.find_max_capacity()
    
    else:
        raise ValueError(f"Unknown mode: {mode}")


# 导出
__all__ = [
    'IntelligentStressTest',
    'PerformanceAnalyzer',
    'run_stress_test',
    'BottleneckType',
    'TestPhase',
    'AnalysisResult',
    'CapacityPoint',
    'IntelligentTestResult',
]
