#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 配置管理 (Pydantic Settings)
支持环境变量、配置文件、多环境配置
"""

from functools import lru_cache
from typing import List, Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class HTTPClientSettings(BaseSettings):
    """HTTP 客户端配置"""
    model_config = SettingsConfigDict(env_prefix="HTTP_")
    
    timeout_total: int = 30
    timeout_connect: int = 5
    timeout_read: int = 10
    verify_ssl: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    max_connections: int = 100
    max_connections_per_host: int = 10


class DNSSettings(BaseSettings):
    """DNS 解析配置"""
    model_config = SettingsConfigDict(env_prefix="DNS_")
    
    servers: List[str] = Field(
        default=["8.8.8.8", "8.8.4.4", "1.1.1.1", "114.114.114.114", "223.5.5.5"]
    )
    cache_ttl: int = 1800  # 30分钟
    resolve_timeout: int = 5
    resolve_lifetime: int = 10


class RateLimitSettings(BaseSettings):
    """速率限制配置"""
    model_config = SettingsConfigDict(env_prefix="RATE_")
    
    max_rate: float = 100.0  # 请求/秒
    max_burst: int = 200
    enabled: bool = True


class ProxySettings(BaseSettings):
    """代理配置"""
    model_config = SettingsConfigDict(env_prefix="PROXY_")
    
    enabled: bool = False
    proxies: List[str] = Field(default=[])
    check_interval: int = 300  # 5分钟
    test_url: str = "http://httpbin.org/ip"
    test_timeout: int = 10


class SecuritySettings(BaseSettings):
    """安全配置"""
    model_config = SettingsConfigDict(env_prefix="SECURITY_")
    
    # SSRF 防护
    ssrf_protection: bool = True
    allow_private_ips: bool = False
    
    # 速率限制
    max_rate: int = 100
    max_burst: int = 200
    
    # API 认证
    auth_enabled: bool = False
    api_keys: List[str] = Field(default=[])
    
    # 命令执行白名单
    allowed_commands: List[str] = Field(
        default=["nmap", "sqlmap", "whois", "dig", "nslookup"]
    )


class ConcurrencySettings(BaseSettings):
    """并发配置"""
    model_config = SettingsConfigDict(env_prefix="CONCURRENCY_")
    
    max_threads: int = 200
    subdomain_threads: int = 50
    port_threads: int = 100
    dir_threads: int = 20
    stress_max_concurrent: int = 10000


class CacheSettings(BaseSettings):
    """缓存配置"""
    model_config = SettingsConfigDict(env_prefix="CACHE_")
    
    enabled: bool = True
    backend: str = "memory"  # memory, sqlite, redis
    memory_max_size: int = 10000
    memory_ttl: int = 3600
    sqlite_path: str = "data/cache.db"
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl: int = 3600


class OutputSettings(BaseSettings):
    """输出配置"""
    model_config = SettingsConfigDict(env_prefix="OUTPUT_")
    
    output_dir: str = "reports"
    log_level: str = "INFO"
    log_file: Optional[str] = None
    json_reports: bool = True
    html_reports: bool = True


class ScannerSettings(BaseSettings):
    """扫描器配置"""
    model_config = SettingsConfigDict(env_prefix="SCANNER_")
    
    default_ports: List[int] = Field(default=[
        21, 22, 23, 25, 53, 80, 81, 88, 110, 135, 139, 143,
        443, 445, 465, 587, 993, 995, 1433, 1521, 3306,
        3389, 5432, 5900, 6379, 7001, 8000, 8080, 8443,
        8888, 9000, 9090, 27017, 9200, 11211
    ])
    
    subdomain_sources: List[str] = Field(
        default=["dns", "certificate", "hackertarget", "rapiddns", "webarchive"]
    )
    
    vulnerability_checks: List[str] = Field(default=[])
    enable_sqli: bool = False
    enable_stress: bool = False


class WebUISettings(BaseSettings):
    """Web UI 配置"""
    model_config = SettingsConfigDict(env_prefix="WEBUI_")
    
    host: str = "0.0.0.0"
    port: int = 5000
    allowed_origins: List[str] = Field(default=["*"])
    session_timeout: int = 3600
    task_expiry: int = 3600
    stress_expiry: int = 1800


class Settings(BaseSettings):
    """主配置类 - 从环境变量和 .env 文件加载"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        nested_model_default_partial_update=True,
    )
    
    # 应用基础
    app_name: str = "AutoRecon"
    version: str = "3.3.1"
    environment: str = "development"  # development, staging, production
    debug: bool = True
    base_dir: str = "."
    
    # 子配置
    http: HTTPClientSettings = Field(default_factory=HTTPClientSettings)
    dns: DNSSettings = Field(default_factory=DNSSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    concurrency: ConcurrencySettings = Field(default_factory=ConcurrencySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    scanner: ScannerSettings = Field(default_factory=ScannerSettings)
    webui: WebUISettings = Field(default_factory=WebUISettings)
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production", "testing"]
        if v not in allowed:
            raise ValueError(f"environment 必须是以下之一: {allowed}")
        return v
    
    @field_validator("base_dir")
    @classmethod
    def validate_base_dir(cls, v: str) -> str:
        import os
        return os.path.abspath(v)
    
    def is_production(self) -> bool:
        return self.environment == "production"
    
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（支持热重载通过清除缓存）"""
    return Settings()


def reload_settings() -> Settings:
    """重新加载配置（清除缓存）"""
    get_settings.cache_clear()
    return get_settings()


# 兼容旧代码的配置访问
class ConfigProxy:
    """向后兼容的配置代理"""
    
    def __getattr__(self, name: str) -> Any:
        settings = get_settings()
        
        # 映射旧配置键
        legacy_map = {
            "timeout": settings.http.timeout_total,
            "connect_timeout": settings.http.timeout_connect,
            "read_timeout": settings.http.timeout_read,
            "max_threads": settings.concurrency.max_threads,
            "subdomain_threads": settings.concurrency.subdomain_threads,
            "port_threads": settings.concurrency.port_threads,
            "dir_threads": settings.concurrency.dir_threads,
            "output_dir": settings.output.output_dir,
            "default_ports": settings.scanner.default_ports,
            "user_agent": settings.http.user_agent,
            "subdomain_prefixes": [],  # 从 data/wordlists 加载
            "dir_wordlist": [],  # 从 data/wordlists 加载
        }
        
        if name in legacy_map:
            return legacy_map[name]
        
        # 尝试从 settings 获取
        if hasattr(settings, name):
            return getattr(settings, name)
        
        # 尝试从子配置获取
        for section in ["http", "dns", "rate_limit", "proxy", "security", 
                       "concurrency", "cache", "output", "scanner", "webui"]:
            section_obj = getattr(settings, section)
            if hasattr(section_obj, name):
                return getattr(section_obj, name)
        
        raise AttributeError(f"配置项不存在: {name}")


# 全局兼容代理
CONFIG = ConfigProxy()


if __name__ == "__main__":
    # 测试配置加载
    settings = get_settings()
    print(f"应用: {settings.app_name} v{settings.version}")
    print(f"环境: {settings.environment}")
    print(f"调试模式: {settings.debug}")
    print(f"HTTP 超时: {settings.http.timeout_total}s")
    print(f"DNS 服务器: {settings.dns.servers}")
    print(f"速率限制: {settings.rate_limit.max_rate} req/s")
    print(f"SSRF 防护: {settings.security.ssrf_protection}")
    print(f"最大线程: {settings.concurrency.max_threads}")
    print(f"输出目录: {settings.output.output_dir}")