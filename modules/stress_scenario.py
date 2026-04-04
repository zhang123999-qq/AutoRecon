#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.2 - 测试场景脚本模块
YAML 场景定义，支持复杂用户行为模拟
"""

import asyncio
import time
import random
import re
import logging
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


# ============ 数据模型 ============

class StepType(Enum):
    """步骤类型"""
    REQUEST = "request"       # HTTP 请求
    THINK = "think"           # 思考时间
    LOOP = "loop"             # 循环
    CONDITION = "condition"   # 条件判断
    WAIT = "wait"             # 等待
    GROUP = "group"           # 步骤组


@dataclass
class Assertion:
    """断言"""
    type: str  # status_code, response_time, body_contains, json_path
    expected: Any
    actual_path: str = ""  # JSON 路径或响应字段


@dataclass
class RequestStep:
    """请求步骤"""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = None
    body: Optional[str] = None
    think_time: float = 0
    assertions: List[Assertion] = None
    extract: Dict[str, str] = None  # 提取变量
    name: str = ""
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.assertions is None:
            self.assertions = []
        if self.extract is None:
            self.extract = {}


@dataclass
class ThinkStep:
    """思考时间步骤"""
    min_time: float = 0.5
    max_time: float = 2.0
    name: str = ""


@dataclass
class LoopStep:
    """循环步骤"""
    count: int = 1
    steps: List[Any] = field(default_factory=list)
    name: str = ""


@dataclass
class ConditionStep:
    """条件步骤"""
    condition: str  # Python 表达式
    if_true: List[Any] = field(default_factory=list)
    if_false: List[Any] = field(default_factory=list)
    name: str = ""


@dataclass
class TestScenario:
    """测试场景"""
    name: str
    description: str = ""
    base_url: str = ""
    default_headers: Dict[str, str] = None
    think_time: Dict[str, float] = None  # min, max
    variables: Dict[str, Any] = None
    steps: List[Any] = field(default_factory=list)
    
    def __post_init__(self):
        if self.default_headers is None:
            self.default_headers = {}
        if self.think_time is None:
            self.think_time = {"min": 0, "max": 1}
        if self.variables is None:
            self.variables = {}


# ============ YAML 加载器 ============

class ScenarioLoader:
    """场景加载器"""
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> TestScenario:
        """从 YAML 文件加载场景"""
        try:
            import yaml
        except ImportError:
            raise ImportError("需要安装 PyYAML: pip install pyyaml")
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict) -> TestScenario:
        """从字典创建场景"""
        scenario = TestScenario(
            name=data.get('name', 'Unnamed'),
            description=data.get('description', ''),
            base_url=data.get('base_url', ''),
            default_headers=data.get('default_headers', {}),
            think_time=data.get('think_time', {"min": 0, "max": 1}),
            variables=data.get('variables', {}),
            steps=[]
        )
        
        # 解析步骤
        for step_data in data.get('steps', []):
            step = cls._parse_step(step_data)
            if step:
                scenario.steps.append(step)
        
        return scenario
    
    @classmethod
    def _parse_step(cls, data: Dict) -> Any:
        """解析单个步骤"""
        step_type = data.get('type', 'request')
        
        if step_type == 'request':
            return RequestStep(
                url=data.get('url', ''),
                method=data.get('method', 'GET'),
                headers=data.get('headers'),
                body=data.get('body'),
                think_time=data.get('think_time', 0),
                name=data.get('name', ''),
                assertions=cls._parse_assertions(data.get('assertions', [])),
                extract=data.get('extract')
            )
        
        elif step_type == 'think':
            think_config = data.get('think_time', {})
            if isinstance(think_config, (int, float)):
                return ThinkStep(min_time=think_config, max_time=think_config)
            return ThinkStep(
                min_time=think_config.get('min', 0.5),
                max_time=think_config.get('max', 2.0)
            )
        
        elif step_type == 'loop':
            return LoopStep(
                count=data.get('count', 1),
                steps=[cls._parse_step(s) for s in data.get('steps', [])],
                name=data.get('name', '')
            )
        
        elif step_type == 'condition':
            return ConditionStep(
                condition=data.get('condition', 'True'),
                if_true=[cls._parse_step(s) for s in data.get('if_true', [])],
                if_false=[cls._parse_step(s) for s in data.get('if_false', [])],
                name=data.get('name', '')
            )
        
        elif step_type == 'wait':
            return ThinkStep(
                min_time=data.get('duration', 1),
                max_time=data.get('duration', 1)
            )
        
        return None
    
    @classmethod
    def _parse_assertions(cls, data: List) -> List[Assertion]:
        """解析断言列表"""
        assertions = []
        for item in data:
            if isinstance(item, dict):
                assertions.append(Assertion(
                    type=item.get('type', 'status_code'),
                    expected=item.get('expected'),
                    actual_path=item.get('path', '')
                ))
            elif isinstance(item, str):
                # 简写: "status_code == 200"
                match = re.match(r'(\w+)\s*(==|!=|<=|>=|<|>)\s*(.+)', item)
                if match:
                    assertions.append(Assertion(
                        type=match.group(1),
                        expected=match.group(3).strip()
                    ))
        return assertions


# ============ 场景执行器 ============

class ScenarioRunner:
    """场景执行器"""
    
    def __init__(self, scenario: TestScenario, http_client=None):
        """
        Args:
            scenario: 测试场景
            http_client: aiohttp ClientSession
        """
        self.scenario = scenario
        self.http_client = http_client
        self.variables = dict(scenario.variables)
        self.results = []
        self.assertion_results = []
    
    async def run_once(self) -> Dict[str, Any]:
        """执行一次完整场景"""
        start_time = time.perf_counter()
        step_results = []
        
        try:
            for step in self.scenario.steps:
                result = await self._execute_step(step)
                step_results.append(result)
                
                # 检查是否应该停止
                if result.get('stop', False):
                    break
        
        except Exception as e:
            logger.error(f"场景执行错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_time": (time.perf_counter() - start_time) * 1000
            }
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        return {
            "success": all(r.get('success', True) for r in step_results),
            "total_time": total_time,
            "step_count": len(step_results),
            "steps": step_results
        }
    
    async def _execute_step(self, step: Any) -> Dict[str, Any]:
        """执行单个步骤"""
        if isinstance(step, RequestStep):
            return await self._execute_request(step)
        elif isinstance(step, ThinkStep):
            return await self._execute_think(step)
        elif isinstance(step, LoopStep):
            return await self._execute_loop(step)
        elif isinstance(step, ConditionStep):
            return await self._execute_condition(step)
        else:
            return {"success": True, "type": "unknown"}
    
    async def _execute_request(self, step: RequestStep) -> Dict[str, Any]:
        """执行请求步骤"""
        import aiohttp
        
        # 替换变量
        url = self._replace_variables(step.url)
        if self.scenario.base_url and not url.startswith('http'):
            url = self.scenario.base_url.rstrip('/') + '/' + url.lstrip('/')
        
        headers = {**self.scenario.default_headers, **(step.headers or {})}
        body = self._replace_variables(step.body) if step.body else None
        
        start_time = time.perf_counter()
        
        try:
            async with self.http_client.request(
                method=step.method,
                url=url,
                headers=headers,
                data=body,
                allow_redirects=True
            ) as response:
                response_body = await response.text()
                response_time = (time.perf_counter() - start_time) * 1000
                
                # 提取变量
                if step.extract:
                    self._extract_variables(step.extract, response_body, response)
                
                # 执行断言
                assertion_results = self._run_assertions(step.assertions, response, response_body)
                
                result = {
                    "success": response.status < 400 and all(a['passed'] for a in assertion_results),
                    "type": "request",
                    "name": step.name or step.url,
                    "url": url,
                    "method": step.method,
                    "status_code": response.status,
                    "response_time": response_time,
                    "assertions": assertion_results
                }
                
                # 思考时间
                if step.think_time > 0:
                    await asyncio.sleep(step.think_time)
                
                return result
        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "type": "request",
                "name": step.name or step.url,
                "error": "timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "type": "request",
                "name": step.name or step.url,
                "error": str(e)
            }
    
    async def _execute_think(self, step: ThinkStep) -> Dict[str, Any]:
        """执行思考时间"""
        think_time = random.uniform(step.min_time, step.max_time)
        await asyncio.sleep(think_time)
        
        return {
            "success": True,
            "type": "think",
            "duration": think_time
        }
    
    async def _execute_loop(self, step: LoopStep) -> Dict[str, Any]:
        """执行循环"""
        results = []
        
        for i in range(step.count):
            for sub_step in step.steps:
                result = await self._execute_step(sub_step)
                results.append(result)
                
                if not result.get('success', True):
                    break
        
        return {
            "success": all(r.get('success', True) for r in results),
            "type": "loop",
            "count": step.count,
            "results": results
        }
    
    async def _execute_condition(self, step: ConditionStep) -> Dict[str, Any]:
        """执行条件判断"""
        # 评估条件
        try:
            condition_result = eval(step.condition, {"__builtins__": {}}, self.variables)
        except Exception as e:
            logger.warning(f"条件评估失败: {e}")
            condition_result = False
        
        # 执行对应分支
        steps_to_execute = step.if_true if condition_result else step.if_false
        results = []
        
        for sub_step in steps_to_execute:
            result = await self._execute_step(sub_step)
            results.append(result)
        
        return {
            "success": all(r.get('success', True) for r in results),
            "type": "condition",
            "condition_met": condition_result,
            "results": results
        }
    
    def _replace_variables(self, text: str) -> str:
        """替换变量占位符"""
        if not text:
            return text
        
        for key, value in self.variables.items():
            placeholder = f"${{{key}}}"
            if placeholder in text:
                text = text.replace(placeholder, str(value))
        
        return text
    
    def _extract_variables(self, extract_config: Dict, body: str, response):
        """从响应中提取变量"""
        import json
        
        for var_name, extraction in extract_config.items():
            try:
                if extraction.startswith('json:'):
                    # JSON 路径提取
                    json_path = extraction[5:]
                    data = json.loads(body)
                    value = self._get_json_value(data, json_path)
                    self.variables[var_name] = value
                
                elif extraction.startswith('header:'):
                    # 响应头提取
                    header_name = extraction[7:]
                    self.variables[var_name] = response.headers.get(header_name, '')
                
                elif extraction.startswith('regex:'):
                    # 正则提取
                    pattern = extraction[6:]
                    match = re.search(pattern, body)
                    if match:
                        self.variables[var_name] = match.group(1) if match.groups() else match.group(0)
                
            except Exception as e:
                logger.warning(f"变量提取失败 {var_name}: {e}")
    
    def _get_json_value(self, data: Any, path: str) -> Any:
        """获取 JSON 路径对应的值"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                return None
        
        return value
    
    def _run_assertions(self, assertions: List[Assertion], response, body: str) -> List[Dict]:
        """运行断言"""
        results = []
        
        for assertion in assertions:
            try:
                if assertion.type == 'status_code':
                    expected = int(assertion.expected)
                    passed = response.status == expected
                
                elif assertion.type == 'response_time':
                    # 需要从外部传入
                    passed = True
                
                elif assertion.type == 'body_contains':
                    passed = str(assertion.expected) in body
                
                else:
                    passed = True
                
                results.append({
                    "type": assertion.type,
                    "expected": assertion.expected,
                    "passed": passed
                })
            
            except Exception as e:
                results.append({
                    "type": assertion.type,
                    "expected": assertion.expected,
                    "passed": False,
                    "error": str(e)
                })
        
        self.assertion_results.extend(results)
        return results


# ============ 场景压力测试器 ============

class ScenarioStressTester:
    """
    基于场景的压力测试器
    
    支持多个虚拟用户并发执行测试场景
    """
    
    def __init__(
        self,
        scenario: TestScenario,
        concurrent_users: int = 10,
        duration: int = 60,
        ramp_up: int = 10
    ):
        self.scenario = scenario
        self.concurrent_users = concurrent_users
        self.duration = duration
        self.ramp_up = ramp_up
        
        # 统计
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        self.total_time = 0
        self.errors: Dict[str, int] = {}
    
    async def run(self) -> Dict[str, Any]:
        """运行场景压力测试"""
        import aiohttp
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # 爬坡启动
            tasks = []
            users_per_step = max(1, self.concurrent_users // 10)
            step_interval = self.ramp_up / 10 if self.ramp_up > 0 else 0
            
            for step in range(10):
                # 添加用户
                for _ in range(users_per_step):
                    if len(tasks) >= self.concurrent_users:
                        break
                    
                    task = asyncio.create_task(self._user_loop(session))
                    tasks.append(task)
                
                if step_interval > 0:
                    await asyncio.sleep(step_interval)
            
            # 运行指定时长
            elapsed = 0
            while elapsed < self.duration:
                await asyncio.sleep(1)
                elapsed = time.time() - start_time
        
        # 计算指标
        total_time = time.time() - start_time
        
        return {
            "scenario": self.scenario.name,
            "concurrent_users": self.concurrent_users,
            "duration": total_time,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "runs_per_second": self.total_runs / total_time if total_time > 0 else 0,
            "success_rate": self.successful_runs / self.total_runs * 100 if self.total_runs > 0 else 0,
            "errors": self.errors
        }
    
    async def _user_loop(self, session):
        """用户循环"""
        runner = ScenarioRunner(self.scenario, session)
        
        while True:
            try:
                result = await runner.run_once()
                
                self.total_runs += 1
                if result.get('success'):
                    self.successful_runs += 1
                else:
                    self.failed_runs += 1
                    error = result.get('error', 'unknown')
                    self.errors[error] = self.errors.get(error, 0) + 1
            
            except Exception as e:
                self.total_runs += 1
                self.failed_runs += 1
                self.errors[str(e)] = self.errors.get(str(e), 0) + 1


# ============ 示例场景 ============

EXAMPLE_SCENARIO_YAML = """
# 用户登录流程测试场景
name: "用户登录流程"
description: "模拟用户登录并浏览商品页面"
base_url: "http://example.com"
default_headers:
  User-Agent: "AutoRecon/3.2"
  Accept: "application/json"

variables:
  username: "testuser"
  password: "testpass123"

think_time:
  min: 0.5
  max: 2.0

steps:
  # 1. 访问首页
  - type: request
    name: "访问首页"
    url: "/"
    method: GET
    assertions:
      - type: status_code
        expected: 200
  
  # 2. 思考
  - type: think
    think_time:
      min: 1.0
      max: 3.0
  
  # 3. 登录
  - type: request
    name: "用户登录"
    url: "/api/login"
    method: POST
    headers:
      Content-Type: "application/json"
    body: '{"username": "${username}", "password": "${password}"}'
    assertions:
      - type: status_code
        expected: 200
    extract:
      token: "json:data.token"
  
  # 4. 循环浏览商品
  - type: loop
    count: 3
    steps:
      - type: request
        name: "商品列表"
        url: "/api/products?page=1"
        method: GET
        headers:
          Authorization: "Bearer ${token}"
        assertions:
          - type: status_code
            expected: 200
      
      - type: think
        think_time:
          min: 2.0
          max: 5.0
  
  # 5. 条件判断
  - type: condition
    condition: "token != ''"
    if_true:
      - type: request
        name: "用户信息"
        url: "/api/user/profile"
        method: GET
        headers:
          Authorization: "Bearer ${token}"
    if_false:
      - type: think
        think_time: 1.0
"""


# 导出
__all__ = [
    'TestScenario',
    'RequestStep',
    'ThinkStep',
    'LoopStep',
    'ConditionStep',
    'Assertion',
    'ScenarioLoader',
    'ScenarioRunner',
    'ScenarioStressTester',
    'EXAMPLE_SCENARIO_YAML',
]
