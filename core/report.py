#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告生成模块 - 支持JSON和HTML格式
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, output_dir: str = 'reports') -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def save_json(self, target: str, data: Dict[str, Any]) -> str:
        """保存JSON报告
        
        Args:
            target: 目标名称
            data: 报告数据
        
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理目标名称中的非法字符
        safe_target = "".join(c if c.isalnum() or c in '-._' else '_' for c in target)
        filename = f"recon_{safe_target}_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        report = {
            'meta': {
                'tool': '信息收集自动化工具',
                'version': '2.3',
                'target': target,
                'timestamp': datetime.now().isoformat(),
            },
            'data': data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def save_html(self, target: str, data: Dict[str, Any]) -> str:
        """保存HTML报告
        
        Args:
            target: 目标名称
            data: 报告数据
        
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_target = "".join(c if c.isalnum() or c in '-._' else '_' for c in target)
        filename = f"recon_{safe_target}_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)
        
        html = self._generate_html(target, data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return filepath
    
    def _generate_html(self, target: str, data: Dict[str, Any]) -> str:
        """生成HTML内容"""
        
        sections = []
        
        # 子域名部分
        if 'subdomain' in data:
            subdomain_data = data['subdomain']
            domains = subdomain_data.get('domains', [])
            sections.append(f"""
            <div class="section">
                <h2>🌐 子域名收集</h2>
                <p>共发现 <strong>{subdomain_data.get('count', 0)}</strong> 个子域名</p>
                <table>
                    <tr><th>子域名</th><th>IP地址</th><th>来源</th></tr>
                    {self._render_subdomains(domains[:50])}
                </table>
            </div>
            """)
        
        # 端口部分
        if 'port' in data:
            port_data = data['port']
            sections.append(f"""
            <div class="section">
                <h2>🔌 端口扫描</h2>
                <p>开放端口: {port_data.get('open_ports', [])}</p>
            </div>
            """)
        
        # CDN部分
        if 'cdn' in data:
            cdn = data['cdn'].get('cdn', '未检测到')
            sections.append(f"""
            <div class="section">
                <h2>🚀 CDN检测</h2>
                <p>CDN厂商: <strong>{cdn}</strong></p>
            </div>
            """)
        
        # WAF部分
        if 'waf' in data:
            waf = data['waf'].get('waf', '未检测到')
            sections.append(f"""
            <div class="section">
                <h2>🛡️ WAF检测</h2>
                <p>WAF厂商: <strong>{waf}</strong></p>
            </div>
            """)
        
        # 敏感信息部分
        if 'sensitive' in data:
            sensitive = data['sensitive']
            total = len(sensitive.get('files', [])) + len(sensitive.get('js_files', []))
            if total > 0:
                sections.append(f"""
                <div class="section warning">
                    <h2>⚠️ 敏感信息检测</h2>
                    <p>发现 <strong>{total}</strong> 处敏感信息泄露</p>
                </div>
                """)
        
        # 子域名接管部分
        if 'takeover' in data:
            takeover = data['takeover']
            if takeover.get('count', 0) > 0:
                sections.append(f"""
                <div class="section danger">
                    <h2>🔴 子域名接管风险</h2>
                    <p>发现 <strong>{takeover['count']}</strong> 个存在接管风险的子域名</p>
                </div>
                """)
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信息收集报告 - {target}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #eee; padding: 20px; line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px; border-radius: 10px; margin-bottom: 20px; text-align: center;
        }}
        .header h1 {{ font-size: 2em; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.8; }}
        .section {{ 
            background: #16213e; border-radius: 10px; padding: 20px; margin-bottom: 15px;
        }}
        .section h2 {{ color: #667eea; margin-bottom: 15px; }}
        .section.warning {{ border-left: 4px solid #f39c12; }}
        .section.danger {{ border-left: 4px solid #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #2a3f5f; }}
        th {{ background: #1a1a2e; color: #667eea; }}
        tr:hover {{ background: #1a1a2e; }}
        .badge {{ 
            display: inline-block; padding: 3px 10px; border-radius: 20px; 
            font-size: 0.85em; margin: 2px;
        }}
        .badge-success {{ background: #27ae60; }}
        .badge-warning {{ background: #f39c12; }}
        .badge-danger {{ background: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 信息收集报告</h1>
            <div class="meta">
                <span>目标: {target}</span> | 
                <span>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
        </div>
        {''.join(sections)}
    </div>
</body>
</html>
        """
        
        return html
    
    def _render_subdomains(self, domains: List[Dict]) -> str:
        """渲染子域名表格行"""
        rows = []
        for d in domains:
            subdomain = d.get('subdomain', 'N/A')
            ip = d.get('ip', 'N/A')
            source = d.get('source', 'dns')
            rows.append(f"<tr><td>{subdomain}</td><td>{ip}</td><td>{source}</td></tr>")
        return ''.join(rows)
    
    def save_txt(self, target: str, content: str) -> str:
        """保存文本报告
        
        Args:
            target: 目标名称
            content: 报告内容
        
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_target = "".join(c if c.isalnum() or c in '-._' else '_' for c in target)
        filename = f"recon_{safe_target}_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filepath
