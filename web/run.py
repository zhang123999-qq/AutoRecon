#!/usr/bin/env python3
"""
AutoRecon Web UI 启动脚本
"""

import sys
import os
from pathlib import Path

# 添加项目路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

if __name__ == "__main__":
    import uvicorn
    from web.app import app
    
    print("""
╔═══════════════════════════════════════════════════════╗
║         AutoRecon Web UI v3.0 - 服务启动              ║
╠═══════════════════════════════════════════════════════╣
║  访问地址: http://127.0.0.1:5000                      ║
║  API文档:  http://127.0.0.1:5000/docs                 ║
╚═══════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=5000)
