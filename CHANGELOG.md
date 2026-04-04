# AutoRecon 更新日志

所有重要的更改都将记录在此文件中。

## [3.2.0] - 2026-04-04

### 新增功能 ✨

#### 压力测试增强
- **WebSocket 实时推送** (`modules/stress_realtime.py`) - 实时进度广播，替代轮询
- **测试场景脚本** (`modules/stress_scenario.py`) - YAML 场景定义，支持复杂用户行为
- **高级测试模式** (`modules/stress_modes.py`) - 阶梯测试、浸泡测试、峰值测试、混合负载

#### 新增模块
| 模块 | 功能 |
|------|------|
| `stress_realtime` | WebSocket 实时推送 |
| `stress_scenario` | YAML 场景脚本 |
| `stress_modes` | 高级测试模式 |

### 测试模式

| 模式 | 说明 |
|------|------|
| `staircase` | 阶梯测试 - 逐步增加并发 |
| `soak` | 浸泡测试 - 长时间稳定性 |
| `spike` | 峰值测试 - 突发流量 |
| `mixed` | 混合负载 - 读写混合 |

---

## [3.1.0] - 2026-03-24

### 新增功能 ✨

#### 核心功能
- **插件系统** (`core/plugin_system.py`) - 动态加载自定义扫描模块，支持启用/禁用和优先级执行
- **持久化缓存** (`core/persistent_cache.py`) - SQLite/Redis 后端，避免重复扫描
- **自适应并发** (`core/adaptive_concurrency.py`) - 根据响应时间动态调整并发数，错误率过高自动降速
- **PDF 报告生成** (`core/pdf_report.py`) - 生成专业的安全扫描报告

#### 扫描模块
- **SSL 证书分析** (`modules/ssl_certificate.py`) - 从证书透明度日志发现子域名，检测证书安全问题
- **GitHub 信息泄露** (`modules/github_leaks.py`) - 检测 GitHub 仓库中的敏感信息泄露（API Key、密码等）
- **JavaScript 分析** (`modules/js_analyzer.py`) - 从 JS 文件中提取 URL、API 端点、敏感信息

### 部署支持 🐳
- **Docker 化** - 添加 `Dockerfile` 和 `docker-compose.yml`，支持容器化部署
- **docker-compose** - 包含主服务、Web UI 和可选的 Redis 缓存

### 开发工具 🛠️
- **pyproject.toml** - 现代化依赖管理，支持可选依赖分组
- **单元测试** (`tests/test_core.py`) - 核心模块测试覆盖

### 性能优化 ⚡

| 优化项 | 效果 |
|--------|------|
| 持久化缓存 | 重复扫描 -90% |
| 自适应并发 | 扫描效率 +30% |
| Docker 化 | 部署时间 -80% |

### 文件结构

```
recon/
├── pyproject.toml              # 新增：现代依赖管理
├── Dockerfile                  # 新增：Docker 镜像
├── docker-compose.yml          # 新增：容器编排
├── core/
│   ├── plugin_system.py       # 新增：插件系统
│   ├── persistent_cache.py    # 新增：持久化缓存
│   ├── adaptive_concurrency.py # 新增：自适应并发
│   └── pdf_report.py          # 新增：PDF 报告
├── modules/
│   ├── ssl_certificate.py     # 新增：SSL 分析
│   ├── github_leaks.py        # 新增：GitHub 泄露
│   └── js_analyzer.py         # 新增：JS 分析
└── tests/
    └── test_core.py           # 新增：单元测试
```

---

## [3.0.0] - 2026-03-XX

### 重大更新
- 全新异步架构，性能提升 10x+
- asyncio + aiohttp 核心引擎
- 17 个扫描模块
- FastAPI Web UI
- 代理池支持
- 智能重试机制

### 扫描模块
- 子域名收集 (async_subdomain)
- 端口扫描 (port_scanner)
- CDN 检测 (cdn_detector)
- 指纹识别 (fingerprint) - 200+ 指纹
- 目录扫描 (dir_scanner)
- 敏感文件检测 (sensitive)
- 漏洞扫描 (vuln_scanner)
- SQL 注入检测 (sqli_scanner)
- SQLMap 集成 (sqlmap_integration)
- 压力测试 (stress_test, stress_advanced)
- WAF 绕过 (waf_bypass)
- 子域接管 (takeover)
- WHOIS 查询 (whois_query)

---

## 版本说明

- **主版本号 (Major)**: 不兼容的 API 变更
- **次版本号 (Minor)**: 向后兼容的功能新增
- **修订号 (Patch)**: 向后兼容的问题修复
