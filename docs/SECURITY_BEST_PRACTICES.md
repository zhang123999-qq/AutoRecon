# AutoRecon 安全最佳实践

本文档提供使用 AutoRecon 进行安全测试的最佳实践指南。

---

## 🎯 目标受众

- 渗透测试工程师
- 安全研究人员
- DevOps 工程师
- 企业安全团队

---

## 📋 测试前准备

### 1. 获取授权

**必须获得书面授权！** 授权文件应包含：

- 测试目标范围
- 测试时间窗口
- 允许的测试类型
- 联系人信息
- 紧急情况处理流程

### 2. 了解目标

```bash
# 确认目标所有权
whois example.com

# 检查是否为第三方托管
dig example.com +short
```

### 3. 评估风险

| 风险等级 | 说明 | 建议 |
|---------|------|------|
| 低 | 静态网站，无数据库 | 可正常测试 |
| 中 | 动态网站，有用户数据 | 避免生产数据操作 |
| 高 | 金融、医疗等敏感系统 | 在测试环境进行 |

---

## 🔧 配置优化

### 生产环境扫描

```bash
# 低影响配置
export MAX_THREADS=20
export MAX_RATE=10
export TIMEOUT_TOTAL=60

python recon_v3.py target.com --yes
```

### 性能测试

```bash
# 高并发配置（需评估目标承受能力）
export MAX_THREADS=100
export MAX_RATE=50

python recon_v3.py target.com -t 100 --yes
```

### 内网扫描

```bash
# 内网扫描配置
export SSRF_PROTECTION=false
export ALLOW_PRIVATE_IPS=true
export MAX_THREADS=50

python recon_v3.py 192.168.1.0/24 --yes
```

---

## 🛡️ 风险控制

### 1. 速率控制

**问题：** 扫描过快可能导致目标服务不可用

**解决方案：**
```bash
# 限制速率
export MAX_RATE=20  # 每秒最多 20 个请求
export MAX_BURST=50  # 最大突发 50 个请求
```

### 2. 时间窗口

**建议：** 在业务低峰期进行测试

```bash
# 使用 cron 在指定时间运行
# 每天凌晨 2 点执行
0 2 * * * /path/to/autorecon/scan.sh
```

### 3. 监控告警

**建议：** 设置监控，在出现异常时及时停止

```python
import asyncio
from modules.stress_test import QuickStressTest

async def scan_with_monitoring():
    result = await QuickStressTest.test_url(
        "https://target.com",
        concurrent=10,
        duration=30
    )
    
    # 检查错误率
    if result['metrics']['errors']['error_rate'] > 0.05:
        print("警告：错误率超过 5%，建议停止测试")
    
    return result
```

---

## 🚨 紧急情况处理

### 扫描导致服务不可用

1. **立即停止扫描**
   ```bash
   # Ctrl+C 或 kill 进程
   pkill -f recon_v3
   ```

2. **联系目标负责人**
   - 说明情况
   - 提供扫描时间、范围
   - 配合排查问题

3. **记录事件**
   - 扫描配置
   - 时间点
   - 响应时间
   - 恢复时间

### 发现严重漏洞

1. **不要公开披露**
2. **加密报告** 发送给授权方
3. **提供修复建议**
4. **跟进修复进度**

---

## 📊 报告与记录

### 扫描报告结构

```
reports/
├── target.com_20260414_200500.json
├── target.com_20260414_200500.html
└── target.com_20260414_200500/
    ├── subdomains.txt
    ├── vulnerabilities.json
    └── screenshots/
```

### 报告内容

1. **执行摘要**
   - 扫描范围
   - 发现概要
   - 风险等级

2. **详细发现**
   - 每个漏洞的详情
   - 复现步骤
   - 修复建议

3. **附录**
   - 扫描配置
   - 工具版本
   - 时间戳

---

## 🔐 数据安全

### 敏感数据处理

```python
# 不要在报告中保存敏感数据
def sanitize_result(result):
    """清理敏感信息"""
    sensitive_keys = ['password', 'token', 'api_key', 'secret']
    for key in sensitive_keys:
        if key in result:
            result[key] = '***REDACTED***'
    return result
```

### 报告存储

```bash
# 加密存储
gpg -c report.json

# 或使用加密压缩
zip -e -P "your-password" report.zip report.json
```

### 报告销毁

```bash
# 安全删除
shred -u report.json

# 或使用 rm -P (macOS)
rm -P report.json
```

---

## 🌐 多目标扫描

### 批量扫描

```python
import asyncio
from recon_v3 import ReconToolV3

async def batch_scan(targets):
    """批量扫描多个目标"""
    results = {}
    for target in targets:
        tool = ReconToolV3(target, threads=20)
        results[target] = await tool.run_all()
        
        # 每个目标之间间隔
        await asyncio.sleep(60)
    
    return results

# 运行
targets = ['example1.com', 'example2.com', 'example3.com']
results = asyncio.run(batch_scan(targets))
```

### 分阶段扫描

```bash
# 阶段1：信息收集
python recon_v3.py target.com -m subdomain,port,cdn

# 阶段2：漏洞扫描（在信息收集完成后）
python recon_v3.py target.com -m vuln,sqli

# 阶段3：深度测试（在漏洞确认后）
# 手动验证或使用专业工具
```

---

## 📈 性能优化

### 并发调优

```python
# 根据目标响应时间调整并发数

# 响应时间 < 100ms：可使用高并发
threads = 100

# 响应时间 100-500ms：中等并发
threads = 50

# 响应时间 > 500ms：低并发
threads = 20
```

### 缓存利用

```python
# 启用缓存避免重复请求
tool = ReconToolV3(
    target="example.com",
    use_cache=True  # 默认启用
)

# 缓存有效期 30 分钟
cache = AsyncCache(ttl=1800)
```

---

## 📚 参考资源

### 法律法规

- [中华人民共和国网络安全法](http://www.npc.gov.cn/npc/xinwen/2016-11/07/content_2001605.htm)
- [网络安全审查办法](http://www.cac.gov.cn/2022-01/04/c_1642890355404471.htm)
- [计算机信息网络国际联网安全保护管理办法](http://www.gov.cn/gongbao/content/2011/content_1860894.htm)

### 行业标准

- OWASP Testing Guide
- NIST Cybersecurity Framework
- ISO 27001

### 技术资源

- [PortSwigger Web Security Academy](https://portswigger.net/web-security)
- [HackerOne Vulnerability Disclosure Guidelines](https://www.hackerone.com/disclosure-guidelines)
- [OWASP Top 10](https://owasp.org/Top10/)

---

## ⚖️ 合规检查清单

扫描前确认：

- [ ] 已获得书面授权
- [ ] 授权范围明确
- [ ] 测试时间已确认
- [ ] 紧急联系人已知
- [ ] 扫描配置已优化
- [ ] 监控已设置
- [ ] 报告模板已准备

扫描中监控：

- [ ] 错误率 < 5%
- [ ] 响应时间正常
- [ ] 无异常告警

扫描后处理：

- [ ] 报告已生成
- [ ] 敏感数据已清理
- [ ] 结果已加密存储
- [ ] 漏洞已报告

---

**记住：安全测试的目的是发现问题并帮助修复，而不是造成破坏。**
