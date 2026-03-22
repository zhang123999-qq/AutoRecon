#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - sqlmap 集成模块
通过 REST API 或命令行集成 sqlmap 进行 SQL 注入检测
"""

import asyncio
import json
import time
import os
import tempfile
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import aiohttp


@dataclass
class SQLMapResult:
    """sqlmap 扫描结果"""
    url: str
    parameter: str = ""
    injection_type: str = ""
    dbms: str = ""
    database: str = ""
    user: str = ""
    version: str = ""
    payload: str = ""
    vulnerable: bool = False
    data: Dict = field(default_factory=dict)
    log: List[str] = field(default_factory=list)


class SQLMapRESTClient:
    """
    sqlmap REST API 客户端
    需要先启动 sqlmap REST API 服务器
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8775):
        self.base_url = f"http://{host}:{port}"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def _get(self, path: str) -> Dict:
        """GET 请求"""
        async with self.session.get(f"{self.base_url}{path}") as resp:
            return await resp.json()
    
    async def _post(self, path: str, data: Dict = None) -> Dict:
        """POST 请求"""
        async with self.session.post(
            f"{self.base_url}{path}",
            json=data,
            headers={"Content-Type": "application/json"}
        ) as resp:
            return await resp.json()
    
    async def new_task(self) -> str:
        """创建新任务"""
        result = await self._get("/task/new")
        return result.get("taskid", "")
    
    async def delete_task(self, taskid: str) -> bool:
        """删除任务"""
        result = await self._get(f"/task/{taskid}/delete")
        return result.get("success", False)
    
    async def set_options(self, taskid: str, options: Dict) -> bool:
        """设置扫描选项"""
        result = await self._post(f"/option/{taskid}/set", options)
        return result.get("success", False)
    
    async def start_scan(self, taskid: str, options: Dict = None) -> bool:
        """
        启动扫描
        
        常用选项:
        - url: 目标 URL
        - data: POST 数据
        - cookie: Cookie
        - headers: 请求头
        - level: 扫描级别 (1-5)
        - risk: 风险级别 (1-3)
        - technique: 注入技术 (BEUSTQ)
        - threads: 线程数
        - dbms: 指定数据库类型
        - os: 指定操作系统
        - tamper: 绕过脚本
        """
        if options:
            await self.set_options(taskid, options)
        result = await self._post(f"/scan/{taskid}/start", options or {})
        return result.get("success", False)
    
    async def get_status(self, taskid: str) -> Dict:
        """获取扫描状态"""
        return await self._get(f"/scan/{taskid}/status")
    
    async def get_data(self, taskid: str) -> Dict:
        """获取扫描数据"""
        return await self._get(f"/scan/{taskid}/data")
    
    async def get_log(self, taskid: str) -> List[Dict]:
        """获取扫描日志"""
        result = await self._get(f"/scan/{taskid}/log")
        return result.get("log", [])
    
    async def stop_scan(self, taskid: str) -> bool:
        """停止扫描"""
        result = await self._get(f"/scan/{taskid}/stop")
        return result.get("success", False)
    
    async def kill_scan(self, taskid: str) -> bool:
        """强制杀死扫描"""
        result = await self._get(f"/scan/{taskid}/kill")
        return result.get("success", False)
    
    async def scan_url(self, url: str, options: Dict = None, timeout: int = 300) -> SQLMapResult:
        """
        扫描单个 URL
        
        Args:
            url: 目标 URL
            options: sqlmap 选项
            timeout: 超时时间（秒）
        
        Returns:
            SQLMapResult 对象
        """
        result = SQLMapResult(url=url)
        
        # 创建任务
        taskid = await self.new_task()
        if not taskid:
            return result
        
        try:
            # 默认选项
            default_options = {
                "url": url,
                "batch": True,
                "level": 1,
                "risk": 1,
                "randomAgent": True,
                "technique": "BEUST",  # Boolean, Error, Union, Stacked, Time
                "threads": 3,
            }
            
            if options:
                default_options.update(options)
            
            # 启动扫描
            await self.start_scan(taskid, default_options)
            
            # 等待扫描完成
            start_time = time.time()
            while time.time() - start_time < timeout:
                status = await self.get_status(taskid)
                
                if status.get("status") == "terminated":
                    break
                
                await asyncio.sleep(2)
            
            # 获取结果
            data = await self.get_data(taskid)
            logs = await self.get_log(taskid)
            
            # 解析结果
            result.log = [log.get("message", "") for log in logs]
            result.data = data
            
            # 提取关键信息
            for item in data.get("data", []):
                value = item.get("value", {})
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        continue
                
                # 检查是否有注入点
                if "value" in value and "data" in value["value"]:
                    injection_data = value["value"]["data"]
                    
                    if injection_data:
                        result.vulnerable = True
                        
                        # 提取注入参数
                        for inj in injection_data:
                            result.parameter = inj.get("parameter", "")
                            result.injection_type = inj.get("type", "")
                            result.dbms = inj.get("dbms", "")
                            result.payload = inj.get("payload", "")
                            
                            # 提取数据库信息
                            if "banner" in inj:
                                result.version = inj["banner"]
                            if "current db" in inj:
                                result.database = inj["current db"]
                            if "current user" in inj:
                                result.user = inj["current user"]
        
        finally:
            # 清理任务
            await self.delete_task(taskid)
        
        return result


class SQLMapCommandLine:
    """
    sqlmap 命令行封装
    直接调用 sqlmap 命令，无需启动 API 服务器
    """
    
    def __init__(self, sqlmap_path: str = "sqlmap"):
        """
        Args:
            sqlmap_path: sqlmap 命令路径，默认使用系统 PATH
        """
        self.sqlmap_path = sqlmap_path
    
    async def scan_url(
        self,
        url: str,
        options: Dict = None,
        timeout: int = 300
    ) -> SQLMapResult:
        """
        扫描单个 URL
        
        Args:
            url: 目标 URL
            options: sqlmap 选项 (字典格式)
            timeout: 超时时间（秒）
        
        Returns:
            SQLMapResult 对象
        """
        result = SQLMapResult(url=url)
        
        # 构建命令
        cmd = [self.sqlmap_path, "-u", url, "--batch"]
        
        # 默认选项
        default_options = {
            "level": 1,
            "risk": 1,
            "random-agent": True,
            "technique": "BEUST",
            "threads": 3,
        }
        
        if options:
            default_options.update(options)
        
        # 转换选项为命令行参数
        for key, value in default_options.items():
            key = key.replace("_", "-")
            
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            elif isinstance(value, list):
                for v in value:
                    cmd.extend([f"--{key}", str(v)])
            else:
                cmd.extend([f"--{key}", str(value)])
        
        try:
            # 运行 sqlmap
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            
            output = stdout.decode("utf-8", errors="ignore")
            result.log.append(output)
            
            # 解析输出
            result.vulnerable = self._parse_vulnerable(output)
            
            if result.vulnerable:
                result.parameter = self._parse_parameter(output)
                result.dbms = self._parse_dbms(output)
                result.injection_type = self._parse_injection_type(output)
                result.payload = self._parse_payload(output)
                result.database = self._parse_database(output)
                result.user = self._parse_user(output)
        
        except asyncio.TimeoutError:
            proc.kill()
            result.log.append("Scan timeout")
        except FileNotFoundError:
            result.log.append("sqlmap not found")
        except Exception as e:
            result.log.append(f"Error: {str(e)}")
        
        return result
    
    def _parse_vulnerable(self, output: str) -> bool:
        """解析是否存在漏洞"""
        indicators = [
            "Parameter:",
            "Type:",
            "Payload:",
            "vulnerable",
        ]
        return any(ind in output for ind in indicators)
    
    def _parse_parameter(self, output: str) -> str:
        """解析注入参数"""
        import re
        match = re.search(r"Parameter:\s+(\w+)", output)
        return match.group(1) if match else ""
    
    def _parse_dbms(self, output: str) -> str:
        """解析数据库类型"""
        import re
        patterns = {
            "MySQL": [r"MySQL", r"MariaDB"],
            "PostgreSQL": [r"PostgreSQL"],
            "Oracle": [r"Oracle"],
            "MSSQL": [r"Microsoft SQL Server", r"MSSQL"],
            "SQLite": [r"SQLite"],
            "Access": [r"Access"],
        }
        
        for dbms, pats in patterns.items():
            for pat in pats:
                if re.search(pat, output, re.IGNORECASE):
                    return dbms
        
        # 尝试从 back-end DBMS 提取
        match = re.search(r"back-end DBMS:\s*'?([^'\n]+)", output)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _parse_injection_type(self, output: str) -> str:
        """解析注入类型"""
        import re
        types = {
            "boolean-based blind": r"boolean-based",
            "error-based": r"error-based",
            "time-based blind": r"time-based",
            "UNION query": r"UNION query",
            "stacked queries": r"stacked queries",
        }
        
        for t, pat in types.items():
            if re.search(pat, output, re.IGNORECASE):
                return t
        
        return ""
    
    def _parse_payload(self, output: str) -> str:
        """解析注入 payload"""
        import re
        match = re.search(r"Payload:\s*(.+?)(?:\n|$)", output)
        return match.group(1).strip() if match else ""
    
    def _parse_database(self, output: str) -> str:
        """解析当前数据库"""
        import re
        match = re.search(r"current database:\s*'?([^'\n]+)", output)
        return match.group(1).strip() if match else ""
    
    def _parse_user(self, output: str) -> str:
        """解析当前用户"""
        import re
        match = re.search(r"current user:\s*'?([^'\n]+)", output)
        return match.group(1).strip() if match else ""


class SQLMapAutoScanner:
    """
    自动 SQL 注入扫描器
    集成 REST API 和命令行两种方式
    """
    
    def __init__(
        self,
        target: str,
        threads: int = 5,
        use_api: bool = False,
        api_host: str = "127.0.0.1",
        api_port: int = 8775,
        timeout: int = 180
    ):
        self.target = target
        self.threads = threads
        self.use_api = use_api
        self.api_host = api_host
        self.api_port = api_port
        self.timeout = timeout
        
        self.results: List[SQLMapResult] = []
        self.urls_to_scan: List[str] = []
    
    async def _discover_urls(self) -> List[str]:
        """发现带参数的 URL"""
        from core.async_engine import AsyncHTTPClient
        import re
        
        urls = []
        base_url = f"http://{self.target}"
        
        try:
            async with AsyncHTTPClient() as client:
                resp = await client.get(base_url)
                body = resp.get("body", "")
                
                # 提取带参数的链接
                patterns = [
                    r'href=["\']([^"\']*\?[^"\']*)["\']',
                    r'src=["\']([^"\']*\?[^"\']*)["\']',
                    r'action=["\']([^"\']*\?[^"\']*)["\']',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, body, re.IGNORECASE)
                    for match in matches:
                        if match.startswith("/"):
                            match = f"http://{self.target}{match}"
                        elif not match.startswith("http"):
                            match = f"http://{self.target}/{match}"
                        
                        if "?" in match and self.target in match:
                            urls.append(match)
        
        except Exception:
            pass
        
        # 添加常见路径
        common_paths = [
            "/index.php?id=1",
            "/page.php?id=1",
            "/detail.php?id=1",
            "/news.php?id=1",
            "/article.php?id=1",
            "/product.php?id=1",
            "/user.php?id=1",
            "/search.php?q=test",
        ]
        
        for path in common_paths:
            urls.append(f"http://{self.target}{path}")
        
        return list(set(urls))
    
    async def scan_url(self, url: str) -> SQLMapResult:
        """扫描单个 URL"""
        if self.use_api:
            async with SQLMapRESTClient(self.api_host, self.api_port) as client:
                return await client.scan_url(url, timeout=self.timeout)
        else:
            client = SQLMapCommandLine()
            return await client.scan_url(url, timeout=self.timeout)
    
    async def run_full_scan(self) -> List[SQLMapResult]:
        """运行完整扫描"""
        print("\n" + "=" * 55)
        print("\u001b[36msqlmap SQL 注入扫描\u001b[0m")
        print("=" * 55 + "\n")
        
        # 发现 URL
        print("[\u001b[36m*\u001b[0m] 发现带参数的 URL...")
        self.urls_to_scan = await self._discover_urls()
        
        if not self.urls_to_scan:
            print("[\u001b[33m-\u001b[0m] 未发现带参数的 URL")
            return []
        
        print(f"[\u001b[32m+\u001b[0m] 发现 {len(self.urls_to_scan)} 个 URL")
        
        # 并发扫描
        semaphore = asyncio.Semaphore(self.threads)
        
        async def limited_scan(url):
            async with semaphore:
                print(f"[\u001b[36m*\u001b[0m] 扫描: {url}")
                return await self.scan_url(url)
        
        tasks = [limited_scan(url) for url in self.urls_to_scan[:10]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for r in results:
            if isinstance(r, SQLMapResult):
                self.results.append(r)
        
        # 输出结果
        vulnerable = [r for r in self.results if r.vulnerable]
        
        if vulnerable:
            print(f"\n[\u001b[31m!\u001b[0m] 发现 {len(vulnerable)} 个 SQL 注入漏洞!")
            for r in vulnerable:
                print(f"    URL: {r.url}")
                print(f"    参数: {r.parameter}")
                print(f"    类型: {r.injection_type}")
                print(f"    数据库: {r.dbms}")
                if r.payload:
                    print(f"    Payload: {r.payload[:50]}...")
                print()
        else:
            print(f"\n[\u001b[32m+\u001b[0m] 未发现 SQL 注入漏洞")
        
        return self.results
    
    def get_results(self) -> List[Dict]:
        """获取结果（字典格式）"""
        return [
            {
                "url": r.url,
                "parameter": r.parameter,
                "injection_type": r.injection_type,
                "dbms": r.dbms,
                "database": r.database,
                "user": r.user,
                "payload": r.payload,
                "vulnerable": r.vulnerable,
            }
            for r in self.results
        ]


# API 服务器启动工具
async def start_sqlmap_api_server(
    host: str = "127.0.0.1",
    port: int = 8775
) -> asyncio.subprocess.Process:
    """
    启动 sqlmap REST API 服务器
    
    Returns:
        进程对象
    """
    # 找到 sqlmap 的 api.py 路径
    try:
        import sqlmap
        sqlmap_dir = os.path.dirname(sqlmap.__file__)
        api_script = os.path.join(sqlmap_dir, "lib", "utils", "api.py")
        
        if not os.path.exists(api_script):
            raise FileNotFoundError("sqlmap api.py not found")
        
        # 启动服务器
        proc = await asyncio.create_subprocess_exec(
            sys.executable, api_script, "-s", "-H", host, "-p", str(port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 等待服务器启动
        await asyncio.sleep(2)
        
        print(f"[\u001b[32m+\u001b[0m] sqlmap API 服务器已启动: http://{host}:{port}")
        return proc
    
    except Exception as e:
        print(f"[\u001b[31m-\u001b[0m] 启动 sqlmap API 服务器失败: {e}")
        return None


# 测试
async def main():
    import sys
    
    target = sys.argv[1] if len(sys.argv) > 1 else "testphp.vulnweb.com"
    
    # 使用命令行方式
    scanner = SQLMapAutoScanner(
        target=target,
        threads=3,
        use_api=False,
        timeout=120
    )
    
    results = await scanner.run_full_scan()
    
    print("\n结果:")
    for r in results:
        print(f"  {r.url}: {'存在漏洞' if r.vulnerable else '安全'}")


if __name__ == "__main__":
    asyncio.run(main())
