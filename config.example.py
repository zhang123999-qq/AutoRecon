# AutoRecon 配置文件示例
# 复制此文件为 config.py 并填写你的配置

# 外部工具路径（可选）
TOOLS = {
    'subfinder': 'subfinder',  # 或完整路径如 'C:\\tools\\subfinder.exe'
    'nmap': 'nmap',            # 或完整路径如 'C:\\Program Files (x86)\\Nmap\\nmap.exe'
    'httpx': 'httpx',          # 或完整路径
}

# 扫描配置
SCAN = {
    'timeout': 10,             # 请求超时（秒）
    'threads': 10,             # 并发线程数
    'retry': 3,                # 重试次数
}

# 输出配置
OUTPUT = {
    'save_report': True,       # 是否保存报告
    'report_dir': 'reports',   # 报告目录
}
