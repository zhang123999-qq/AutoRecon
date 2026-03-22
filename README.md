# 🔍 AutoRecon v3.0

**异步信息收集框架 | Async Reconnaissance Framework**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![Async](https://img.shields.io/badge/Async-aiohttp-green)](https://docs.aiohttp.org/)
[![License](https://img.shields.io/badge/License-GPL%20v3-green.svg)](LICENSE)

---

## ✨ v3.0 新特性

- 🚀 **异步架构** - 基于 asyncio，性能提升 10x+
- 📊 **HTML 报告** - 自动生成可视化扫描报告
- 🔒 **漏洞扫描** - 检测敏感文件泄露、SQL注入、XSS等
- 📚 **扩展字典** - 5000+ 子域名前缀，200+ 指纹
- 💾 **智能缓存** - DNS 和 HTTP 结果缓存
- 🎯 **多数据源** - DNS枚举、证书透明度、搜索引擎等

---

## 📦 模块列表

| 模块 | 功能 | 状态 |
|------|------|------|
| `subdomain` | 子域名收集 | ✅ |
| `port` | 端口扫描 | ✅ |
| `cdn` | CDN 检测 | ✅ |
| `fingerprint` | 指纹识别 (200+) | ✅ |
| `sensitive` | 敏感信息检测 | ✅ |
| `vuln` | 漏洞扫描 | ✅ 新增 |

---

## 🚀 快速开始

```bash
# 安装依赖
pip install aiohttp dnspython jinja2

# 快速扫描
python recon_v3.py example.com

# 全模块扫描
python recon_v3.py example.com -m all

# 漏洞扫描
python recon_v3.py example.com -m vuln

# 高并发
python recon_v3.py example.com -t 100
```

---

## 📊 性能对比

| 指标 | v2.3 | v3.0 |
|------|------|------|
| 架构 | 线程池 | asyncio |
| 并发速度 | ~50/s | **600-700/s** |
| 子域名字典 | 40+ | **5000+** |
| 指纹库 | 30+ | **200+** |
| 数据源 | 3个 | **5个** |

---

## 📝 输出示例

```
扫描摘要
-------------------------------------------------------
  子域名: 459 个
  开放端口: 5 个
  CDN: CloudFlare
  指纹: 8 个
  [!] 安全问题: 3 个 (高危: 1)
-------------------------------------------------------
```

---

## 📄 许可证

[GPL-3.0 License](LICENSE)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ by [zhang123999-qq](https://github.com/zhang123999-qq)
