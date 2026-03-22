# 网站压力测试模块使用说明

## 概述

AutoRecon v3.0 集成了专业的网站压力测试功能，支持：
- 快速压力测试
- 智能测试流程
- 容量极限测试
- 性能瓶颈分析
- 抗压等级评估

## 测试模式

### 1. 快速测试 (quick)

简单快速的测试，适合初步评估：

```python
from modules.stress_test import QuickStressTest

result = await QuickStressTest.test_url(
    url="http://example.com",
    concurrent=10,      # 并发用户数
    duration=10,        # 持续时间（秒）
    timeout=10          # 请求超时（秒）
)

print(f"QPS: {result['metrics']['throughput']['qps']}")
print(f"抗压等级: {result['metrics']['stress_level']}")
```

### 2. 智能测试 (intelligent)

完整的自动化测试流程：
1. 预热测试 (1 用户, 5 秒)
2. 基准测试 (5 用户, 10 秒)
3. 负载测试 (递增并发)
4. 压力测试 (高负载)
5. 分析报告

```python
from modules.stress_advanced import IntelligentStressTest

tester = IntelligentStressTest("http://example.com")
result = await tester.auto_test()

print(result['analysis']['bottleneck_type'])
print(result['analysis']['suggestions'])
```

### 3. 容量极限测试 (capacity)

逐步增加负载，找到系统崩溃点：

```python
from modules.stress_advanced import IntelligentStressTest

tester = IntelligentStressTest("http://example.com")
result = await tester.find_max_capacity()

print(f"最大 QPS: {result['max_qps']}")
print(f"最佳并发数: {result['best_concurrent']}")
```

## 抗压等级评估

系统会根据综合指标评估抗压等级：

| 等级 | QPS | 响应时间 | 错误率 | 评分 |
|------|-----|----------|--------|------|
| 优秀 | > 1000 | < 100ms | < 0.1% | 80+ |
| 良好 | 500-1000 | < 200ms | < 1% | 60-79 |
| 一般 | 100-500 | < 500ms | < 5% | 40-59 |
| 较差 | 50-100 | < 1000ms | < 10% | 20-39 |
| 危险 | < 50 | > 1000ms | > 10% | < 20 |

## 性能瓶颈分析

系统自动识别 6 种常见瓶颈：

### 1. CPU 瓶颈
**特征**: 响应时间随负载线性增长
**建议**: 增加 CPU、优化代码、启用缓存

### 2. 数据库瓶颈
**特征**: 响应时间波动大，P99 远高于 P50
**建议**: 检查慢查询、添加索引、增大连接池

### 3. 网络瓶颈
**特征**: 响应时间稳定但较长
**建议**: 检查带宽、启用压缩、使用 CDN

### 4. 连接数瓶颈
**特征**: 高并发下错误率飙升
**建议**: 增加最大连接数、启用连接复用

### 5. 内存瓶颈
**特征**: 响应时间逐渐增加
**建议**: 增加内存、优化内存使用

### 6. 带宽瓶颈
**特征**: 吞吐量达到上限
**建议**: 升级带宽、启用压缩、CDN 分发

## Web API 端点

### POST /api/stress

创建压力测试任务（异步）：

```bash
curl -X POST http://localhost:5000/api/stress \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://example.com",
    "mode": "quick",
    "concurrent": 10,
    "duration": 10
  }'
```

响应：
```json
{
  "test_id": "abc12345",
  "status": "created"
}
```

### GET /api/stress/{test_id}

获取测试状态和结果：

```bash
curl http://localhost:5000/api/stress/abc12345
```

### POST /api/stress/quick

快速测试（同步，直接返回结果）：

```bash
curl -X POST http://localhost:5000/api/stress/quick \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://example.com",
    "concurrent": 10,
    "duration": 10
  }'
```

## 高级配置

```python
from modules.stress_test import StressTestConfig, StressTester

config = StressTestConfig(
    target_url="http://example.com",
    
    # 并发配置
    concurrent_users=50,      # 并发用户数
    max_concurrent=200,       # 最大并发数
    ramp_up_time=20,          # 爬坡时间（秒）
    duration=60,              # 持续时间（秒）
    
    # 请求配置
    method="GET",             # HTTP 方法
    timeout=30,               # 请求超时（秒）
    think_time=0.5,           # 思考时间（秒）
    
    # 测试模式
    test_mode="concurrent",   # concurrent, throughput, spike
    
    # 高级选项
    verify_ssl=False,
    follow_redirects=True,
    
    # 停止条件
    stop_on_error=False,
    max_error_rate=50.0,      # 最大错误率
)

tester = StressTester(config)

# 设置进度回调
async def on_progress(phase, current, total):
    print(f"{phase}: {current}/{total}")

tester.on_progress = on_progress

# 运行测试
metrics = await tester.run()
```

## 测试模式详解

### 1. 并发测试 (concurrent)

模拟固定数量的并发用户：
- 逐步爬坡到目标并发数
- 持续运行指定时间
- 适合测试稳定负载

### 2. 吞吐量测试 (throughput)

以目标 QPS 发送请求：
- 严格控制请求速率
- 测试系统吞吐能力
- 适合容量规划

### 3. 峰值测试 (spike)

模拟流量突增：
- 正常负载 → 突然高峰 → 恢复
- 测试系统弹性
- 适合测试突发事件应对

## 测试报告示例

```
# 网站压力测试报告

## 测试概述
- 测试时间: 2026-03-22 12:30:00
- 抗压等级: 良好
- QPS: 523.45
- 平均响应时间: 156.23 ms
- 错误率: 0.85%

## 响应时间分布
| 指标 | 值 |
|------|------|
| 最小 | 45.23 ms |
| P50 | 120.45 ms |
| P90 | 289.67 ms |
| P95 | 345.12 ms |
| P99 | 567.89 ms |
| 最大 | 1234.56 ms |

## 瓶颈分析
类型: 数据库瓶颈
置信度: 65%
描述: 响应时间波动大，可能是数据库查询慢

## 优化建议
1. 检查慢查询日志
2. 添加数据库索引
3. 增大数据库连接池
4. 考虑读写分离
```

## 最佳实践

### 1. 测试前准备
- 确认目标网站允许测试
- 通知相关运维人员
- 选择低峰期进行大规模测试

### 2. 测试策略
- 从小并发开始，逐步增加
- 观察错误率和响应时间
- 记录每个阶段的指标

### 3. 结果分析
- 关注 P95、P99 响应时间
- 分析错误类型和分布
- 结合监控系统数据

### 4. 持续测试
- 建立性能基准
- 定期回归测试
- 对比历史数据

## 注意事项

1. **合法合规**: 仅测试自己拥有的或有授权的系统
2. **资源消耗**: 高并发测试会消耗大量本地资源
3. **目标影响**: 可能影响目标网站正常服务
4. **网络因素**: 测试结果受网络环境影响

## 故障排查

### 连接超时
```
- 检查目标是否可达
- 增加请求超时时间
- 检查防火墙设置
```

### 错误率过高
```
- 降低并发数
- 检查目标服务状态
- 查看详细错误信息
```

### 本地资源不足
```
- 减少并发数
- 增加请求间隔
- 关闭其他程序
```
