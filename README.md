<div align="center">

# 🔍 AutoRecon

**自动化信息收集框架 | Automated Reconnaissance Framework**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL%20v3-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/zhang123999-qq/AutoRecon?style=social)](https://github.com/zhang123999-qq/AutoRecon/stargazers)

[English](#english) | [中文文档](#中文文档)

</div>

---

## 中文文档

### 🎯 简介

AutoRecon 是一个模块化的自动化信息收集框架，专为安全研究人员和渗透测试人员设计。支持子域名枚举、端口扫描、指纹识别、CDN检测等多种功能。

### ✨ 特性

- 🔧 **模块化架构** - 10+ 独立模块，按需使用
- 📊 **HTML报告** - 自动生成可视化报告
- 🎨 **彩色日志** - 清晰的终端输出
- ⚡ **并发执行** - 高效的异步处理
- 🔌 **工具集成** - 支持 subfinder, nmap, httpx 等工具

### 📦 模块列表

| 模块 | 功能 |
|------|------|
| `subdomain` | 子域名枚举 |
| `port` | 端口扫描 |
| `directory` | 目录扫描 |
| `fingerprint` | 指纹识别 |
| `whois` | Whois 查询 |
| `icp` | 备案查询 |
| `cdn` | CDN 检测 |
| `sensitive` | 敏感信息检测 |
| `takeover` | 子域名接管检测 |
| `waf` | WAF 检测与绕过 |

### 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/zhang123999-qq/AutoRecon.git
cd AutoRecon

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp config.example.py config.py

# 运行
python recon.py -d example.com
```

### 📋 依赖

- Python 3.8+
- subfinder (可选)
- nmap (可选)
- httpx (可选)

### 📝 使用示例

```bash
# 基础扫描
python recon.py -d target.com

# 指定模块
python recon.py -d target.com -m subdomain,port,fingerprint

# 完整扫描
python recon.py -d target.com --full

# 生成报告
python recon.py -d target.com --report
```

### 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 📄 许可证

[GPL-3.0 License](LICENSE)

---

## English

### 🎯 Introduction

AutoRecon is a modular automated reconnaissance framework designed for security researchers and penetration testers. It supports subdomain enumeration, port scanning, fingerprinting, CDN detection, and more.

### ✨ Features

- 🔧 **Modular Architecture** - 10+ independent modules
- 📊 **HTML Reports** - Auto-generated visual reports
- 🎨 **Colored Logs** - Clear terminal output
- ⚡ **Concurrent Execution** - Efficient async processing
- 🔌 **Tool Integration** - Supports subfinder, nmap, httpx

### 🚀 Quick Start

```bash
# Clone
git clone https://github.com/zhang123999-qq/AutoRecon.git
cd AutoRecon

# Install dependencies
pip install -r requirements.txt

# Run
python recon.py -d example.com
```

### 📄 License

[GPL-3.0 License](LICENSE)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

Made with ❤️ by [zhang123999-qq](https://github.com/zhang123999-qq)

</div>
