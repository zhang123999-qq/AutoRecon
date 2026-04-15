#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部工具集成模块 v2.3
集成 subfinder, nmap, httpx 等专业安全工具
"""

import os
import shutil
import platform

# 添加项目路径
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import Logger, CommandRunner
from config import CONFIG


class ExternalToolManager:
    """外部工具管理器"""
    
    # 工具配置
    TOOLS = {
        'subfinder': {
            'description': '子域名收集工具',
            'install': {
                'windows': 'go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest',
                'linux': 'go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest',
                'mac': 'brew install subfinder'
            },
            'check_cmd': 'subfinder -version',
            'path_hints': {
                'windows': [
                    os.path.expanduser(r'~\go\bin\subfinder.exe'),
                    r'C:\Program Files\Go\bin\subfinder.exe'
                ]
            }
        },
        'nmap': {
            'description': '端口扫描工具',
            'install': {
                'windows': 'winget install Insecure.Nmap',
                'linux': 'sudo apt install nmap',
                'mac': 'brew install nmap'
            },
            'check_cmd': 'nmap --version',
            'path_hints': {
                'windows': [
                    r'C:\Program Files (x86)\Nmap\nmap.exe',
                    r'C:\Program Files\Nmap\nmap.exe'
                ]
            }
        },
        'httpx': {
            'description': 'HTTP探测工具',
            'install': {
                'windows': 'go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest',
                'linux': 'go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest',
                'mac': 'brew install httpx'
            },
            'check_cmd': 'httpx -version',
            'path_hints': {
                'windows': [
                    os.path.expanduser(r'~\go\bin\httpx.exe'),
                    r'C:\Program Files\Go\bin\httpx.exe'
                ]
            }
        },
        'naabu': {
            'description': '端口扫描工具',
            'install': {
                'windows': 'go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest',
                'linux': 'go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest',
                'mac': 'brew install naabu'
            },
            'check_cmd': 'naabu -version',
            'path_hints': {
                'windows': [
                    os.path.expanduser(r'~\go\bin\naabu.exe')
                ]
            }
        },
        'nuclei': {
            'description': '漏洞扫描工具',
            'install': {
                'windows': 'go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest',
                'linux': 'go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest',
                'mac': 'brew install nuclei'
            },
            'check_cmd': 'nuclei -version',
            'path_hints': {
                'windows': [
                    os.path.expanduser(r'~\go\bin\nuclei.exe')
                ]
            }
        }
    }
    
    def __init__(self):
        self.available_tools = {}
        self.tool_paths = {}
        self.system = platform.system().lower()
        self._check_all_tools()
    
    def _find_tool_path(self, tool_name):
        """查找工具路径"""
        tool = self.TOOLS.get(tool_name)
        if not tool:
            return None
        
        # 先检查 PATH
        path = shutil.which(tool_name)
        if path:
            return path
        
        # 检查预设路径
        path_hints = tool.get('path_hints', {}).get(self.system, [])
        for hint in path_hints:
            if os.path.exists(hint):
                return hint
        
        return None
    
    def _check_tool(self, tool_name):
        """检查工具是否可用"""
        if tool_name not in self.TOOLS:
            return False
        
        tool = self.TOOLS[tool_name]
        tool_path = self._find_tool_path(tool_name)
        
        if tool_path:
            self.tool_paths[tool_name] = tool_path
            return True
        
        return False
    
    def _check_all_tools(self):
        """检查所有工具"""
        for tool_name in self.TOOLS:
            self.available_tools[tool_name] = self._check_tool(tool_name)
    
    def get_tool_path(self, tool_name):
        """获取工具路径"""
        return self.tool_paths.get(tool_name) or shutil.which(tool_name)
    
    def get_available_tools(self):
        """获取可用工具列表"""
        return [name for name, available in self.available_tools.items() if available]
    
    def get_missing_tools(self):
        """获取缺失工具列表"""
        return [name for name, available in self.available_tools.items() if not available]
    
    def print_status(self):
        """打印工具状态"""
        Logger.info("外部工具状态:")
        for name, available in self.available_tools.items():
            status = "[+] 已安装" if available else "[-] 未安装"
            path = self.tool_paths.get(name, '')
            path_info = f" ({path})" if path else ""
            print(f"  {status} {name}: {self.TOOLS[name]['description']}{path_info}")


class SubfinderRunner:
    """Subfinder运行器"""
    
    def __init__(self):
        self.manager = ExternalToolManager()
        self.available = self.manager.available_tools.get('subfinder', False)
        self.path = self.manager.get_tool_path('subfinder')
    
    def run(self, domain, output_file=None):
        """运行subfinder
        
        使用安全的参数列表方式执行，防止命令注入。
        """
        if not self.available:
            Logger.warn("subfinder 未安装，使用内置子域名收集")
            return None
        
        Logger.info(f"使用 subfinder 收集 {domain} 的子域名...")
        
        # 构建参数列表（安全方式）
        args = ['-d', domain, '-silent']
        
        if output_file:
            args.extend(['-o', output_file])
        
        # 使用 run_safe 方法，防止命令注入
        result = CommandRunner.run_safe(self.path, args, timeout=300)
        
        if result['success']:
            subdomains = result['stdout'].strip().split('\n')
            subdomains = [s.strip() for s in subdomains if s.strip()]
            Logger.success(f"subfinder 发现 {len(subdomains)} 个子域名")
            return subdomains
        
        return None


class NmapRunner:
    """Nmap运行器"""
    
    def __init__(self):
        self.manager = ExternalToolManager()
        self.available = self.manager.available_tools.get('nmap', False)
        self.path = self.manager.get_tool_path('nmap')
    
    def run(self, target, ports=None, scan_type='quick'):
        """运行nmap扫描
        
        Args:
            target: 目标IP或域名
            ports: 端口列表
            scan_type: 扫描类型 (quick, full, service, vuln)
            
        Security:
            使用参数列表方式执行，防止命令注入。
        """
        if not self.available:
            Logger.warn("nmap 未安装，使用内置端口扫描")
            return None
        
        Logger.info(f"使用 nmap 扫描 {target}...")
        
        # 构建参数列表（安全方式）
        args = []
        
        # 扫描类型
        if scan_type == 'quick':
            args.extend(['-T4', '-F'])  # 快速扫描，常用端口
        elif scan_type == 'full':
            args.append('-p-')  # 全端口
        elif scan_type == 'service':
            args.extend(['-sV', '-sC'])  # 服务版本检测
        elif scan_type == 'vuln':
            args.append('--script=vuln')  # 漏洞扫描
        
        if ports:
            args.extend(['-p', ','.join(map(str, ports))])
        
        args.append(target)
        
        # 使用 run_safe 方法，防止命令注入
        result = CommandRunner.run_safe(self.path, args, timeout=600)
        
        if result['success']:
            Logger.success(f"nmap 扫描完成")
            return result['stdout']
        
        return None


class HttpxRunner:
    """Httpx运行器"""
    
    def __init__(self):
        self.manager = ExternalToolManager()
        self.available = self.manager.available_tools.get('httpx', False)
        self.path = self.manager.get_tool_path('httpx')
    
    def run(self, urls, output_file=None):
        """运行httpx探测
        
        Args:
            urls: URL列表或文件路径
            output_file: 输出文件
            
        Security:
            使用参数列表方式执行，防止命令注入。
        """
        if not self.available:
            Logger.warn("httpx 未安装，使用内置HTTP探测")
            return None
        
        Logger.info(f"使用 httpx 探测存活...")
        
        # 构建参数列表（安全方式）
        args = ['-silent', '-status-code', '-title', '-tech-detect']
        
        # 判断是文件还是列表
        if isinstance(urls, str) and os.path.exists(urls):
            args.extend(['-l', urls])
        else:
            # 写入临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for url in urls:
                    f.write(url + '\n')
                temp_file = f.name
            args.extend(['-l', temp_file])
        
        if output_file:
            args.extend(['-o', output_file])
        
        # 使用 run_safe 方法，防止命令注入
        result = CommandRunner.run_safe(self.path, args, timeout=300)
        
        if result['success']:
            lines = result['stdout'].strip().split('\n')
            Logger.success(f"httpx 探测完成，发现 {len(lines)} 个存活服务")
            return lines
        
        return None


class ExternalToolsScanner:
    """外部工具扫描器"""
    
    def __init__(self):
        self.manager = ExternalToolManager()
        self.subfinder = SubfinderRunner()
        self.nmap = NmapRunner()
        self.httpx = HttpxRunner()
    
    def print_tool_status(self):
        """打印工具状态"""
        self.manager.print_status()
    
    def run_full_scan(self, target):
        """运行完整扫描"""
        results = {
            'subfinder': None,
            'nmap': None,
            'httpx': None
        }
        
        # Subfinder
        if self.subfinder.available:
            results['subfinder'] = self.subfinder.run(target)
        
        # Nmap
        if self.nmap.available:
            results['nmap'] = self.nmap.run(target, scan_type='quick')
        
        # Httpx
        if self.httpx.available and results['subfinder']:
            urls = [f"http://{d}" for d in results['subfinder']]
            results['httpx'] = self.httpx.run(urls)
        
        return results


if __name__ == '__main__':
    manager = ExternalToolManager()
    manager.print_status()
    
    print(f"\n可用工具: {manager.get_available_tools()}")
    print(f"缺失工具: {manager.get_missing_tools()}")
