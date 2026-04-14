# 网站压力测试模块使用说明 (v2)

## 概述

AutoRecon v3.0 集成了专业的网站压力测试功能，**支持无上限并发和持续时间配置**：
- 快速压力测试
- 智能测试流程（6 阶段全自动）
- 容量极限测试（自动探测崩溃点）
- 性能瓶颈分析（8 种瓶颈识别）
- 抗压等级评估
- 性能评分系统

## 🚀 无上限配置

v2 版本移除了所有限制，由用户自行决定测试强度：

```python
from modules.stress_test import StressTestConfig

config = StressTestConfig(
    target_url="http://example.com",
    concurrent_users=10000,    # 支持 10000+ 并发
    duration=3600,             # 支持 1 小时+ 测试
    max_concurrent=50000,      # 连接池支持 50000
)
```

### 系统资源建议

| 并发数 | CPU | 内存 | 网络 |
|--------|-----|------|------|
| 100 | 2核 | 2GB | 10Mbps |
| 1000 | 4核 | 4GB | 100Mbps |
| 10000 | 8核 | 8GB | 1Gbps |
| 50000+ | 16核+ | 16GB+ | 10Gbps |

## 测试模式

### 1. 快速测试 (quick)

简单快速的测试，适合初步评估：

```python
from modules.stress_test import QuickStressTest

result = await QuickStressTest.test_url(
    url="http://example.com",
    concurrent=10,      # 并发用户数（无上限）
    duration=10,        # 持续时间（无上限）
    timeout=30          # 请求超时
)

print(f"QPS: {result['metrics']['throughput']['qps']}")
print(f"抗压等级: {result['metrics']['stress_level']}")
```

### 2. 智能测试 (intelligent) ⭐ 推荐

完整的 6 阶段自动化测试流程：
1. **预热测试** - 1 用户，检测基础响应
2. **基准测试** - 5 用户，建立性能基线
3. **负载测试** - 渐进增加并发，观察性能变化
4. **压力测试** - 高并发持续测试
5. **峰值测试** - 突发流量模拟（可选）
6. **分析报告** - 瓶颈识别 + 优化建议

```python
from modules.stress_advanced import IntelligentStressTest

tester = IntelligentStressTest(
    url="http://example.com",
    max_concurrent=1000,   # 最大并发限制（安全保护）
    max_duration=300       # 单阶段最大时长
)
result = await tester.auto_test()

# 查看分析结果
print(f"瓶颈类型: {result['analysis']['bottleneck_type']}")
print(f"性能评分: {result['performance_score']}/100")
print(f"优化建议: {result['recommendations']}")
```

### 3. 容量极限测试 (capacity)

逐步增加负载，**自动找到系统崩溃点**：

```python
from modules.stress_advanced import IntelligentStressTest

tester = IntelligentStressTest("http://example.com")
result = await tester.find_max_capacity(
    start_concurrent=5,     # 起始并发
    step_multiplier=1.5,    # 每步增长倍数
    max_steps=20            # 最多测试 20 步
)

print(f"最大 QPS: {result['summary']['max_qps']}")
print(f"最优并发数: {result['summary']['optimal_concurrent']}")
print(f"安全并发数: {result['summary']['safe_concurrent']}")
print(f"崩溃点: {result['summary']['breaking_concurrent']}")
```

## 抗压等级评估

系统根据 QPS、响应时间、错误率综合评分：

| 等级 | QPS | 响应时间 | 错误率 | 评分 |
|------|-----|----------|--------|------|
| 优秀 | > 1000 | < 100ms | < 0.1% | 80-100 |
| 良好 | 500-1000 | < 200ms | < 1% | 60-79 |
| 一般 | 100-500 | < 500ms | < 5% | 40-59 |
| 较差 | 50-100 | < 1000ms | < 10% | 20-39 |
| 危险 | < 50 | > 1000ms | > 10% | < 20 |

## 性能瓶颈分析

系统自动识别 **8 种**常见瓶颈：

### 1. CPU 瓶颈
**特征**: 响应时间稳定但较长，低错误率
**建议**: 增加 CPU 核心数、优化计算密集型代码、启用缓存

### 2. 内存瓶颈
**特征**: 内存相关错误 (OOM)
**建议**: 增加内存、检查内存泄漏、优化数据结构

### 3. 数据库瓶颈
**特征**: 响应时间波动大 (P99 >> P50)
**建议**: 检查慢查询、添加索引、增大连接池、读写分离

### 4. 网络瓶颈
**特征**: 超时频繁、响应时间 > 1s
**建议**: 检查网络延迟、启用压缩、使用 CDN

### 5. 带宽瓶颈
**特征**: 吞吐量 > 50 MB/s
**建议**: 升级带宽、启用 Gzip、CDN 分发

### 6. 连接数瓶颈
**特征**: 连接拒绝错误、高错误率
**建议**: 增加最大连接数、启用 Keep-Alive、负载均衡

### 7. 磁盘 I/O 瓶颈
**特征**: 响应时间波动、QPS < 200
**建议**: 使用 SSD、增加缓存、异步 I/O

### 8. 应用逻辑瓶颈
**特征**: 低 QPS 但低错误率
**建议**: 性能分析热点代码、减少外部调用、优化序列化

## Web API 端点

### POST /api/stress

创建压力测试任务（异步）：

```bash
curl -X POST http://localhost:8000/api/stress \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://example.com",
    "mode": "intelligent",
    "concurrent": 100,
    "duration": 60,
    "max_concurrent": 10000
  }'
```

### POST /api/stress/quick

快速测试（同步返回）：

```bash
curl -X POST http://localhost:8000/api/stress/quick \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://example.com",
    "concurrent": 100,
    "duration": 30,
    "max_concurrent": 5000
  }'
```

### GET /api/stress/{test_id}

获取测试状态和实时结果：

```bash
curl http://localhost:8000/api/stress/abc12345
```

## 高级配置

```python
from modules.stress_test import StressTestConfig, StressTester

config = StressTestConfig(
    target_url="http://example.com",
    
    # 并发配置（无上限）
    concurrent_users=1000,     # 并发用户数
    max_concurrent=50000,      # 最大并发数（连接池）
    ramp_up_time=60,           # 爬坡时间（秒）
    duration=300,              # 持续时间（秒）
    
    # 请求配置
    method="GET",
    timeout=60,                # 请求超时
    think_time=0.1,            # 思考时间
    think_time_random=0.05,    # 随机思考时间
    
    # 测试模式
    test_mode="concurrent",    # concurrent, throughput
    
    # 高级选项
    verify_ssl=False,
    follow_redirects=True,
    max_redirects=5,
    
    # 停止条件
    stop_on_error=False,
    max_error_rate=50.0,       # 最大错误率 %
    max_response_time=30000,   # 最大响应时间 ms
    
    # 重试配置
    max_retries=3,
    retry_delay=0.1
)

tester = StressTester(config)

# 实时进度回调
async def on_progress(phase, current, total):
    metrics = tester.get_current_metrics()
    print(f"[{phase}] {current}/{total} - QPS: {metrics['qps']:.0f}")

tester.on_progress = on_progress

# 运行测试
metrics = await tester.run()
print(f"抗压等级: {metrics.stress_level}")
```

## 容量曲线示例

容量极限测试会生成详细的容量曲线：

```
步骤  并发   QPS      响应时间   错误率   状态
1     5      125.3    45ms      0%       
2     8      198.7    52ms      0%       
3     12     289.4    68ms      0%       
4     18     412.8    95ms      0.2%     
5     27     523.1    128ms     0.5%     ← 最优
6     41     489.2    210ms     2.3%     
7     62     398.5    356ms     8.7%     
8     93     234.1    789ms     23.4%    ← 崩溃点
```

**安全运行建议**: 最优并发 ÷ 2 = 13-14 并发

## 智能测试报告示例

```json
{
  "url": "http://example.com",
  "test_time": "2026-03-22 15:30:00",
  
  "warmup": {"avg_response_time": 45.23},
  "baseline": {"qps": 125.3, "avg_time": 52.1},
  
  "load_test": [
    {"concurrent": 10, "qps": 198.7, "avg_time": 68.2, "error_rate": 0},
    {"concurrent": 20, "qps": 356.4, "avg_time": 95.3, "error_rate": 0.1},
    {"concurrent": 50, "qps": 523.1, "avg_time": 156.7, "error_rate": 0.8}
  ],
  
  "stress_test": {
    "concurrent": 100,
    "qps": 489.2,
    "avg_time": 289.4,
    "error_rate": 2.3,
    "stress_level": "良好"
  },
  
  "spike_test": {
    "base_concurrent": 50,
    "spike_concurrent": 250,
    "qps_drop": 15.2,
    "recovery_ok": true
  },
  
  "analysis": {
    "bottleneck_type": "数据库瓶颈",
    "confidence": 72,
    "description": "响应时间波动大，可能是数据库查询慢",
    "severity": "medium",
    "suggestions": [
      "检查慢查询日志",
      "添加数据库索引",
      "增大数据库连接池"
    ]
  },
  
  "performance_score": 68,
  "stress_level": "良好"
}
```

## 最佳实践

### 1. 测试前准备
- ✅ 确认目标网站允许测试
- ✅ 通知相关运维人员
- ✅ 选择低峰期进行大规模测试
- ✅ 监控本地资源使用

### 2. 测试策略
- 从小并发开始 (5-10)
- 逐步增加，观察性能拐点
- 记录每个阶段的指标
- 使用智能测试自动化流程

### 3. 结果分析
- 关注 P95、P99 响应时间
- 分析错误类型和分布
- 结合监控系统数据
- 多次测试取平均值

### 4. 持续测试
- 建立性能基准
- 定期回归测试
- 对比历史数据
- 代码变更后重新测试

## 注意事项

⚠️ **合法合规**: 仅测试自己拥有的或有授权的系统

⚠️ **资源消耗**: 高并发测试会消耗大量本地 CPU、内存、网络

⚠️ **目标影响**: 可能影响目标网站正常服务，请谨慎操作

⚠️ **网络因素**: 测试结果受网络环境影响，建议多次测试

## 故障排查

### 连接超时
```
原因: 目标不可达或防火墙拦截
解决: ping 测试、增加超时时间、检查防火墙
```

### 错误率过高
```
原因: 并发超过目标处理能力
解决: 降低并发、检查目标服务状态、分析错误类型
```

### 本地资源不足
```
原因: 本地 CPU/内存/网络耗尽
解决: 减少并发、关闭其他程序、升级硬件
```

### 测试卡住
```
原因: 网络问题或目标无响应
解决: 检查网络连接、设置合理的超时时间
```

---

**AutoRecon v3.0** - 专业安全测试工具
