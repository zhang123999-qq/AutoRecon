#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全修复验证测试
测试所有安全修复是否正确实施
"""

import sys
import os
import ast
import unittest

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStressScenarioSecurity(unittest.TestCase):
    """测试 stress_scenario.py 的 AST 白名单安全修复"""
    
    def setUp(self):
        """设置测试环境"""
        from modules.stress_scenario import ScenarioRunner, TestScenario
        # 创建一个简单的测试场景
        self.scenario = TestScenario(
            name="test",
            base_url="http://test.local",
            variables={"status": 200, "count": 20, "name": "test", "value": 50, "active": True, "items": "a", "x": 50}
        )
        self.executor = ScenarioRunner(scenario=self.scenario)
    
    def test_allowed_simple_comparison(self):
        """测试允许的简单比较表达式"""
        # 应该通过的表达式
        safe_conditions = [
            "status == 200",
            "count > 10",
            "name == 'test'",
            "value < 100 and active == True",
            "items in ['a', 'b', 'c']",
            "x >= 0 and x <= 100",
        ]
        
        for condition in safe_conditions:
            try:
                result = self.executor._safe_eval_condition(
                    condition, 
                    {"status": 200, "count": 20, "name": "test", "value": 50, "active": True, "items": "a", "x": 50}
                )
                self.assertIsInstance(result, bool, f"条件 {condition} 应返回布尔值")
                print(f"✅ 通过: {condition}")
            except Exception as e:
                self.fail(f"安全表达式 {condition} 不应抛出异常: {e}")
    
    def test_blocked_dangerous_expressions(self):
        """测试阻止的危险表达式"""
        # 应该被阻止的危险表达式
        dangerous_conditions = [
            "__import__('os').system('rm -rf /')",  # 模块导入
            "open('/etc/passwd').read()",           # 文件操作
            "eval('1+1')",                          # 嵌套 eval
            "exec('print(1)')",                     # exec
            "().__class__.__bases__",               # 类型操作
            "lambda x: x",                          # lambda
        ]
        
        for condition in dangerous_conditions:
            with self.assertRaises(ValueError, msg=f"危险表达式应被阻止: {condition}"):
                self.executor._safe_eval_condition(condition, {})
                print(f"❌ 未阻止: {condition}")
    
    def test_ast_whitelist_completeness(self):
        """测试 AST 白名单完整性"""
        allowed_nodes = self.executor._ALLOWED_AST_NODES
        
        # 必须包含的节点
        required_nodes = {
            ast.Expression, ast.BoolOp, ast.Compare, ast.BinOp,
            ast.Constant, ast.Name, ast.And, ast.Or,
            ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        }
        
        for node in required_nodes:
            self.assertIn(node, allowed_nodes, f"白名单应包含 {node.__name__}")
        
        # 必须排除的危险节点
        forbidden_nodes = {
            ast.Import, ast.ImportFrom,  # 导入
            ast.Call,                     # 函数调用
            ast.FunctionDef,              # 函数定义
            ast.ClassDef,                 # 类定义
            ast.Lambda,                   # Lambda
            ast.Attribute,                # 属性访问（防止 __class__.__bases__ 等攻击）
        }
        
        for node in forbidden_nodes:
            self.assertNotIn(node, allowed_nodes, f"白名单不应包含 {node.__name__}")


class TestCommandRunnerSecurity(unittest.TestCase):
    """测试 utils.py 的 CommandRunner 安全修复"""
    
    def test_default_shell_false(self):
        """测试默认 shell=False"""
        from core.utils import CommandRunner
        
        # 检查 run 方法的默认参数
        import inspect
        sig = inspect.signature(CommandRunner.run)
        shell_param = sig.parameters.get('shell')
        
        self.assertIsNotNone(shell_param, "run 方法应有 shell 参数")
        self.assertEqual(shell_param.default, False, "shell 默认值应为 False")
    
    def test_run_safe_method_exists(self):
        """测试 run_safe 方法存在"""
        from core.utils import CommandRunner
        
        self.assertTrue(hasattr(CommandRunner, 'run_safe'), "应有 run_safe 方法")
    
    def test_command_whitelist(self):
        """测试命令白名单"""
        from core.utils import CommandRunner
        
        # 白名单中的命令
        self.assertTrue(
            CommandRunner._validate_shell_command("nmap -sV target"),
            "nmap 应在白名单中"
        )
        
        # 不在白名单中的命令
        self.assertFalse(
            CommandRunner._validate_shell_command("rm -rf /"),
            "rm 不应在白名单中"
        )
    
    def test_shell_true_validation(self):
        """测试 shell=True 时的验证"""
        from core.utils import CommandRunner
        
        # 不在白名单的命令应被阻止
        result = CommandRunner.run("echo test", shell=True)
        self.assertFalse(result['success'], "非白名单命令应被阻止")
        self.assertIn('Security', result.get('error', ''), "应返回安全错误")


class TestHTTPClientSSRFProtection(unittest.TestCase):
    """测试 http.py 的 SSRF 防护"""
    
    def test_ssrf_error_exists(self):
        """测试 SSRFError 异常存在"""
        from core.http import SSRFError
        
        self.assertTrue(issubclass(SSRFError, Exception), "SSRFError 应是 Exception 子类")
    
    def test_blocked_ip_ranges(self):
        """测试内网 IP 黑名单"""
        from core.http import BLOCKED_IP_RANGES
        
        # 应包含的网段
        required_ranges = [
            '10.0.0.0/8',
            '172.16.0.0/12',
            '192.168.0.0/16',
            '127.0.0.0/8',
        ]
        
        for cidr in required_ranges:
            self.assertIn(cidr, BLOCKED_IP_RANGES, f"黑名单应包含 {cidr}")
    
    def test_ssrf_check_function(self):
        """测试 SSRF 检查函数"""
        from core.http import _check_ssrf, SSRFError
        
        # 公网 IP 应通过（如果能解析）
        # 注意：这个测试需要网络连接
        
        # 内网 IP 应被阻止
        internal_urls = [
            "http://127.0.0.1/admin",
            "http://192.168.1.1/config",
            "http://10.0.0.1/internal",
            "http://172.16.0.1/private",
        ]
        
        for url in internal_urls:
            with self.assertRaises(SSRFError, msg=f"应阻止内网 URL: {url}"):
                _check_ssrf(url)


class TestDeprecationWarnings(unittest.TestCase):
    """测试废弃警告"""
    
    def test_http_client_has_deprecation_docstring(self):
        """测试 HTTPClient 有废弃文档字符串"""
        from core.http import HTTPClient
        
        # 检查模块文档字符串中是否有废弃警告
        import core.http as http_module
        self.assertIn('废弃', http_module.__doc__ or '', "模块文档应包含废弃警告")
    
    def test_subdomain_collector_has_deprecation_docstring(self):
        """测试 SubdomainCollector 有废弃文档字符串"""
        import modules.subdomain as subdomain_module
        
        # 检查模块文档字符串中是否有废弃警告
        self.assertIn('废弃', subdomain_module.__doc__ or '', "模块文档应包含废弃警告")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("AutoRecon 安全修复验证测试")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestStressScenarioSecurity))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandRunnerSecurity))
    suite.addTests(loader.loadTestsFromTestCase(TestHTTPClientSSRFProtection))
    suite.addTests(loader.loadTestsFromTestCase(TestDeprecationWarnings))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    print(f"测试总数: {result.testsRun}")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ 所有安全修复验证通过！")
    else:
        print("\n❌ 部分测试失败，请检查修复实现。")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
