#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信息收集自动化工具 - 配置文件
"""

import os

# 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "reports")

# 扫描配置
CONFIG = {
    # 超时设置
    "timeout": 30,
    "connect_timeout": 5,
    "read_timeout": 10,
    
    # 线程配置
    "max_threads": 20,
    "subdomain_threads": 10,
    "port_threads": 50,
    "dir_threads": 10,
    
    # 输出目录
    "output_dir": OUTPUT_DIR,
    
    # 默认扫描端口
    "default_ports": [
        21, 22, 23, 25, 53, 80, 81, 88, 110, 135, 139, 143, 
        443, 445, 465, 587, 993, 995, 1433, 1521, 3306, 
        3389, 5432, 5900, 6379, 7001, 8000, 8080, 8443, 
        8888, 9000, 9090, 27017, 9200, 11211
    ],
    
    # User-Agent
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    
    # 子域名字典
    "subdomain_prefixes": [
        'www', 'mail', 'ftp', 'admin', 'blog', 'api', 'dev', 'test',
        'staging', 'portal', 'app', 'mobile', 'm', 'bbs', 'forum',
        'cdn', 'static', 'img', 'image', 'images', 'video', 'media',
        'shop', 'store', 'pay', 'payment', 'secure', 'vpn', 'remote',
        'git', 'svn', 'jenkins', 'ci', 'crm', 'erp', 'oa', 'hr',
        'email', 'webmail', 'smtp', 'pop', 'imap', 'ns1', 'ns2',
        'proxy', 'cache', 'file', 'download', 'upload', 'assets',
        'css', 'js', 'fonts', 'lib', 'docs', 'help', 'support'
    ],
    
    # 目录字典
    "dir_wordlist": [
        '/', '/admin', '/login', '/api', '/backup', '/config',
        '/data', '/db', '/files', '/images', '/js', '/css',
        '/uploads', '/tmp', '/test', '/debug', '.git', '.svn',
        '.env', 'robots.txt', 'sitemap.xml', 'phpinfo.php',
        '/wp-admin', '/wp-login.php', '/administrator',
        '/manager', '/console', '/druid', '/actuator',
        '/swagger-ui.html', '/api-docs', '/graphql',
        '/.git/config', '/.svn/entries', '/WEB-INF/web.xml',
        '/admin.php', '/install.php', '/config.php.bak',
        '/backup.zip', '/db.sql', '/database.sql'
    ]
}

# Web指纹库
FINGERPRINTS = {
    # CMS
    'WordPress': ['wp-content', 'wp-includes', 'wp-login.php'],
    'Drupal': ['Drupal.settings', 'misc/drupal.js', '/misc/drupal.js'],
    'Joomla': ['Joomla', '/administrator/', 'option=com_'],
    'Discuz!': ['Discuz', 'discuz_uid'],
    'PhpWind': ['phpwind', 'windid'],
    'DedeCMS': ['dedecms', 'dedeajax'],
    'ThinkPHP': ['ThinkPHP', 'think_var'],
    
    # 框架
    'Spring': ['Whitelabel Error Page', 'springframework'],
    'Django': ['csrfmiddlewaretoken', 'django', 'DJANGO'],
    'Flask': ['Werkzeug', 'flask'],
    'Laravel': ['laravel', 'Laravel'],
    'Express': ['Express', 'express'],
    'Rails': ['Ruby on Rails', 'rails'],
    
    # 服务器
    'Tomcat': ['Apache Tomcat', 'manager/html'],
    'Nginx': ['nginx', 'Nginx'],
    'Apache': ['Apache', 'apache'],
    'IIS': ['IIS', 'Microsoft-IIS'],
    'Jetty': ['Jetty', 'jetty'],
    
    # 语言
    'PHP': ['PHP/', '.php', 'X-Powered-By: PHP'],
    'ASP.NET': ['ASP.NET', '__VIEWSTATE', 'ASP.NET_SessionId'],
    'JSP': ['.jsp', 'JSESSIONID'],
    
    # 前端框架
    'Vue.js': ['vue', 'Vue', '__vue__'],
    'React': ['react', 'React', '_reactRootContainer'],
    'Angular': ['angular', 'ng-version', 'ng-app'],
    'jQuery': ['jquery', 'jQuery'],
    'Bootstrap': ['bootstrap', 'Bootstrap'],
    
    # 数据库管理
    'phpMyAdmin': ['phpMyAdmin', 'pma_username'],
    'Adminer': ['Adminer', 'adminer'],
    
    # 其他
    'Shiro': ['rememberMe', 'JSESSIONID'],
    'FastJSON': ['fastjson', 'com.alibaba.fastjson']
}

# 端口服务识别
SERVICE_SIGNATURES = {
    21: 'FTP',
    22: 'SSH',
    23: 'Telnet',
    25: 'SMTP',
    53: 'DNS',
    80: 'HTTP',
    110: 'POP3',
    143: 'IMAP',
    443: 'HTTPS',
    445: 'SMB',
    1433: 'MSSQL',
    1521: 'Oracle',
    3306: 'MySQL',
    3389: 'RDP',
    5432: 'PostgreSQL',
    5900: 'VNC',
    6379: 'Redis',
    7001: 'WebLogic',
    8080: 'HTTP-Proxy',
    8443: 'HTTPS-Alt',
    27017: 'MongoDB',
    9200: 'Elasticsearch',
    11211: 'Memcached'
}

# 敏感文件/目录
SENSITIVE_PATHS = [
    # 版本控制
    '/.git/config', '/.git/HEAD', '/.svn/entries', '/.hg/',
    
    # 配置文件
    '/.env', '/config.php', '/database.yml', '/settings.py',
    '/web.config', '/app.config', '/.htaccess',
    
    # 备份文件
    '/backup.sql', '/backup.zip', '/db.sql', '/dump.sql',
    '/backup.tar.gz', '/www.zip', '/web.zip',
    
    # 敏感信息
    '/phpinfo.php', '/info.php', '/test.php',
    '/README.md', '/CHANGELOG.md', '/LICENSE',
    
    # 后台
    '/admin', '/admin/', '/administrator', '/manager',
    '/console', '/login', '/wp-admin', '/wp-login.php',
    
    # API文档
    '/swagger-ui.html', '/swagger-ui/', '/api-docs',
    '/graphql', '/graphiql',
    
    # 监控
    '/actuator', '/druid', '/solr', '/jenkins'
]
