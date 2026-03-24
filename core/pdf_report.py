#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.1 - PDF 报告生成器
生成专业的安全扫描报告
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from io import BytesIO

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib.colors import HexColor, black, white, grey
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, ListFlowable, ListItem
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    # 创建占位符，避免导入错误
    HexColor = lambda x: x
    black = 'black'
    white = 'white'
    grey = 'grey'


class PDFReportGenerator:
    """
    PDF 报告生成器
    
    功能：
    - 生成专业的安全报告
    - 支持中文
    - 自定义样式
    - 风险统计图表
    """
    
    # 颜色定义
    COLORS = {
        'primary': HexColor('#1a73e8'),
        'success': HexColor('#34a853'),
        'warning': HexColor('#fbbc04'),
        'danger': HexColor('#ea4335'),
        'info': HexColor('#4285f4'),
        'dark': HexColor('#202124'),
        'light': HexColor('#f8f9fa'),
        'grey': HexColor('#5f6368'),
    }
    
    def __init__(self, title: str = "AutoRecon Security Report"):
        """
        初始化生成器
        
        Args:
            title: 报告标题
        """
        if not HAS_REPORTLAB:
            raise ImportError("请安装 reportlab: pip install reportlab")
        
        self.title = title
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """设置自定义样式"""
        # 标题样式
        self.styles.add(ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=self.COLORS['primary'],
            spaceAfter=30,
            alignment=TA_CENTER,
        ))
        
        # 标题样式
        self.styles.add(ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=self.COLORS['dark'],
            spaceBefore=20,
            spaceAfter=10,
        ))
        
        # 副标题样式
        self.styles.add(ParagraphStyle(
            'CustomSubHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.COLORS['grey'],
            spaceBefore=15,
            spaceAfter=8,
        ))
        
        # 正文样式
        self.styles.add(ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['dark'],
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ))
        
        # 高危样式
        self.styles.add(ParagraphStyle(
            'HighRisk',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['danger'],
            fontName='Helvetica-Bold',
        ))
        
        # 中危样式
        self.styles.add(ParagraphStyle(
            'MediumRisk',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['warning'],
            fontName='Helvetica-Bold',
        ))
        
        # 低危样式
        self.styles.add(ParagraphStyle(
            'LowRisk',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.COLORS['success'],
            fontName='Helvetica-Bold',
        ))
    
    def generate(
        self, 
        scan_result: Dict[str, Any], 
        output_path: str,
        logo_path: str = None
    ) -> str:
        """
        生成 PDF 报告
        
        Args:
            scan_result: 扫描结果
            output_path: 输出路径
            logo_path: Logo 路径
            
        Returns:
            str: 生成的文件路径
        """
        # 创建文档
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        # 内容列表
        elements = []
        
        # 标题页
        elements.extend(self._create_title_page(scan_result, logo_path))
        elements.append(PageBreak())
        
        # 执行摘要
        elements.extend(self._create_executive_summary(scan_result))
        elements.append(PageBreak())
        
        # 扫描统计
        elements.extend(self._create_statistics(scan_result))
        elements.append(PageBreak())
        
        # 发现详情
        elements.extend(self._create_findings(scan_result))
        
        # 建议
        elements.extend(self._create_recommendations(scan_result))
        
        # 生成 PDF
        doc.build(elements)
        
        return output_path
    
    def _create_title_page(self, scan_result: Dict, logo_path: str = None) -> list:
        """创建标题页"""
        elements = []
        
        # Logo
        if logo_path and os.path.exists(logo_path):
            img = Image(logo_path, width=3*inch, height=1*inch)
            elements.append(img)
            elements.append(Spacer(1, 1*inch))
        
        # 标题
        elements.append(Paragraph(self.title, self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.5*inch))
        
        # 目标信息
        target = scan_result.get('target', 'N/A')
        elements.append(Paragraph(f"<b>Target:</b> {target}", self.styles['CustomBody']))
        
        # 扫描时间
        scan_time = scan_result.get('scan_time', datetime.now().isoformat())
        elements.append(Paragraph(f"<b>Scan Time:</b> {scan_time}", self.styles['CustomBody']))
        
        # 报告生成时间
        elements.append(Paragraph(
            f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.styles['CustomBody']
        ))
        
        # 版本
        elements.append(Paragraph(
            f"<b>Scanner Version:</b> AutoRecon v3.1.0",
            self.styles['CustomBody']
        ))
        
        return elements
    
    def _create_executive_summary(self, scan_result: Dict) -> list:
        """创建执行摘要"""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
        
        # 风险等级统计
        high_count = scan_result.get('high_risk_count', 0)
        medium_count = scan_result.get('medium_risk_count', 0)
        low_count = scan_result.get('low_risk_count', 0)
        
        # 总体评估
        if high_count > 0:
            risk_level = "HIGH RISK"
            risk_style = 'HighRisk'
        elif medium_count > 0:
            risk_level = "MEDIUM RISK"
            risk_style = 'MediumRisk'
        else:
            risk_level = "LOW RISK"
            risk_style = 'LowRisk'
        
        elements.append(Paragraph(
            f"Overall Risk Level: {risk_level}",
            self.styles[risk_style]
        ))
        elements.append(Spacer(1, 0.3*inch))
        
        # 摘要文本
        summary = f"""
        This security assessment identified a total of {high_count + medium_count + low_count} findings.
        Among them, {high_count} are high severity, {medium_count} are medium severity, 
        and {low_count} are low severity.
        """
        elements.append(Paragraph(summary, self.styles['CustomBody']))
        
        # 风险统计表格
        risk_data = [
            ['Severity', 'Count', 'Status'],
            ['High', str(high_count), 'Action Required' if high_count > 0 else 'OK'],
            ['Medium', str(medium_count), 'Review Recommended' if medium_count > 0 else 'OK'],
            ['Low', str(low_count), 'Monitor'],
        ]
        
        table = Table(risk_data, colWidths=[2*inch, 1*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, 1), HexColor('#ffeeee') if high_count > 0 else white),
            ('BACKGROUND', (0, 2), (-1, 2), HexColor('#fff8e1') if medium_count > 0 else white),
            ('BACKGROUND', (0, 3), (-1, 3), HexColor('#e8f5e9')),
            ('GRID', (0, 0), (-1, -1), 1, grey),
        ]))
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(table)
        
        return elements
    
    def _create_statistics(self, scan_result: Dict) -> list:
        """创建扫描统计"""
        elements = []
        
        elements.append(Paragraph("Scan Statistics", self.styles['CustomHeading']))
        
        # 统计数据
        stats_data = [
            ['Metric', 'Value'],
            ['Total Requests', str(scan_result.get('total_requests', 0))],
            ['Scan Duration', f"{scan_result.get('duration', 0):.2f} seconds"],
            ['Subdomains Found', str(scan_result.get('subdomain_count', 0))],
            ['Open Ports', str(scan_result.get('open_ports', 0))],
            ['Vulnerabilities', str(scan_result.get('vuln_count', 0))],
            ['Sensitive Files', str(scan_result.get('sensitive_count', 0))],
            ['Technologies Detected', str(scan_result.get('tech_count', 0))],
        ]
        
        table = Table(stats_data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['info']),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, self.COLORS['light']]),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_findings(self, scan_result: Dict) -> list:
        """创建发现详情"""
        elements = []
        
        elements.append(Paragraph("Detailed Findings", self.styles['CustomHeading']))
        
        # 子域名
        subdomains = scan_result.get('subdomains', [])
        if subdomains:
            elements.append(Paragraph("Subdomains", self.styles['CustomSubHeading']))
            
            subdomain_data = [['#', 'Domain', 'IP Address', 'Status']]
            for i, sub in enumerate(subdomains[:20], 1):  # 限制数量
                if isinstance(sub, dict):
                    subdomain_data.append([
                        str(i),
                        sub.get('domain', 'N/A'),
                        sub.get('ip', 'N/A'),
                        sub.get('status', 'N/A'),
                    ])
                else:
                    subdomain_data.append([str(i), str(sub), '-', '-'])
            
            table = Table(subdomain_data, colWidths=[0.5*inch, 2.5*inch, 1.5*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['info']),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, grey),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 0.2*inch))
        
        # 漏洞
        vulnerabilities = scan_result.get('vulnerabilities', [])
        if vulnerabilities:
            elements.append(Paragraph("Vulnerabilities", self.styles['CustomSubHeading']))
            
            for i, vuln in enumerate(vulnerabilities[:15], 1):
                severity = vuln.get('severity', 'low').lower()
                
                if severity == 'high':
                    style = 'HighRisk'
                elif severity == 'medium':
                    style = 'MediumRisk'
                else:
                    style = 'LowRisk'
                
                elements.append(Paragraph(
                    f"<b>{i}. {vuln.get('name', 'Unknown')}</b> [{severity.upper()}]",
                    self.styles[style]
                ))
                elements.append(Paragraph(
                    f"   URL: {vuln.get('url', 'N/A')}",
                    self.styles['CustomBody']
                ))
                elements.append(Paragraph(
                    f"   {vuln.get('description', '')}",
                    self.styles['CustomBody']
                ))
                elements.append(Spacer(1, 0.1*inch))
        
        return elements
    
    def _create_recommendations(self, scan_result: Dict) -> list:
        """创建修复建议"""
        elements = []
        
        elements.append(PageBreak())
        elements.append(Paragraph("Recommendations", self.styles['CustomHeading']))
        
        recommendations = [
            {
                'title': 'Keep Software Updated',
                'description': 'Ensure all server software, frameworks, and libraries are up to date with the latest security patches.',
            },
            {
                'title': 'Implement Security Headers',
                'description': 'Configure security headers such as CSP, X-Frame-Options, and X-Content-Type-Options.',
            },
            {
                'title': 'Enable HTTPS',
                'description': 'Enforce HTTPS for all communications and configure proper SSL/TLS settings.',
            },
            {
                'title': 'Access Control',
                'description': 'Implement proper access controls and authentication mechanisms for sensitive endpoints.',
            },
            {
                'title': 'Regular Security Audits',
                'description': 'Conduct regular security assessments and penetration testing.',
            },
        ]
        
        for rec in recommendations:
            elements.append(Paragraph(f"<b>{rec['title']}</b>", self.styles['CustomBody']))
            elements.append(Paragraph(rec['description'], self.styles['CustomBody']))
            elements.append(Spacer(1, 0.1*inch))
        
        return elements


# ============== 使用示例 ==============

def example_usage():
    """示例：生成 PDF 报告"""
    
    if not HAS_REPORTLAB:
        print("[!] 请安装 reportlab: pip install reportlab")
        return
    
    # 模拟扫描结果
    scan_result = {
        'target': 'example.com',
        'scan_time': '2026-03-24 10:00:00',
        'duration': 45.5,
        'total_requests': 1500,
        'high_risk_count': 2,
        'medium_risk_count': 5,
        'low_risk_count': 10,
        'subdomain_count': 25,
        'open_ports': 3,
        'vuln_count': 17,
        'sensitive_count': 4,
        'tech_count': 8,
        'subdomains': [
            {'domain': 'www.example.com', 'ip': '1.2.3.4', 'status': '200'},
            {'domain': 'api.example.com', 'ip': '1.2.3.5', 'status': '200'},
        ],
        'vulnerabilities': [
            {'name': 'XSS Vulnerability', 'severity': 'high', 'url': '/search?q=test', 'description': 'Reflected XSS found'},
            {'name': 'Information Disclosure', 'severity': 'medium', 'url': '/debug', 'description': 'Debug endpoint exposed'},
        ],
    }
    
    # 生成报告
    generator = PDFReportGenerator("AutoRecon Security Report")
    output_path = generator.generate(scan_result, "reports/security_report.pdf")
    
    print(f"[+] 报告已生成: {output_path}")


if __name__ == "__main__":
    example_usage()
