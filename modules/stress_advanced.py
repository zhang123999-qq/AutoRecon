#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 高级压力测试模块（深度优化版）
智能测试场景、自动瓶颈分析、优化建议
"""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from modules.stress_test import (
    StressTester, StressTestConfig, TestMetrics,
    QuickStressTest
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
    UNKNOWN = "未知"


@dataclass
class AnalysisResult:
    """分析结果"""
    bottleneck_type: BottleneckType
    confidence: float
    description: str
    suggestions: List[str]


class PerformanceAnalyzer:
    """性能分析器"""
    
    @staticmethod
    def analyze(metrics: TestMetrics) -> AnalysisResult:
        """分析性能瓶颈"""
        avg_time = metrics.avg_response_time
        p99_time = metrics.p99_response_time
        error_rate = metrics.error_rate
        qps = metrics.qps
        
        # 1. 连接数瓶颈
        if error_rate > 10:
            for error_type in metrics.error_types:
                if 'connection' in error_type.lower() or 'refused' in error_type.lower():
                    return AnalysisResult(
                        bottleneck_type=BottleneckType.CONNECTION,
                        confidence=80,
                        description="连接数达到上限，服务器拒绝新连接",
                        suggestions=[
                            "增加服务器最大连接数配置",
                            "启用连接复用 (Keep-Alive)",
                            "使用负载均衡分流",
                            "检查连接泄漏问题"
                        ]
                    )
        
        # 2. 数据库瓶颈
        if p99_time > avg_time * 5 and avg_time > 200:
            return AnalysisResult(
                bottleneck_type=BottleneckType.DATABASE,
                confidence=70,
                description="响应时间波动大，可能是数据库查询慢或连接池不足",
                suggestions=[
                    "检查慢查询日志",
                    "添加数据库索引",
                    "增大数据库连接池",
                    "考虑读写分离"
                ]
            )
        
        # 3. CPU 瓶颈
        if avg_time > 500 and p99_time > avg_time * 3 and error_rate < 5:
            return AnalysisResult(
                bottleneck_type=BottleneckType.CPU,
                confidence=75,
                description="响应时间随负载增加显著增长，可能是 CPU 资源不足",
                suggestions=[
                    "增加服务器 CPU 资源",
                    "优化计算密集型代码",
                    "启用缓存减少重复计算",
                    "考虑异步处理或队列"
                ]
            )
        
        # 4. 网络瓶颈
        if avg_time > 100 and qps < 100 and error_rate < 1:
            return AnalysisResult(
                bottleneck_type=BottleneckType.NETWORK,
                confidence=65,
                description="网络延迟较高，可能是带宽不足或网络质量差",
                suggestions=[
                    "检查网络带宽使用情况",
                    "启用 HTTP/2 或 HTTP/3",
                    "启用 Gzip 压缩",
                    "使用 CDN 加速"
                ]
            )
        
        # 5. 内存瓶颈
        if 'Memory' in str(metrics.error_types) or 'OOM' in str(metrics.error_types):
            return AnalysisResult(
                bottleneck_type=BottleneckType.MEMORY,
                confidence=75,
                description="内存资源紧张，可能触发频繁 GC 或 OOM",
                suggestions=[
                    "增加服务器内存",
                    "优化内存使用",
                    "检查内存泄漏",
                    "调整 GC 参数"
                ]
            )
        
        # 6. 带宽瓶颈
        if metrics.throughput_mbps > 50:
            return AnalysisResult(
                bottleneck_type=BottleneckType.BANDWIDTH,
                confidence=70,
                description="带宽使用率接近上限，成为性能瓶颈",
                suggestions=[
                    "升级带宽",
                    "启用内容压缩",
                    "使用 CDN 分发静态资源",
                    "优化资源体积"
                ]
            )
        
        # 默认
        return AnalysisResult(
            bottleneck_type=BottleneckType.UNKNOWN,
            confidence=30,
            description="未能确定具体瓶颈类型，建议进一步分析",
            suggestions=[
                "启用详细日志记录",
                "监控系统资源使用",
                "使用 APM 工具分析",
                "进行代码级性能分析"
            ]
        )


class IntelligentStressTest:
    """智能压力测试"""
    
    def __init__(self, url: str):
        self.url = url
    
    async def auto_test(self) -> Dict:
        """自动化测试流程"""
        logger.info(f"开始智能压力测试: {self.url}")
        
        # 阶段 1: 预热
        logger.info("阶段 1/5: 预热测试")
        warmup_result = await QuickStressTest.test_url(self.url, concurrent=1, duration=3)
        warmup_time = warmup_result['metrics']['response_time']['avg']
        
        # 阶段 2: 基准测试
        logger.info("阶段 2/5: 基准测试")
        baseline_result = await QuickStressTest.test_url(self.url, concurrent=5, duration=5)
        baseline_qps = baseline_result['metrics']['throughput']['qps']
        
        # 阶段 3: 负载测试
        logger.info("阶段 3/5: 负载测试")
        load_results = []
        
        for concurrent in [10, 20, 50]:
            result = await QuickStressTest.test_url(self.url, concurrent=concurrent, duration=10)
            load_results.append({
                "concurrent": concurrent,
                "qps": result['metrics']['throughput']['qps'],
                "avg_time": result['metrics']['response_time']['avg'],
                "error_rate": result['metrics']['errors']['error_rate']
            })
            
            if result['metrics']['errors']['error_rate'] > 20:
                logger.warning("错误率过高，停止递增")
                break
        
        # 阶段 4: 压力测试
        logger.info("阶段 4/5: 压力测试")
        max_concurrent = max(r["concurrent"] for r in load_results) if load_results else 10
        stress_concurrent = min(100, max_concurrent * 2)
        
        stress_result = await QuickStressTest.test_url(
            self.url, 
            concurrent=stress_concurrent, 
            duration=15
        )
        
        # 阶段 5: 分析
        logger.info("阶段 5/5: 生成分析报告")
        
        # 创建指标对象进行分析
        metrics = TestMetrics()
        m = stress_result['metrics']
        metrics.avg_response_time = m['response_time']['avg']
        metrics.p99_response_time = m['response_time']['p99']
        metrics.qps = m['throughput']['qps']
        metrics.error_rate = m['errors']['error_rate']
        metrics.throughput_mbps = m['throughput']['throughput_mbps']
        metrics.error_types = m['errors'].get('error_types', {})
        
        analysis = PerformanceAnalyzer.analyze(metrics)
        
        return {
            "url": self.url,
            "warmup": {"avg_response_time": warmup_time},
            "baseline": {
                "qps": baseline_result['metrics']['throughput']['qps'],
                "avg_time": baseline_result['metrics']['response_time']['avg']
            },
            "load_test": load_results,
            "stress_test": {
                "qps": stress_result['metrics']['throughput']['qps'],
                "avg_time": stress_result['metrics']['response_time']['avg'],
                "error_rate": stress_result['metrics']['errors']['error_rate'],
                "stress_level": stress_result['metrics']['stress_level']
            },
            "analysis": {
                "bottleneck_type": analysis.bottleneck_type.value,
                "confidence": analysis.confidence,
                "description": analysis.description,
                "suggestions": analysis.suggestions
            },
            "stress_level": stress_result['metrics']['stress_level']
        }
    
    async def find_max_capacity(self) -> Dict:
        """寻找最大容量"""
        logger.info(f"开始容量极限测试: {self.url}")
        
        results = []
        concurrent = 5
        max_concurrent = 200  # 降低最大并发，避免过长时间测试
        
        while concurrent <= max_concurrent:
            logger.info(f"测试并发: {concurrent}")
            
            result = await QuickStressTest.test_url(
                self.url, 
                concurrent=concurrent, 
                duration=5  # 减少每次测试时间
            )
            
            m = result['metrics']
            results.append({
                "concurrent": concurrent,
                "qps": m['throughput']['qps'],
                "avg_time": m['response_time']['avg'],
                "error_rate": m['errors']['error_rate']
            })
            
            # 检查崩溃点
            if m['errors']['error_rate'] > 30:
                logger.warning(f"系统崩溃! 错误率: {m['errors']['error_rate']:.1f}%")
                break
            
            if m['response_time']['avg'] > 10000:
                logger.warning(f"响应时间过长: {m['response_time']['avg']:.0f} ms")
                break
            
            concurrent = int(concurrent * 1.5)
        
        # 分析结果
        valid_results = [r for r in results if r['error_rate'] < 10]
        best = max(valid_results, key=lambda x: x['qps']) if valid_results else results[-1]
        breaking = next((r for r in reversed(results) if r['error_rate'] > 10), results[-1])
        
        return {
            "url": self.url,
            "results": results,
            "max_qps": best['qps'],
            "best_concurrent": best['concurrent'],
            "breaking_concurrent": breaking['concurrent'],
            "recommendation": f"建议日常运行在 {best['concurrent'] // 2} 并发以下"
        }


async def run_stress_test(
    url: str,
    mode: str = "quick",
    concurrent: int = 10,
    duration: int = 10
) -> Dict:
    """运行压力测试（供 Web API 调用）"""
    if mode == "quick":
        return await QuickStressTest.test_url(url, concurrent, duration)
    
    elif mode == "intelligent":
        tester = IntelligentStressTest(url)
        return await tester.auto_test()
    
    elif mode == "capacity":
        tester = IntelligentStressTest(url)
        return await tester.find_max_capacity()
    
    else:
        raise ValueError(f"Unknown mode: {mode}")


# 导出
__all__ = [
    'IntelligentStressTest',
    'PerformanceAnalyzer',
    'run_stress_test',
    'BottleneckType',
]
