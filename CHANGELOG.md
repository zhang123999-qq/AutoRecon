# AutoRecon 更新日志

所有重要的更改都将记录在此文件中。

## [3.3.1] - 2026-04-15

### 源码质量优化 📊

#### 质量评分提升
| 指标 | 初始 | 最终 | 提升 |
|------|------|------|------|
| 综合评分 | 6.2/10 | 8.6/10 | +2.4 |
| 警告数量 | 54 | 8 | -46 |
| 类型注解 | 0.0/10 | 6.1/10 | +6.1 |
| 文档字符串 | 5.4/10 | 6.5/10 | +1.1 |
| 代码复杂度 | 5.5/10 | 6.7/10 | +1.2 |

#### 代码修复
| 修复项 | 数量 | 说明 |
|--------|------|------|
| 裸 except 替换 | 26处 | 改为具体异常类型 |
| 复杂度重构 | 5个函数 | 表驱动模式替代多层 if-elif |
| 类型注解 | 核心模块 | utils, logger, base, report, app |
| 文档字符串 | 数据模型 | ScanRequest, ScanStatus, ConnectionManager 等 |
| 测试修复 | 6个 | SQLiteCache 测试缺少 await |

#### 重构的复杂函数
| 文件 | 函数 | 复杂度变化 |
|------|------|------------|
| `dir_scanner.py` | `_classify_sensitive_path` | 18→4 |
| `stress_advanced.py` | `PerformanceAnalyzer.analyze` | 22→5 |
| `stress_advanced.py` | `calculate_score` | 16→3 |
| `stress_test.py` | `_calculate_stress_level` | 19→3 |
| `code_quality_check.py` | `check_security` | 19→5 |

#### 测试验证
- 69 个测试全部通过
- 安全修复测试：12 passed
- SSRF 防护测试：18 passed
- 输入验证测试：19 passed
- 核心模块测试：20 passed

---

## [3.3.0] - 2026-04-14

### 安全加固 🔒

#### P0 - 关键安全修复
| 修复项 | 说明 |
|--------|------|
| 免责声明 | 启动时显示法律声明和授权确认 |
| `--yes` 参数 | 跳过授权确认（自动化场景） |
| 命令注入防护 | `validate_url()`, `validate_parameter()` 函数 |
| SSRF 防护 | IPv4/IPv6 黑名单 + DNS 检查，防止内网探测 |
| Web API 认证 | Bearer Token 认证，支持多 API Key |

#### P1 - 功能增强
| 功能 | 说明 |
|------|------|
| 测试覆盖 | 48 个测试用例全部通过 |
| 速率限制 | `MAX_RATE=100`, `MAX_BURST=200` 防止滥用 |
| 日志脱敏 | `sanitize_message()` 自动过滤敏感信息 |
| Pre-commit Hooks | 代码提交前自动检查 |

#### P2 - 架构优化
| 优化项 | 说明 |
|--------|------|
| 配置重构 | dataclass + 环境变量，支持 `.env` 文件 |
| 类型注解 | `py.typed` + `mypy.ini`，支持静态类型检查 |
| IPv6 Bug 修复 | `validate_target()` 正确处理 IPv6 地址格式 |
| validators 可选 | 内置 fallback 验证函数，减少依赖 |

#### P3 - 文档完善
| 文档 | 说明 |
|------|------|
| `SECURITY.md` | 安全策略和漏洞报告指南 |
| `CONTRIBUTING.md` | 贡献指南和开发规范 |
| `SECURITY_BEST_PRACTICES.md` | 安全最佳实践文档 |
| `.env.example` | 环境变量配置示例 |

### Web UI 改进 🌐

| 改进 | 说明 |
|------|------|
| Bootstrap 本地化 | 无需 CDN，离线可用 |
| CORS 配置修复 | 正确处理跨域请求 |
| 字体路径修复 | Bootstrap Icons 本地化 |

### 新增文件
```
├── .env.example              # 环境变量示例
├── .pre-commit-config.yaml   # Pre-commit Hooks
├── SECURITY.md               # 安全文档
├── CONTRIBUTING.md           # 贡献指南
├── mypy.ini                  # MyPy 配置
├── py.typed                  # 类型标记
├── pytest.ini                # Pytest 配置
├── requirements-dev.txt      # 开发依赖
├── docs/SECURITY_BEST_PRACTICES.md
├── tests/test_async_engine.py
├── tests/test_input_validation.py
├── tests/test_ssrf_protection.py
├── tests/test_web_api.py
└── web/static/vendor/        # Bootstrap 本地资源
```

### 安全黑名单

**IPv4 黑名单 (8 个网段):**
- `127.0.0.0/8` - 本地回环
- `10.0.0.0/8` - 私有网络 A
- `172.16.0.0/12` - 私有网络 B
- `192.168.0.0/16` - 私有网络 C
- `169.254.0.0/16` - 链路本地
- `0.0.0.0/8` - 当前网络
- `224.0.0.0/4` - 组播地址
- `240.0.0.0/4` - 保留地址

**IPv6 黑名单 (6 个网段):**
- `::1/128` - 本地回环
- `fc00::/7` - 唯一本地地址
- `fe80::/10` - 链路本地
- `ff00::/8` - 组播地址
- `::/128` - 未指定地址
- `::ffff:0:0/96` - IPv4 映射地址

---

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
