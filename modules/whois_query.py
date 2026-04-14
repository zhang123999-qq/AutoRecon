#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whois查询模块
"""

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import Logger, CommandRunner
from config import CONFIG


class WhoisQuery:
    """Whois查询器"""
    
    def __init__(self, domain):
        self.domain = domain
        self.info = {}
    
    def query_local(self):
        """使用本地whois命令查询"""
        Logger.info(f"正在通过本地whois查询 {self.domain}...")
        
        # 优先使用本地 whois.exe
        local_whois = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'whois.exe')
        
        if os.path.exists(local_whois):
            # Windows: 使用本地 whois.exe，需要 -accepteula
            result = CommandRunner.run([local_whois, '-accepteula', self.domain], timeout=30)
        else:
            # 尝试系统 whois
            result = CommandRunner.run(['whois', self.domain], timeout=30)
        
        if not result['success']:
            Logger.warn("本地whois命令不可用")
            return None
        
        return result['stdout']
    
    def parse_whois(self, raw_data):
        """解析Whois数据"""
        if not raw_data:
            return {}
        
        info = {}
        
        # 注册商
        registrar = re.search(r'Registrar:\s*(.+)', raw_data, re.IGNORECASE)
        if registrar:
            info['registrar'] = registrar.group(1).strip()
        
        # 注册人
        registrant = re.search(r'Registrant(?:\s+Name)?:\s*(.+)', raw_data, re.IGNORECASE)
        if registrant:
            info['registrant'] = registrant.group(1).strip()
        
        # 注册邮箱
        email = re.search(r'Registrant\s+Email:\s*(.+)', raw_data, re.IGNORECASE)
        if not email:
            email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_data)
        if email:
            info['email'] = email.group(1).strip() if hasattr(email, 'group') else email.group(0)
        
        # 创建时间
        created = re.search(r'Creation\s+Date:\s*(.+)', raw_data, re.IGNORECASE)
        if not created:
            created = re.search(r'Registered\s+on:\s*(.+)', raw_data, re.IGNORECASE)
        if created:
            info['created'] = created.group(1).strip()
        
        # 过期时间
        expiry = re.search(r'Registry\s+Expiry\s+Date:\s*(.+)', raw_data, re.IGNORECASE)
        if not expiry:
            expiry = re.search(r'Expiration\s+Date:\s*(.+)', raw_data, re.IGNORECASE)
        if expiry:
            info['expiry'] = expiry.group(1).strip()
        
        # 更新时间
        updated = re.search(r'Updated\s+Date:\s*(.+)', raw_data, re.IGNORECASE)
        if not updated:
            updated = re.search(r'Last\s+Updated:\s*(.+)', raw_data, re.IGNORECASE)
        if updated:
            info['updated'] = updated.group(1).strip()
        
        # DNS服务器
        nameservers = re.findall(r'Name\s*Server:\s*(.+)', raw_data, re.IGNORECASE)
        if nameservers:
            info['nameservers'] = [ns.strip() for ns in nameservers]
        
        # 域名状态
        status = re.findall(r'Domain\s+Status:\s*(.+)', raw_data, re.IGNORECASE)
        if status:
            info['status'] = [s.strip() for s in status]
        
        return info
    
    def query_online(self):
        """使用在线API查询"""
        Logger.info(f"正在通过在线API查询 {self.domain}...")
        
        info = {}
        
        try:
            import urllib.request
            import json
            
            # 使用 whoisapi API
            url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?domainName={self.domain}&outputFormat=JSON"
            req = urllib.request.Request(url, headers={'User-Agent': CONFIG['user_agent']})
            
            response = urllib.request.urlopen(req, timeout=30)
            data = json.loads(response.read().decode('utf-8'))
            
            whois_record = data.get('WhoisRecord', {})
            
            if whois_record:
                info['registrar'] = whois_record.get('registrarName', '')
                info['created'] = whois_record.get('createdDate', '')
                info['expiry'] = whois_record.get('expiresDate', '')
                info['updated'] = whois_record.get('updatedDate', '')
                
                registrant = whois_record.get('registrant', {})
                if registrant:
                    info['registrant'] = registrant.get('organization', registrant.get('name', ''))
                    info['email'] = registrant.get('email', '')
                
                info['nameservers'] = whois_record.get('nameServers', {}).get('hostNames', [])
        
        except Exception as e:
            Logger.warn(f"在线API查询失败: {e}")
        
        return info
    
    def run(self):
        """执行Whois查询"""
        # 尝试本地whois
        raw_data = self.query_local()
        
        if raw_data:
            self.info = self.parse_whois(raw_data)
        
        # 如果本地查询失败或结果不完整，尝试在线API
        if not self.info or len(self.info) < 3:
            online_info = self.query_online()
            if online_info:
                self.info.update(online_info)
        
        if self.info:
            Logger.success(f"Whois查询成功")
            for key, value in self.info.items():
                if isinstance(value, list):
                    print(f"  {key}: {', '.join(value)}")
                else:
                    print(f"  {key}: {value}")
        else:
            Logger.warn("未获取到Whois信息")
        
        return self.info
    
    def is_expired(self):
        """检查域名是否过期"""
        from datetime import datetime
        
        expiry = self.info.get('expiry', '')
        if expiry:
            try:
                # 解析日期
                expiry_date = None
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%d-%b-%Y']:
                    try:
                        expiry_date = datetime.strptime(expiry[:19].replace('T', ' ').split('.')[0].strip(), fmt.replace('T%H:%M:%S', ' %H:%M:%S'))
                        break
                    except:
                        continue
                
                if expiry_date:
                    return datetime.now() > expiry_date
            except:
                pass
        
        return False


class ICPQuery:
    """备案查询器"""
    
    def __init__(self, domain):
        self.domain = domain
        self.info = {}
    
    def query(self):
        """查询备案信息"""
        Logger.info(f"正在查询 {self.domain} 的备案信息...")
        
        # 注意: 实际使用需要备案查询API
        # 这里提供框架，具体API需要用户自己配置
        
        try:
            # 可以使用 icp.chinaz.com 等服务
            import urllib.request
            
            url = f"http://icp.chinaz.com/{self.domain}"
            req = urllib.request.Request(url, headers={'User-Agent': CONFIG['user_agent']})
            
            response = urllib.request.urlopen(req, timeout=30)
            content = response.read().decode('utf-8', errors='ignore')
            
            # 简单解析 (实际需要更复杂的解析)
            if '备案号' in content:
                # 提取备案号
                icp_match = re.search(r'京ICP备\d+号', content)
                if icp_match:
                    self.info['icp_number'] = icp_match.group(0)
                    Logger.success(f"备案号: {self.info['icp_number']}")
            else:
                Logger.info("未查询到备案信息")
        
        except Exception as e:
            Logger.warn(f"备案查询失败: {e}")
        
        return self.info
    
    def run(self):
        return self.query()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        domain = sys.argv[1]
    else:
        domain = 'baidu.com'
    
    whois = WhoisQuery(domain)
    results = whois.run()
    
    print(f"\nWhois信息:")
    for key, value in results.items():
        print(f"  {key}: {value}")
