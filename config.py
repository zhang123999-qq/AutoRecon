#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.0 - 配置管理

支持环境变量覆盖，便于容器化和生产环境部署
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional


def _get_env_list(key: str, default: str = "") -> List[str]:
    """从环境变量读取列表（逗号分隔）"""
    value = os.environ.get(key, default)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_env_int(key: str, default: int) -> int:
    """从环境变量读取整数"""
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _get_env_float(key: str, default: float) -> float:
    """从环境变量读取浮点数"""
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """从环境变量读取布尔值"""
    value = os.environ.get(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


@dataclass
class TimeoutConfig:
    """超时配置"""
    total: int = field(default_factory=lambda: _get_env_int("TIMEOUT_TOTAL", 30))
    connect: int = field(default_factory=lambda: _get_env_int("TIMEOUT_CONNECT", 5))
    read: int = field(default_factory=lambda: _get_env_int("TIMEOUT_READ", 10))
    dns: int = field(default_factory=lambda: _get_env_int("TIMEOUT_DNS", 3))


@dataclass
class ThreadingConfig:
    """并发配置"""
    max_threads: int = field(default_factory=lambda: min(_get_env_int("MAX_THREADS", 200), 200))
    subdomain_threads: int = field(default_factory=lambda: _get_env_int("SUBDOMAIN_THREADS", 50))
    port_threads: int = field(default_factory=lambda: _get_env_int("PORT_THREADS", 100))
    dir_threads: int = field(default_factory=lambda: _get_env_int("DIR_THREADS", 20))


@dataclass
class NetworkConfig:
    """网络配置"""
    dns_servers: List[str] = field(default_factory=lambda: _get_env_list(
        "DNS_SERVERS", "8.8.8.8,8.8.4.4,1.1.1.1"
    ))
    user_agent: str = field(default_factory=lambda: os.environ.get(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ))
    verify_ssl: bool = field(default_factory=lambda: _get_env_bool("VERIFY_SSL", True))


@dataclass
class SecurityConfig:
    """安全配置"""
    # SSRF 防护
    ssrf_protection_enabled: bool = field(default_factory=lambda: _get_env_bool("SSRF_PROTECTION", True))
    allow_private_ips: bool = field(default_factory=lambda: _get_env_bool("ALLOW_PRIVATE_IPS", False))
    
    # 速率限制
    max_rate: int = field(default_factory=lambda: _get_env_int("MAX_RATE", 100))
    max_burst: int = field(default_factory=lambda: _get_env_int("MAX_BURST", 200))
    
    # API 认证
    api_keys: List[str] = field(default_factory=lambda: _get_env_list("API_KEYS", ""))
    auth_enabled: bool = field(default_factory=lambda: _get_env_bool("AUTH_ENABLED", False))


@dataclass
class OutputConfig:
    """输出配置"""
    output_dir: str = field(default_factory=lambda: os.environ.get(
        "OUTPUT_DIR", 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    ))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    log_file: Optional[str] = field(default_factory=lambda: os.environ.get("LOG_FILE", None))


@dataclass
class AppConfig:
    """应用总配置"""
    base_dir: str = field(default_factory=lambda: os.path.dirname(os.path.abspath(__file__)))
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    threading: ThreadingConfig = field(default_factory=ThreadingConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # 默认扫描端口
    default_ports: List[int] = field(default_factory=lambda: [
        21, 22, 23, 25, 53, 80, 81, 88, 110, 135, 139, 143, 
        443, 445, 465, 587, 993, 995, 1433, 1521, 3306, 
        3389, 5432, 5900, 6379, 7001, 8000, 8080, 8443, 
        8888, 9000, 9090, 27017, 9200, 11211
    ])
    
    def __post_init__(self):
        """确保输出目录存在"""
        os.makedirs(self.output.output_dir, exist_ok=True)


# 全局配置实例
config = AppConfig()


# ============== 以下为静态配置（指纹库等） ==============

# Web指纹库
FINGERPRINTS: Dict[str, List[str]] = {
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
SERVICE_SIGNATURES: Dict[int, str] = {
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
SENSITIVE_PATHS: List[str] = [
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

# 子域名前缀（常用）
SUBDOMAIN_PREFIXES: List[str] = [
    'www', 'mail', 'ftp', 'admin', 'blog', 'api', 'dev', 'test',
    'staging', 'portal', 'app', 'mobile', 'm', 'bbs', 'forum',
    'cdn', 'static', 'img', 'image', 'images', 'video', 'media',
    'shop', 'store', 'pay', 'payment', 'secure', 'vpn', 'remote',
    'git', 'svn', 'jenkins', 'ci', 'crm', 'erp', 'oa', 'hr',
    'email', 'webmail', 'smtp', 'pop', 'imap', 'ns1', 'ns2',
    'proxy', 'cache', 'file', 'download', 'upload', 'assets',
    'css', 'js', 'fonts', 'lib', 'docs', 'help', 'support'
]

# 目录字典
DIR_WORDLIST: List[str] = [
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


# ============== 兼容旧代码 ==============

# 基础配置
BASE_DIR = config.base_dir
OUTPUT_DIR = config.output.output_dir

# 向后兼容的 CONFIG 字典
CONFIG = {
    "timeout": config.timeout.total,
    "connect_timeout": config.timeout.connect,
    "read_timeout": config.timeout.read,
    "max_threads": config.threading.max_threads,
    "subdomain_threads": config.threading.subdomain_threads,
    "port_threads": config.threading.port_threads,
    "dir_threads": config.threading.dir_threads,
    "output_dir": config.output.output_dir,
    "default_ports": config.default_ports,
    "user_agent": config.network.user_agent,
    "subdomain_prefixes": SUBDOMAIN_PREFIXES,
    "dir_wordlist": DIR_WORDLIST,
}
