#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - GitHub 信息泄露检测模块
检测 GitHub 仓库中的敏感信息泄露
"""

import asyncio
import re
import aiohttp
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class SecretType(Enum):
    """敏感信息类型"""
    AWS_KEY = "AWS Access Key"
    AWS_SECRET = "AWS Secret Key"
    GITHUB_TOKEN = "GitHub Token"
    API_KEY = "API Key"
    PRIVATE_KEY = "Private Key"
    PASSWORD = "Password"
    DATABASE_URL = "Database URL"
    JWT_SECRET = "JWT Secret"
    STRIPE_KEY = "Stripe Key"
    SLACK_TOKEN = "Slack Token"
    GOOGLE_API_KEY = "Google API Key"


@dataclass
class LeakedSecret:
    """泄露的敏感信息"""
    type: SecretType
    file_path: str
    line_number: int
    snippet: str
    repository: str
    url: str
    severity: str = "high"  # high, medium, low


@dataclass
class GitHubResult:
    """GitHub 检测结果"""
    query: str
    repositories: List[Dict[str, Any]] = field(default_factory=list)
    leaked_secrets: List[LeakedSecret] = field(default_factory=list)
    potential_risks: List[str] = field(default_factory=list)
    total_count: int = 0


class GitHubLeakScanner:
    """
    GitHub 信息泄露扫描器
    
    功能：
    - 搜索目标相关的公开仓库
    - 检测敏感文件（.env, credentials, config）
    - 正则匹配敏感信息（API Key, 密码等）
    - 风险评估
    """
    
    # GitHub API 基础 URL
    API_URL = "https://api.github.com"
    
    # 敏感文件模式
    SENSITIVE_FILES = [
        '.env', '.env.local', '.env.production', '.env.development',
        'credentials.json', 'secrets.json', 'config.json',
        'private.key', 'id_rsa', 'id_ed25519',
        '.htpasswd', '.netrc', '_netrc',
        'database.yml', 'settings.py', 'local_settings.py',
        'wp-config.php', 'configuration.php',
    ]
    
    # 敏感信息正则模式
    SECRET_PATTERNS = [
        # AWS
        (SecretType.AWS_KEY, r'AKIA[0-9A-Z]{16}'),
        (SecretType.AWS_SECRET, r'(?i)aws(.{0,20})?[\'\"][0-9a-zA-Z/+=]{40}[\'\"]'),
        # GitHub
        (SecretType.GITHUB_TOKEN, r'ghp_[0-9a-zA-Z]{36}'),
        (SecretType.GITHUB_TOKEN, r'gho_[0-9a-zA-Z]{36}'),
        (SecretType.GITHUB_TOKEN, r'github_pat_[0-9a-zA-Z_]{22,}'),
        # API Keys
        (SecretType.API_KEY, r'(?i)(api[_-]?key|apikey)[\s]*[=:]\s*[\'\"][0-9a-zA-Z_-]{20,}[\'\"]'),
        (SecretType.GOOGLE_API_KEY, r'AIza[0-9A-Za-z_-]{35}'),
        (SecretType.STRIPE_KEY, r'sk_live_[0-9a-zA-Z]{24}'),
        (SecretType.SLACK_TOKEN, r'xox[baprs]-[0-9]{10,}-[0-9a-zA-Z]{24,}'),
        # Private Key
        (SecretType.PRIVATE_KEY, r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----'),
        # Database URL
        (SecretType.DATABASE_URL, r'(?i)(mysql|postgres|mongodb|redis)://[^\s\'"]+:[^\s\'"]+@[^\s\'"]+'),
        # JWT
        (SecretType.JWT_SECRET, r'(?i)jwt[_-]?secret[\s]*[=:]\s*[\'\"][0-9a-zA-Z_-]{20,}[\'\"]'),
        # Password (常见模式)
        (SecretType.PASSWORD, r'(?i)(password|passwd|pwd)[\s]*[=:]\s*[\'\"][^\'"]{6,}[\'\"]'),
    ]
    
    # 搜索关键词
    SEARCH_KEYWORDS = [
        'password', 'secret', 'apikey', 'api_key', 'token',
        'private_key', 'credentials', 'auth', 'access_key',
    ]
    
    def __init__(self, target: str, github_token: str = None):
        """
        初始化扫描器
        
        Args:
            target: 目标域名或组织名
            github_token: GitHub Personal Access Token（提高速率限制）
        """
        self.target = target
        self.github_token = github_token
        self.session: Optional[aiohttp.ClientSession] = None
        self.results = GitHubResult(query=target)
    
    async def __aenter__(self):
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        self.session = aiohttp.ClientSession(headers=headers)
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def search_repositories(self, max_results: int = 50) -> List[Dict]:
        """
        搜索目标相关的仓库
        
        Args:
            max_results: 最大结果数
            
        Returns:
            List[Dict]: 仓库列表
        """
        url = f"{self.API_URL}/search/repositories"
        params = {
            "q": f"{self.target} in:name,description,homepage",
            "sort": "stars",
            "order": "desc",
            "per_page": min(max_results, 100)
        }
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.results.total_count = data.get('total_count', 0)
                    return data.get('items', [])
                elif resp.status == 403:
                    print("[!] GitHub API 速率限制，请稍后重试或使用 Token")
                    return []
        except Exception as e:
            print(f"[!] 搜索仓库失败: {e}")
        
        return []
    
    async def search_code(self, query: str, max_results: int = 30) -> List[Dict]:
        """
        搜索代码（需要 Token）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            List[Dict]: 代码搜索结果
        """
        if not self.github_token:
            print("[!] 代码搜索需要 GitHub Token")
            return []
        
        url = f"{self.API_URL}/search/code"
        params = {
            "q": f"{query} org:{self.target}" if '.' not in self.target else f"{query} {self.target}",
            "per_page": min(max_results, 100)
        }
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('items', [])
                elif resp.status == 403:
                    print("[!] GitHub API 速率限制")
                    return []
        except Exception as e:
            print(f"[!] 代码搜索失败: {e}")
        
        return []
    
    async def check_repository(self, repo: Dict) -> List[LeakedSecret]:
        """
        检查单个仓库的敏感信息
        
        Args:
            repo: 仓库信息
            
        Returns:
            List[LeakedSecret]: 泄露的敏感信息列表
        """
        secrets = []
        repo_name = repo['full_name']
        default_branch = repo.get('default_branch', 'main')
        
        # 检查敏感文件
        for sensitive_file in self.SENSITIVE_FILES:
            url = f"{self.API_URL}/repos/{repo_name}/contents/{sensitive_file}"
            url += f"?ref={default_branch}"
            
            try:
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('type') == 'file':
                            # 文件存在，记录风险
                            self.results.potential_risks.append(
                                f"{repo_name}: 发现敏感文件 {sensitive_file}"
                            )
                            # 如果有内容，检查敏感信息
                            if 'content' in data:
                                import base64
                                try:
                                    content = base64.b64decode(data['content']).decode('utf-8', errors='ignore')
                                    file_secrets = self._scan_content(content, sensitive_file, repo_name)
                                    secrets.extend(file_secrets)
                                except:
                                    pass
                
                # 避免速率限制
                await asyncio.sleep(0.5)
                
            except Exception:
                pass
        
        return secrets
    
    def _scan_content(self, content: str, file_path: str, repo: str) -> List[LeakedSecret]:
        """
        扫描内容中的敏感信息
        
        Args:
            content: 文件内容
            file_path: 文件路径
            repo: 仓库名
            
        Returns:
            List[LeakedSecret]: 发现的敏感信息
        """
        secrets = []
        lines = content.split('\n')
        
        for secret_type, pattern in self.SECRET_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                # 计算行号
                line_num = content[:match.start()].count('\n') + 1
                
                # 获取上下文
                snippet = lines[line_num - 1] if line_num <= len(lines) else match.group()
                
                # 创建泄露记录
                leaked = LeakedSecret(
                    type=secret_type,
                    file_path=file_path,
                    line_number=line_num,
                    snippet=snippet[:100],  # 限制长度
                    repository=repo,
                    url=f"https://github.com/{repo}/blob/main/{file_path}",
                    severity=self._get_severity(secret_type)
                )
                secrets.append(leaked)
        
        return secrets
    
    def _get_severity(self, secret_type: SecretType) -> str:
        """获取敏感信息严重程度"""
        high_severity = [
            SecretType.AWS_SECRET,
            SecretType.PRIVATE_KEY,
            SecretType.GITHUB_TOKEN,
            SecretType.DATABASE_URL,
        ]
        
        if secret_type in high_severity:
            return "high"
        elif secret_type in [SecretType.PASSWORD, SecretType.JWT_SECRET]:
            return "medium"
        else:
            return "low"
    
    async def scan(self) -> GitHubResult:
        """
        执行完整扫描
        
        Returns:
            GitHubResult: 扫描结果
        """
        print(f"\n[*] 扫描 GitHub 信息泄露: {self.target}")
        
        # 搜索仓库
        print("[*] 搜索相关仓库...")
        repos = await self.search_repositories()
        self.results.repositories = repos
        
        print(f"[+] 发现 {len(repos)} 个相关仓库")
        
        # 检查每个仓库
        for i, repo in enumerate(repos[:10]):  # 限制检查数量
            print(f"[*] 检查仓库 {i+1}/{min(len(repos), 10)}: {repo['full_name']}")
            secrets = await self.check_repository(repo)
            self.results.leaked_secrets.extend(secrets)
        
        # 代码搜索（需要 Token）
        if self.github_token:
            print("[*] 搜索代码中的敏感信息...")
            for keyword in self.SEARCH_KEYWORDS[:3]:  # 限制关键词数量
                code_results = await self.search_code(keyword)
                print(f"    {keyword}: 发现 {len(code_results)} 个结果")
                await asyncio.sleep(2)  # 避免 API 限制
        
        # 总结
        print(f"\n[+] 扫描完成:")
        print(f"    仓库数: {len(self.results.repositories)}")
        print(f"    泄露风险: {len(self.results.potential_risks)}")
        print(f"    敏感信息: {len(self.results.leaked_secrets)}")
        
        return self.results
    
    def print_results(self):
        """打印结果"""
        print("\n" + "=" * 60)
        print("GitHub 信息泄露扫描报告")
        print("=" * 60)
        
        if self.results.leaked_secrets:
            print("\n[!] 发现敏感信息泄露:")
            for secret in self.results.leaked_secrets:
                print(f"\n  类型: {secret.type.value}")
                print(f"  文件: {secret.file_path}:{secret.line_number}")
                print(f"  仓库: {secret.repository}")
                print(f"  严重程度: {secret.severity}")
                print(f"  片段: {secret.snippet[:50]}...")
        
        if self.results.potential_risks:
            print("\n[!] 潜在风险:")
            for risk in self.results.potential_risks:
                print(f"  - {risk}")
        
        if not self.results.leaked_secrets and not self.results.potential_risks:
            print("\n[+] 未发现明显的信息泄露")


# ============== 使用示例 ==============

async def main():
    """示例：GitHub 泄露检测"""
    
    # 方式1：无 Token（限制较多）
    async with GitHubLeakScanner("example.com") as scanner:
        result = await scanner.scan()
        scanner.print_results()
    
    # 方式2：使用 Token（完整功能）
    # async with GitHubLeakScanner("example.com", github_token="ghp_xxx") as scanner:
    #     result = await scanner.scan()
    #     scanner.print_results()


if __name__ == "__main__":
    asyncio.run(main())
