#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目录扫描模块

⚠️ 已废弃警告 ⚠
--------------
此模块已废弃，建议使用异步版本：
    from modules.async_dir_scanner import AsyncDirScanner

原因：
    1. 使用同步方式 + ThreadPoolExecutor，性能较差
    2. 使用旧版 HTTPClient，无 SSRF 防护
    3. 不符合项目异步架构

迁移示例：
    # 旧代码
    scanner = DirScanner(target)
    results = scanner.scan()
    
    # 新代码
    async with AsyncDirScanner(target) as scanner:
        results = await scanner.scan()

废弃版本: v3.3.0
移除版本: v4.0.0
"""

import warnings

# 显示废弃警告
warnings.warn(
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️  DirScanner 已废弃\n"
    "请使用: from modules.async_dir_scanner import AsyncDirScanner\n"
    "原因: 同步方式、无 SSRF 防护、性能较差\n"
    "废弃版本: v3.3.0 | 移除版本: v4.0.0\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    DeprecationWarning,
    stacklevel=2
)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import Logger, HTTPClient
from config import CONFIG, SENSITIVE_PATHS


class DirScanner:
    """目录扫描器"""
    
    def __init__(self, target, threads=None, timeout=None):
        self.target = target if target.startswith('http') else f"http://{target}"
        self.threads = threads or CONFIG.get('dir_threads', 10)
        self.timeout = timeout or CONFIG.get('timeout', 30)
        self.client = HTTPClient(timeout=5)
        self.found_paths = []
        self.sensitive_findings = []
    
    def _scan_single_path(self, path):
        """扫描单个路径"""
        url = f"{self.target}{path}"
        result = self.client.get(url)
        
        if result['status'] in [200, 301, 302, 403, 401]:
            return {
                'path': path,
                'url': url,
                'status': result['status'],
                'size': len(result.get('body', '')),
                'redirect': result['headers'].get('Location', '')
            }
        
        return None
    
    def scan(self, wordlist=None):
        """执行目录扫描"""
        paths = wordlist or CONFIG.get('dir_wordlist', [])
        Logger.info(f"正在扫描 {self.target} 的目录 ({len(paths)} 个路径)...")
        
        found = []
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._scan_single_path, path): path for path in paths}
            
            completed = 0
            total = len(paths)
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    found.append(result)
                    self.found_paths.append(result)
                
                completed += 1
                if completed % 20 == 0:
                    print(f"\r  进度: {completed}/{total} | 发现: {len(found)}", end='', flush=True)
        
        print()  # 换行
        Logger.success(f"发现 {len(found)} 个有效路径")
        
        return found
    
    def scan_sensitive(self):
        """扫描敏感文件和目录"""
        Logger.info(f"正在扫描敏感文件和目录...")
        
        found = []
        
        for path in SENSITIVE_PATHS:
            result = self._scan_single_path(path)
            
            if result and result['status'] in [200, 301, 302]:
                result['type'] = self._classify_sensitive_path(path)
                found.append(result)
                self.sensitive_findings.append(result)
                Logger.success(f"  发现敏感文件: {path} (状态: {result['status']})")
        
        if not found:
            Logger.info("  未发现敏感文件")
        
        return found
    
    def _classify_sensitive_path(self, path):
        """分类敏感路径
        
        使用模式匹配字典替代多层if-elif，降低圈复杂度。
        
        Args:
            path: 路径字符串
            
        Returns:
            分类名称
        """
        path_lower = path.lower()
        
        # 模式匹配规则（按优先级排序）
        patterns = [
            # (关键词元组, 分类名称)
            (('.git', '.svn', '.hg'), '版本控制'),
            (('.env',), '配置文件'),
            (('config', 'settings'), '配置文件'),
            (('backup', '.sql', '.zip'), '备份文件'),
            (('admin', 'login', 'manager'), '后台入口'),
            (('phpinfo', 'info.php'), '信息泄露'),
            (('swagger', 'api-docs', 'graphql'), 'API文档'),
        ]
        
        for keywords, category in patterns:
            if any(kw in path_lower for kw in keywords):
                return category
        
        return '其他敏感文件'
    
    def run(self, wordlist=None, scan_sensitive=True):
        """执行完整目录扫描"""
        results = {
            'directories': [],
            'sensitive': []
        }
        
        # 扫描常规目录
        results['directories'] = self.scan(wordlist)
        
        # 扫描敏感文件
        if scan_sensitive:
            results['sensitive'] = self.scan_sensitive()
        
        return results
    
    def get_admin_pages(self):
        """获取后台页面"""
        return [p for p in self.found_paths if 'admin' in p['path'].lower() or 'login' in p['path'].lower()]
    
    def get_api_endpoints(self):
        """获取API端点"""
        return [p for p in self.found_paths if 'api' in p['path'].lower()]


if __name__ == '__main__':
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = 'http://baidu.com'
    
    scanner = DirScanner(target)
    results = scanner.run()
    
    print(f"\n发现目录/文件:")
    for item in results['directories']:
        print(f"  {item['path']} ({item['status']})")
    
    if results['sensitive']:
        print(f"\n敏感文件:")
        for item in results['sensitive']:
            print(f"  [{item['type']}] {item['path']}")
