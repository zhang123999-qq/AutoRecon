#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon 源码质量检测工具
检查代码风格、文档字符串、类型注解、代码复杂度等
"""

import os
import ast
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional


@dataclass
class QualityIssue:
    """质量问题"""
    file: str
    line: int
    category: str
    severity: str  # error, warning, info
    message: str


class CodeQualityChecker:
    """代码质量检查器"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issues: List[QualityIssue] = []
        self.stats = {
            'total_files': 0,
            'total_lines': 0,
            'total_functions': 0,
            'total_classes': 0,
            'files_with_issues': set(),
        }
    
    def check_all(self):
        """运行所有检查"""
        print("=" * 70)
        print("AutoRecon 源码质量检测")
        print("=" * 70)
        
        # 获取所有 Python 文件
        python_files = list(self.project_path.rglob("*.py"))
        python_files = [f for f in python_files if '.venv' not in str(f)]
        
        self.stats['total_files'] = len(python_files)
        
        print(f"\n📁 扫描 {len(python_files)} 个 Python 文件...\n")
        
        # 检查每个文件
        for file_path in python_files:
            self.check_file(file_path)
        
        # 打印报告
        self.print_report()
    
    def check_file(self, file_path: Path):
        """检查单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            self.stats['total_lines'] += len(lines)
            
            # 相对路径
            rel_path = str(file_path.relative_to(self.project_path))
            
            # 1. 语法检查
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.add_issue(rel_path, e.lineno or 0, 'syntax', 'error', f'语法错误: {e.msg}')
                return
            
            # 2. 文档字符串检查
            self.check_docstrings(rel_path, tree)
            
            # 3. 类型注解检查
            self.check_type_hints(rel_path, tree)
            
            # 4. 函数复杂度检查
            self.check_complexity(rel_path, tree)
            
            # 5. 代码风格检查
            self.check_style(rel_path, lines)
            
            # 6. 安全问题检查
            self.check_security(rel_path, content, tree)
            
            # 统计
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self.stats['total_functions'] += 1
                elif isinstance(node, ast.ClassDef):
                    self.stats['total_classes'] += 1
        
        except Exception as e:
            print(f"  ⚠️ 无法检查 {file_path.name}: {e}")
    
    def check_docstrings(self, file_path: str, tree: ast.Module):
        """检查文档字符串"""
        # 模块文档字符串
        if not ast.get_docstring(tree):
            # 只有核心模块要求文档字符串
            if 'core/' in file_path or 'modules/' in file_path:
                self.add_issue(file_path, 1, 'docstring', 'info', '缺少模块文档字符串')
        
        # 类和函数文档字符串
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not ast.get_docstring(node):
                    self.add_issue(file_path, node.lineno, 'docstring', 'warning', 
                                   f'类 {node.name} 缺少文档字符串')
            
            elif isinstance(node, ast.FunctionDef):
                # 跳过私有方法
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue
                
                if not ast.get_docstring(node):
                    # 只有公开方法需要文档字符串
                    if len(node.body) > 3:  # 超过3行的函数
                        self.add_issue(file_path, node.lineno, 'docstring', 'info',
                                       f'函数 {node.name} 缺少文档字符串')
    
    def check_type_hints(self, file_path: str, tree: ast.Module):
        """检查类型注解"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查参数类型注解
                args = node.args
                total_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
                annotated_args = sum(1 for arg in args.args + args.posonlyargs + args.kwonlyargs 
                                     if arg.annotation)
                
                # 检查返回值类型注解
                has_return_annotation = node.returns is not None
                
                # 公开函数应该有类型注解
                if not node.name.startswith('_') and total_args > 0:
                    if annotated_args < total_args * 0.5:  # 少于50%参数有注解
                        self.add_issue(file_path, node.lineno, 'type_hint', 'info',
                                       f'函数 {node.name} 参数类型注解不完整 ({annotated_args}/{total_args})')
                    
                    if not has_return_annotation and len(node.body) > 2:
                        self.add_issue(file_path, node.lineno, 'type_hint', 'info',
                                       f'函数 {node.name} 缺少返回值类型注解')
    
    def check_complexity(self, file_path: str, tree: ast.Module):
        """检查函数复杂度"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 计算圈复杂度（简化版）
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                
                if complexity > 15:
                    self.add_issue(file_path, node.lineno, 'complexity', 'warning',
                                   f'函数 {node.name} 复杂度过高 ({complexity})')
                elif complexity > 10:
                    self.add_issue(file_path, node.lineno, 'complexity', 'info',
                                   f'函数 {node.name} 复杂度较高 ({complexity})')
    
    def check_style(self, file_path: str, lines: List[str]):
        """检查代码风格"""
        for i, line in enumerate(lines, 1):
            # 行长度检查
            if len(line) > 120:
                self.add_issue(file_path, i, 'style', 'info', f'行过长 ({len(line)} 字符)')
            
            # 尾随空格
            if line.rstrip() != line and line.strip():
                self.add_issue(file_path, i, 'style', 'info', '行尾有空格')
            
            # 导入检查
            if line.startswith('import ') or line.startswith('from '):
                # 检查是否使用通配符导入
                if 'import *' in line:
                    self.add_issue(file_path, i, 'style', 'warning', '使用通配符导入')
            
            # bare except 检查
            if re.match(r'^\s*except\s*:', line):
                self.add_issue(file_path, i, 'style', 'warning', '使用裸 except 子句')
            
            # TODO/FIXME 检查
            if 'TODO' in line or 'FIXME' in line:
                self.add_issue(file_path, i, 'todo', 'info', '包含 TODO/FIXME 注释')
    
    def _check_dangerous_functions(self, file_path: str, node: ast.Call) -> None:
        """检查危险的 eval/exec 调用"""
        if isinstance(node.func, ast.Name):
            if node.func.id in ('eval', 'exec'):
                self.add_issue(file_path, node.lineno, 'security', 'warning',
                               f'使用 {node.func.id}() 可能存在安全风险')
    
    def _check_shell_injection(self, file_path: str, node: ast.keyword) -> None:
        """检查 shell=True 命令注入风险"""
        if node.arg == 'shell':
            if isinstance(node.value, ast.Constant) and node.value.value == True:
                self.add_issue(file_path, node.lineno, 'security', 'warning',
                               '使用 shell=True 可能存在命令注入风险')
    
    def _check_hardcoded_credentials(self, file_path: str, node: ast.Assign) -> None:
        """检查硬编码凭证"""
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            
            name_lower = target.id.lower()
            sensitive_words = ['password', 'passwd', 'secret', 'api_key', 'token']
            
            if not any(word in name_lower for word in sensitive_words):
                continue
            
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            
            value = node.value.value
            # 排除短字符串、占位符和枚举值
            if len(value) <= 3 or value.startswith('${') or value in ['xxx', 'test', 'example']:
                continue
            
            # 排除枚举定义
            enum_values = ['aws_key', 'aws_secret', 'github_token', 'api_key', 'private_key',
                          'password', 'database_url', 'jwt_secret', 'stripe_key', 
                          'slack_token', 'google_api_key']
            if value.lower() in enum_values:
                continue
            
            self.add_issue(file_path, node.lineno, 'security', 'warning',
                           f'可能的硬编码凭证: {target.id}')
    
    def check_security(self, file_path: str, content: str, tree: ast.Module) -> None:
        """检查安全问题"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self._check_dangerous_functions(file_path, node)
            elif isinstance(node, ast.keyword):
                self._check_shell_injection(file_path, node)
            elif isinstance(node, ast.Assign):
                self._check_hardcoded_credentials(file_path, node)
    
    def add_issue(self, file: str, line: int, category: str, severity: str, message: str):
        """添加问题"""
        self.issues.append(QualityIssue(file, line, category, severity, message))
        self.stats['files_with_issues'].add(file)
    
    def print_report(self):
        """打印报告"""
        # 按严重程度分组
        by_severity = defaultdict(list)
        for issue in self.issues:
            by_severity[issue.severity].append(issue)
        
        # 按类别分组
        by_category = defaultdict(list)
        for issue in self.issues:
            by_category[issue.category].append(issue)
        
        print("\n" + "=" * 70)
        print("📊 统计摘要")
        print("=" * 70)
        print(f"  文件总数: {self.stats['total_files']}")
        print(f"  代码行数: {self.stats['total_lines']}")
        print(f"  函数数量: {self.stats['total_functions']}")
        print(f"  类数量: {self.stats['total_classes']}")
        print(f"  有问题的文件: {len(self.stats['files_with_issues'])}")
        
        print("\n" + "=" * 70)
        print("📋 问题统计")
        print("=" * 70)
        
        severity_icons = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}
        
        for severity in ['error', 'warning', 'info']:
            count = len(by_severity[severity])
            icon = severity_icons.get(severity, '•')
            print(f"  {icon} {severity.upper()}: {count}")
        
        print("\n" + "=" * 70)
        print("📁 问题分类")
        print("=" * 70)
        
        category_names = {
            'syntax': '语法错误',
            'docstring': '文档字符串',
            'type_hint': '类型注解',
            'complexity': '代码复杂度',
            'style': '代码风格',
            'security': '安全问题',
            'todo': 'TODO 注释',
        }
        
        for category, issues in sorted(by_category.items(), key=lambda x: -len(x[1])):
            name = category_names.get(category, category)
            print(f"  {name}: {len(issues)}")
        
        # 打印详细问题
        if by_severity['error']:
            print("\n" + "=" * 70)
            print("❌ 错误详情")
            print("=" * 70)
            for issue in by_severity['error'][:10]:
                print(f"  {issue.file}:{issue.line}")
                print(f"    {issue.message}")
        
        if by_severity['warning']:
            print("\n" + "=" * 70)
            print("⚠️ 警告详情")
            print("=" * 70)
            for issue in by_severity['warning'][:15]:
                print(f"  {issue.file}:{issue.line}")
                print(f"    {issue.message}")
        
        # 计算评分
        print("\n" + "=" * 70)
        print("📊 质量评分")
        print("=" * 70)
        
        # 基于问题数量计算评分
        errors = len(by_severity['error'])
        warnings = len(by_severity['warning'])
        infos = len(by_severity['info'])
        
        # 扣分规则（调整权重）
        score = 10.0
        score -= errors * 2.0  # 每个错误扣2分
        score -= warnings * 0.05  # 每个警告扣0.05分
        score -= infos * 0.002  # 每个信息扣0.002分
        score = max(0, min(10, score))  # 限制在0-10之间
        
        # 各维度评分
        print(f"\n  综合评分: {score:.1f}/10")
        
        # 分维度评分
        print("\n  分维度评分:")
        
        # 文档字符串
        doc_issues = len(by_category.get('docstring', []))
        doc_score = max(0, 10 - doc_issues * 0.1)
        print(f"    文档字符串: {doc_score:.1f}/10")
        
        # 类型注解 - 使用覆盖率计算
        type_issues = len(by_category.get('type_hint', []))
        # 假设每个类型注解问题对应一个缺少注解的参数/返回值
        # 估算总函数数量约为 type_issues / 3（平均每个函数3个注解点）
        total_functions = self.stats['total_functions']
        estimated_total_annotations = max(type_issues, total_functions * 2)  # 每个函数约2个注解点
        type_coverage = max(0, 1 - (type_issues / estimated_total_annotations)) if estimated_total_annotations > 0 else 1
        type_score = type_coverage * 10
        print(f"    类型注解: {type_score:.1f}/10")
        
        # 代码风格
        style_issues = len(by_category.get('style', []))
        style_score = max(0, 10 - style_issues * 0.05)
        print(f"    代码风格: {style_score:.1f}/10")
        
        # 安全性
        security_issues = len(by_category.get('security', []))
        security_score = max(0, 10 - security_issues * 0.5)
        print(f"    安全性: {security_score:.1f}/10")
        
        # 复杂度
        complexity_issues = len(by_category.get('complexity', []))
        complexity_score = max(0, 10 - complexity_issues * 0.3)
        print(f"    代码复杂度: {complexity_score:.1f}/10")
        
        print("\n" + "=" * 70)
        print("✅ 检测完成")
        print("=" * 70)


if __name__ == '__main__':
    import sys
    
    project_path = sys.argv[1] if len(sys.argv) > 1 else '/mnt/f/AutoRecon'
    
    checker = CodeQualityChecker(project_path)
    checker.check_all()
