# Contributing to AutoRecon

感谢你对 AutoRecon 的兴趣！本文档将帮助你参与项目开发。

---

## 🚀 快速开始

### 开发环境设置

```bash
# 1. Fork 并克隆仓库
git clone https://github.com/YOUR_USERNAME/AutoRecon.git
cd AutoRecon

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 3. 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 如果存在

# 4. 安装 pre-commit hooks
pip install pre-commit
pre-commit install

# 5. 运行测试
pytest tests/ -v
```

---

## 📝 代码规范

### Python 版本

- 最低支持：Python 3.10+
- 推荐使用：Python 3.12

### 代码风格

我们使用以下工具确保代码质量：

| 工具 | 用途 | 配置 |
|------|------|------|
| **black** | 代码格式化 | `--line-length=120` |
| **isort** | Import 排序 | `--profile black` |
| **flake8** | 风格检查 | `--max-line-length=120` |
| **mypy** | 类型检查 | `mypy.ini` |
| **bandit** | 安全检查 | 自动扫描 |

### 提交前检查

```bash
# 手动运行所有检查
pre-commit run --all-files

# 或单独运行
black .
isort .
flake8 .
mypy .
bandit -r . -x ./tests,.venv
```

---

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_ssrf_protection.py -v

# 运行覆盖率测试
pytest --cov=. --cov-report=html
```

### 测试覆盖率

我们期望测试覆盖率不低于 60%。新增代码应包含相应测试。

### 测试命名规范

```python
# 测试文件命名
test_<module_name>.py

# 测试类命名
class Test<FeatureName>:
    
# 测试方法命名
def test_<specific_behavior>(self):
```

---

## 🔧 模块开发

### 添加新模块

1. 在 `modules/` 目录创建新文件：

```python
# modules/my_scanner.py

from core.async_engine import AsyncHTTPClient

class MyScanner:
    """我的扫描器"""
    
    def __init__(self, target: str, **kwargs):
        self.target = target
        self.results = []
    
    async def scan(self) -> list:
        """执行扫描"""
        async with AsyncHTTPClient() as client:
            # 你的扫描逻辑
            pass
        return self.results
```

2. 在 `modules/__init__.py` 中导出

3. 在 `recon_v3.py` 中注册模块

4. 添加测试文件 `tests/test_my_scanner.py`

---

## 📚 文档

### 代码文档

使用 Google 风格的 docstring：

```python
def scan_url(url: str, timeout: int = 30) -> dict:
    """扫描指定 URL
    
    Args:
        url: 目标 URL
        timeout: 超时时间（秒）
        
    Returns:
        包含扫描结果的字典
        
    Raises:
        ValueError: URL 格式无效
        TimeoutError: 请求超时
        
    Example:
        >>> result = scan_url("https://example.com")
        >>> print(result['status'])
        200
    """
```

### README 更新

如果你的改动影响用户使用，请更新 README.md：

- 新功能：添加到功能列表
- API 变更：更新 API 文档
- 配置变更：更新配置说明

---

## 🔐 安全考虑

### 输入验证

所有用户输入必须验证：

```python
from recon_v3 import validate_url, validate_parameter

url = validate_url(user_input_url)
param = validate_parameter(user_input_param)
```

### SSRF 防护

使用 `skip_ssrf_check` 参数时需谨慎：

```python
# 默认启用 SSRF 防护
result = await client.get(url)

# 仅在明确需要时跳过
result = await client.get(url, skip_ssrf_check=True)
```

### 敏感信息

不要在日志中记录敏感信息：

```python
# ❌ 错误
logger.info(f"Connecting with password: {password}")

# ✅ 正确
logger.info("Connecting with credentials")
```

---

## 📤 提交 PR

### PR 流程

1. 创建功能分支：`git checkout -b feature/my-feature`
2. 提交改动：`git commit -m "feat: add my feature"`
3. 推送分支：`git push origin feature/my-feature`
4. 创建 Pull Request

### 提交信息格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `test`: 测试相关
- `refactor`: 重构
- `security`: 安全修复

**示例：**
```
feat(scanner): add XSS detection module

- Add reflected XSS scanner
- Add stored XSS detection
- Include 50+ XSS payloads

Closes #123
```

### PR 检查清单

- [ ] 代码通过所有测试
- [ ] 代码通过 pre-commit 检查
- [ ] 新功能有对应测试
- [ ] 文档已更新
- [ ] 提交信息格式正确

---

## 🐛 报告 Bug

### Bug 报告模板

```markdown
**描述**
简要描述问题

**复现步骤**
1. 执行命令 `python recon_v3.py example.com -m all`
2. 等待扫描完成
3. 发现错误

**预期行为**
应该正常完成扫描

**实际行为**
扫描中断，出现错误

**环境**
- OS: Ubuntu 22.04
- Python: 3.12.0
- AutoRecon: 3.2.0

**日志**
```
粘贴错误日志
```
```

---

## 💡 功能建议

欢迎提出新功能建议！请描述：
- 功能用途
- 使用场景
- 可能的实现方式

---

## 📄 许可证

提交代码即表示你同意将代码以 GPL-3.0 许可证开源。

---

感谢你的贡献！🎉
