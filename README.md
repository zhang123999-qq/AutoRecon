# 🔍 AutoRecon v3.2

**异步信息收集框架 | Async Reconnaissance Framework**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Async](https://img.shields.io/badge/Async-aiohttp-green)](https://docs.aiohttp.org/)
[![Web UI](https://img.shields.io/badge/Web_UI-FastAPI-orange)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-GPL%20v3-green.svg)](LICENSE)

---

## ✨ v3.2 新特性

- 🚀 **异步架构** - 基于 asyncio，性能提升 10x+
- 🌐 **Web UI** - 全新 Web 界面，实时查看扫描进度
- 📊 **HTML 报告** - 自动生成可视化扫描报告
- 🔒 **漏洞扫描** - 检测敏感文件泄露、SQL注入、XSS等
- 💉 **SQLMap 集成** - 专业 SQL 注入检测
- 📈 **高级压力测试** - 阶梯测试、浸泡测试、峰值测试、场景脚本
- 🔌 **WebSocket 实时推送** - 实时进度广播
- 📚 **扩展字典** - 5000+ 子域名前缀，200+ 指纹
- 💾 **智能缓存** - DNS 和 HTTP 结果缓存

---

## 📦 模块列表

| 模块 | 功能 | 状态 |
|------|------|------|
| `subdomain` | 子域名收集 | ✅ |
| `port` | 端口扫描 | ✅ |
| `cdn` | CDN 检测 | ✅ |
| `fingerprint` | 指纹识别 (200+) | ✅ |
| `sensitive` | 敏感信息检测 | ✅ |
| `vuln` | 漏洞扫描 | ✅ |
| `sqli` | SQLMap 注入扫描 | ✅ |
| `stress` | 压力测试 | ✅ |
| `stress_realtime` | WebSocket 实时推送 | ✅ 新增 |
| `stress_scenario` | 场景脚本 | ✅ 新增 |
| `stress_modes` | 高级测试模式 | ✅ 新增 |

---

## 🚀 快速开始

### 安装依赖

```bash
# 核心依赖
pip install aiohttp dnspython jinja2

# Web UI 依赖
pip install fastapi uvicorn websockets

# SQLMap 集成（可选）
pip install sqlmap
```

### 命令行模式

```bash
# 快速扫描
python recon_v3.py example.com

# 全模块扫描
python recon_v3.py example.com -m all

# 漏洞扫描
python recon_v3.py example.com -m vuln,sqli

# 高并发
python recon_v3.py example.com -t 100
```

### Web UI 模式

```bash
# 启动 Web 服务
python web/run.py

# 或使用 uvicorn
uvicorn web.app:app --host 0.0.0.0 --port 5000
```

访问 `http://127.0.0.1:5000` 即可使用 Web 界面。

**Web UI 功能：**
- 📊 实时扫描进度（WebSocket）
- 📜 扫描日志实时展示
- 📁 历史记录管理
- 📑 报告下载与查看
- 📈 **压力测试面板** - 配置并发、时长，查看抗压等级
- 🎨 深色主题界面

---

## 📈 压力测试

### Web UI 使用

1. 点击"压力测试"标签页
2. 输入目标 URL
3. 选择测试模式：
   - **快速测试** - 简单评估，适合初步了解
   - **智能测试** - 自动递增并发，生成分析报告
   - **容量极限** - 找到系统崩溃点
4. 配置并发数和持续时间
5. 点击"开始测试"

### 抗压等级

| 等级 | QPS | 响应时间 | 错误率 |
|------|-----|----------|--------|
| 优秀 | > 1000 | < 100ms | < 0.1% |
| 良好 | 500-1000 | < 200ms | < 1% |
| 一般 | 100-500 | < 500ms | < 5% |
| 较差 | 50-100 | < 1000ms | < 10% |
| 危险 | < 50 | > 1000ms | > 10% |

### 代码调用

```python
from modules.stress_test import QuickStressTest
import asyncio

async def test():
    result = await QuickStressTest.test_url(
        "http://example.com",
        concurrent=50,
        duration=30
    )
    print(f"QPS: {result['metrics']['throughput']['qps']}")
    print(f"抗压等级: {result['metrics']['stress_level']}")

asyncio.run(test())
```

---

## 💉 SQLMap 集成

### 功能特性

- 自动发现带参数的 URL
- 批量并发扫描
- 结果自动解析
- 支持 REST API 和命令行两种模式

### 代码调用

```python
from modules.sqlmap_integration import SQLMapCommandLine
import asyncio

async def scan():
    client = SQLMapCommandLine()
    result = await client.scan_url("http://example.com/page?id=1")
    print(f"存在漏洞: {result.vulnerable}")
    print(f"数据库类型: {result.dbms}")

asyncio.run(scan())
```

---

## 📊 性能对比

| 指标 | v2.3 | v3.0 |
|------|------|------|
| 架构 | 线程池 | asyncio |
| 并发速度 | ~50/s | **600-700/s** |
| 子域名字典 | 40+ | **5000+** |
| 指纹库 | 30+ | **200+** |
| Web UI | ❌ | ✅ |
| 压力测试 | ❌ | ✅ |
| SQLMap | ❌ | ✅ |

---

## 📁 项目结构

```
recon_tool/
├── recon_v3.py          # CLI 主程序
├── web/                  # Web UI
│   ├── app.py           # FastAPI 后端
│   ├── run.py           # 启动脚本
│   ├── templates/       # HTML 模板
│   └── static/          # 静态资源
├── modules/              # 扫描模块
│   ├── async_subdomain.py    # 子域名收集
│   ├── vuln_scanner.py       # 漏洞扫描
│   ├── sqlmap_integration.py # SQLMap 集成
│   ├── stress_test.py        # 压力测试
│   └── ...
├── core/                 # 核心引擎
├── data/                 # 数据文件
│   ├── fingerprints.py  # Web 指纹库
│   └── wordlists.py     # 字典文件
├── docs/                 # 文档
└── reports/              # 扫描报告
```

---

## 📖 API 文档

启动 Web 服务后，访问 `/docs` 查看 Swagger API 文档。

### 主要 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/scan` | POST | 创建扫描任务 |
| `/api/scan/{id}` | GET | 获取扫描状态 |
| `/api/stress/quick` | POST | 快速压力测试 |
| `/api/sqlmap` | POST | SQLMap 扫描 |
| `/ws/{scan_id}` | WebSocket | 实时进度 |

---

## 📄 许可证

[GPL-3.0 License](LICENSE)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ by [zhang123999-qq](https://github.com/zhang123999-qq)
