# sqlmap 集成说明

## 概述

AutoRecon v3.0 集成了 sqlmap 进行自动化的 SQL 注入检测。支持两种使用方式：

1. **命令行模式** - 直接调用 sqlmap 命令
2. **REST API 模式** - 启动 sqlmap API 服务器

## 安装要求

```bash
# 安装 sqlmap
pip install sqlmap

# 验证安装
sqlmap --version
```

## 使用方式

### 1. 命令行模式（推荐）

最简单的方式，直接调用 sqlmap 命令行工具：

```python
from modules.sqlmap_integration import SQLMapCommandLine
import asyncio

async def scan():
    client = SQLMapCommandLine()
    result = await client.scan_url(
        "http://example.com/page?id=1",
        options={
            "level": 2,
            "risk": 2,
            "random-agent": True
        },
        timeout=180
    )
    
    print(f"存在漏洞: {result.vulnerable}")
    print(f"数据库类型: {result.dbms}")
    print(f"注入参数: {result.parameter}")

asyncio.run(scan())
```

### 2. REST API 模式

适合需要批量扫描或需要更精细控制的场景：

```python
from modules.sqlmap_integration import SQLMapRESTClient, start_sqlmap_api_server
import asyncio

async def scan_with_api():
    # 1. 启动 API 服务器（只需启动一次）
    server = await start_sqlmap_api_server(port=8775)
    
    # 2. 创建客户端
    async with SQLMapRESTClient(port=8775) as client:
        result = await client.scan_url(
            "http://example.com/page?id=1",
            timeout=180
        )
        
        print(f"存在漏洞: {result.vulnerable}")
    
    # 3. 关闭服务器
    server.terminate()

asyncio.run(scan_with_api())
```

### 3. 自动扫描模式

自动发现 URL 并扫描：

```python
from modules.sqlmap_integration import SQLMapAutoScanner
import asyncio

async def auto_scan():
    scanner = SQLMapAutoScanner(
        target="example.com",
        threads=5,
        use_api=False,  # 使用命令行模式
        timeout=180
    )
    
    results = await scanner.run_full_scan()
    
    for r in results:
        if r.vulnerable:
            print(f"漏洞: {r.url} - {r.parameter}")

asyncio.run(auto_scan())
```

## sqlmap 选项说明

常用选项：

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `level` | 扫描级别 (1-5) | 1 |
| `risk` | 风险级别 (1-3) | 1 |
| `technique` | 注入技术 (BEUSTQ) | BEUST |
| `threads` | 线程数 | 3 |
| `timeout` | 请求超时（秒） | 30 |
| `random-agent` | 随机 User-Agent | True |
| `batch` | 非交互模式 | True |
| `tamper` | 绕过脚本 | - |
| `dbms` | 指定数据库类型 | 自动检测 |

注入技术代码：
- `B` - Boolean-based blind
- `E` - Error-based
- `U` - UNION query-based
- `S` - Stacked queries
- `T` - Time-based blind
- `Q` - Inline queries

## Web API 端点

### POST /api/sqlmap

单独的 sqlmap 扫描接口：

```bash
curl -X POST http://localhost:5000/api/sqlmap \
  -H "Content-Type: application/json" \
  -d '{"url": "http://example.com/page?id=1", "timeout": 180}'
```

响应：
```json
{
  "url": "http://example.com/page?id=1",
  "vulnerable": true,
  "parameter": "id",
  "injection_type": "boolean-based blind",
  "dbms": "MySQL",
  "database": "testdb",
  "user": "root@localhost",
  "payload": "1' AND 1=1--"
}
```

### GET /api/sqlmap/status

检查 sqlmap 是否可用：

```bash
curl http://localhost:5000/api/sqlmap/status
```

响应：
```json
{
  "available": true,
  "path": "/usr/bin/sqlmap"
}
```

## 绕过技术

### tamper 脚本

```python
result = await client.scan_url(
    url,
    options={
        "tamper": ["space2comment", "between"]  # 绕过空格过滤
    }
)
```

常用 tamper 脚本：
- `space2comment` - 空格替换为注释
- `between` - 用 NOT BETWEEN 替代 >
- `charencode` - 字符编码
- `base64encode` - Base64 编码
- `equaltolike` - = 替换为 LIKE

## 性能优化

1. **降低扫描级别** - `level=1, risk=1` 适合快速扫描
2. **限制线程数** - sqlmap 本身并发，无需过多线程
3. **指定数据库类型** - 如果已知，可以加速扫描
4. **限制超时** - 防止长时间阻塞

## 注意事项

1. **法律合规** - 仅在授权范围内使用
2. **网络稳定性** - 目标网站需要可访问
3. **WAF 绕过** - 可能需要 tamper 脚本
4. **扫描时间** - 深度扫描可能需要几分钟到几小时

## 错误排查

### sqlmap not found

```bash
# 检查 sqlmap 路径
which sqlmap
sqlmap --version

# 如果未安装
pip install sqlmap
```

### 连接失败

```python
# 使用代理
result = await client.scan_url(
    url,
    options={
        "proxy": "http://127.0.0.1:8080"
    }
)
```

### 超时问题

```python
# 增加超时时间
result = await client.scan_url(url, timeout=300)
```

## 示例：完整扫描流程

```python
import asyncio
from modules.sqlmap_integration import SQLMapAutoScanner

async def main():
    # 创建扫描器
    scanner = SQLMapAutoScanner(
        target="target-site.com",
        threads=5,
        timeout=180
    )
    
    # 运行扫描
    results = await scanner.run_full_scan()
    
    # 获取结果
    for result in results:
        if result.vulnerable:
            print(f"漏洞发现:")
            print(f"  URL: {result.url}")
            print(f"  参数: {result.parameter}")
            print(f"  类型: {result.injection_type}")
            print(f"  数据库: {result.dbms}")
            print(f"  Payload: {result.payload}")
            print()
    
    # 导出结果
    import json
    with open("sqli_results.json", "w") as f:
        json.dump(scanner.get_results(), f, indent=2)

asyncio.run(main())
```

## 集成到 AutoRecon

sqlmap 已集成到 AutoRecon 的完整扫描流程中：

1. 选择"SQL注入"模块
2. 输入目标域名
3. 点击"开始扫描"
4. 系统自动：
   - 发现带参数的 URL
   - 使用 sqlmap 检测每个 URL
   - 报告发现的漏洞
