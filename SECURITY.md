# Security Policy / 安全策略

## Supported Versions / 支持版本

| Version | Supported          |
| ------- | ------------------ |
| 3.2.x   | :white_check_mark: |
| < 3.0   | :x:                |

---

## ⚠️ 重要警告 / Important Warning

**本工具仅供授权的安全测试使用！**

未经授权对第三方系统进行扫描属于违法行为，可能违反：
- 中国《网络安全法》
- 中国《刑法》第285-287条（非法侵入计算机信息系统罪、非法获取计算机信息系统数据罪等）
- 其他国家/地区的计算机犯罪相关法律

使用者必须确保已获得目标系统所有者的**书面授权**。

---

## 🔒 安全特性

### 内置防护措施

| 特性 | 说明 | 配置 |
|------|------|------|
| **SSRF 防护** | 自动阻止对内网 IP 的请求 | `SSRF_PROTECTION=true` |
| **命令注入防护** | URL/参数输入严格验证 | 默认启用 |
| **速率限制** | 最大 100 req/s，防止 DoS | `MAX_RATE=100` |
| **日志脱敏** | 自动过滤敏感信息 | 默认启用 |
| **API 认证** | Bearer Token 认证 | `AUTH_ENABLED=true` |

### SSRF 防护详情

默认阻止访问以下 IP 段：

**IPv4：**
- `10.0.0.0/8` - 私有网络 A 类
- `172.16.0.0/12` - 私有网络 B 类
- `192.168.0.0/16` - 私有网络 C 类
- `127.0.0.0/8` - 本地回环
- `169.254.0.0/16` - 链路本地（含 AWS metadata 169.254.169.254）
- `0.0.0.0/8` - 当前网络
- `224.0.0.0/4` - 多播地址
- `240.0.0.0/4` - 保留地址

**IPv6：**
- `::1/128` - 本地回环
- `fc00::/7` - 唯一本地地址
- `fe80::/10` - 链路本地
- `ff00::/8` - 多播
- `::ffff:0:0/96` - IPv4 映射地址

### 内网扫描

如需扫描内网（仅限授权场景），设置环境变量：

```bash
export ALLOW_PRIVATE_IPS=true
export SSRF_PROTECTION=false  # 完全禁用 SSRF 防护
```

⚠️ **警告：禁用 SSRF 防护可能导致安全风险！**

---

## 🛡️ 安全配置建议

### 生产环境部署

```bash
# 1. 启用 API 认证
export AUTH_ENABLED=true
export API_KEYS="$(openssl rand -hex 32),$(openssl rand -hex 32)"

# 2. 配置 CORS
export ALLOWED_ORIGINS="https://your-domain.com"

# 3. 启用日志文件
export LOG_FILE=/var/log/autorecon/scan.log
export LOG_LEVEL=INFO

# 4. 限制并发
export MAX_THREADS=100
export MAX_RATE=50

# 5. SSL 配置
export VERIFY_SSL=true
```

### Docker 部署

```dockerfile
# 使用非 root 用户
USER app

# 只暴露必要端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s CMD curl -f http://localhost:5000/health || exit 1
```

### Nginx 反向代理

```nginx
# 限制请求速率
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    listen 443 ssl http2;
    
    # SSL 配置
    ssl_certificate /etc/ssl/certs/autorecon.crt;
    ssl_certificate_key /etc/ssl/private/autorecon.key;
    
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:5000;
    }
}
```

---

## 📝 日志安全

### 自动脱敏

日志模块自动过滤以下敏感信息：

- 密码：`password=***`
- API Key：`api_key=***`
- Token：`token=***`, `bearer ***`
- Cookie：`cookie=***`
- Secret：`secret=***`

### 日志访问控制

```bash
# 设置日志文件权限
chmod 600 /var/log/autorecon/scan.log
chown autorecon:autorecon /var/log/autorecon/scan.log
```

---

## 🔐 API 安全

### 认证方式

```bash
# 获取 API Key
API_KEY="your-secret-key-1"

# 请求示例
curl -H "Authorization: Bearer $API_KEY" \
     -X POST https://your-server/api/scan \
     -H "Content-Type: application/json" \
     -d '{"target": "example.com"}'
```

### 权限管理

建议为不同用户/场景使用不同的 API Key：

```bash
# 生成多个 API Key
export API_KEYS="admin-key-xxx,scanner-key-yyy,readonly-key-zzz"
```

---

## 🚨 安全漏洞报告

如果您发现安全漏洞，请负责任地披露：

1. **不要**公开披露漏洞详情
2. 发送详细信息到安全邮箱
3. 等待 90 天的修复期

我们承诺：
- 48 小时内确认收到报告
- 7 天内提供初步评估
- 尽快发布修复补丁

---

## 📋 安全检查清单

部署前请确认：

- [ ] 已设置 `API_KEYS` 环境变量
- [ ] 已启用 `AUTH_ENABLED=true`
- [ ] 已配置 HTTPS
- [ ] 已设置适当的 CORS 策略
- [ ] 已限制并发和速率
- [ ] 日志文件权限正确
- [ ] SSRF 防护已启用（除非内网扫描）
- [ ] 已阅读并理解免责声明

---

## 🔄 更新日志

### v3.2.1 (2026-04-14)
- 新增 SSRF 防护（IPv4/IPv6）
- 新增命令注入防护
- 新增日志脱敏功能
- 新增 API 认证支持
- 新增速率限制保护
- 更新安全文档
