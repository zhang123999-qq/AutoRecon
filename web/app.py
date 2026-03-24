#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon Web UI - FastAPI 后端
"""

import sys
import os
import asyncio
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入核心组件
from core.async_engine import AsyncDNSResolver, AsyncCache, ResultStore


# ============ 数据模型 ============

class ScanRequest(BaseModel):
    target: str
    modules: List[str] = ["subdomain", "cdn", "sensitive"]
    threads: int = 50


class ScanStatus(BaseModel):
    scan_id: str
    target: str
    status: str  # pending, running, completed, failed
    progress: int
    current_module: str
    results: Dict
    error: Optional[str] = None
    created_at: str
    elapsed: float = 0


# ============ 全局状态 ============

app = FastAPI(
    title="AutoRecon Web UI",
    description="自动化信息收集工具 - Web界面",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 扫描任务存储
scan_tasks: Dict[str, ScanStatus] = {}

# 任务过期时间（秒）
TASK_EXPIRY_SECONDS = 3600  # 1小时后自动清理


def cleanup_expired_tasks():
    """清理过期的扫描任务"""
    now = datetime.now()
    expired = []
    
    for scan_id, task in scan_tasks.items():
        if task.status in ['completed', 'failed']:
            try:
                created = datetime.strptime(task.created_at, "%Y-%m-%d %H:%M:%S")
                if (now - created).total_seconds() > TASK_EXPIRY_SECONDS:
                    expired.append(scan_id)
            except:
                pass
    
    for scan_id in expired:
        del scan_tasks[scan_id]
    
    return len(expired)

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, scan_id: str):
        await websocket.accept()
        if scan_id not in self.active_connections:
            self.active_connections[scan_id] = []
        self.active_connections[scan_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, scan_id: str):
        if scan_id in self.active_connections:
            if websocket in self.active_connections[scan_id]:
                self.active_connections[scan_id].remove(websocket)
            if not self.active_connections[scan_id]:
                del self.active_connections[scan_id]
    
    async def broadcast(self, scan_id: str, message: dict):
        if scan_id in self.active_connections:
            for connection in self.active_connections[scan_id][:]:
                try:
                    await connection.send_json(message)
                except:
                    self.disconnect(connection, scan_id)

manager = ConnectionManager()


# ============ 扫描任务执行 ============

class WebScanRunner:
    """独立的 Web 扫描运行器，不依赖 CLI 版本"""
    
    # 模块配置
    MODULE_CONFIG = {
        'subdomain': {'name': '子域名收集', 'icon': 'globe'},
        'port': {'name': '端口扫描', 'icon': 'plug'},
        'cdn': {'name': 'CDN检测', 'icon': 'cloud'},
        'fingerprint': {'name': '指纹识别', 'icon': 'fingerprint'},
        'sensitive': {'name': '敏感信息检测', 'icon': 'exclamation-triangle'},
        'vuln': {'name': '漏洞扫描', 'icon': 'bug'},
        'sqli': {'name': 'SQL注入扫描', 'icon': 'database'},
    }
    
    def __init__(self, scan_id: str, target: str, modules: List[str], threads: int = 50):
        self.scan_id = scan_id
        self.target = target
        self.modules = modules
        self.threads = threads
        
        self.results = {}
        self.cache = AsyncCache()
        self.dns = AsyncDNSResolver(cache=self.cache)
        self.store = ResultStore("reports")
        
        self.start_time = None
        self.end_time = None
        self.progress = 0
        self.current_module = ""
    
    async def broadcast_progress(self, module_name: str, progress: int):
        """广播进度更新"""
        self.progress = progress
        self.current_module = module_name
        
        if self.scan_id in scan_tasks:
            scan_tasks[self.scan_id].progress = progress
            scan_tasks[self.scan_id].current_module = module_name
        
        await manager.broadcast(self.scan_id, {
            'type': 'progress',
            'module': module_name,
            'progress': progress
        })
    
    async def run_subdomain(self) -> Dict:
        """子域名收集"""
        from modules.async_subdomain import AsyncSubdomainCollector
        
        collector = AsyncSubdomainCollector(
            self.target,
            threads=self.threads,
            use_cache=True
        )
        
        results = await collector.run_full()
        
        self.results['subdomain'] = {
            'count': len(results),
            'domains': [r.subdomain for r in results],
            'details': [
                {'subdomain': r.subdomain, 'ip': r.ip, 'source': r.source}
                for r in results
            ]
        }
        
        return self.results['subdomain']
    
    async def run_port_scan(self) -> Dict:
        """端口扫描"""
        # 获取要扫描的主机
        hosts = [self.target]
        if 'subdomain' in self.results:
            ips = set()
            for detail in self.results['subdomain'].get('details', []):
                if detail.get('ip'):
                    ips.add(detail['ip'])
            hosts.extend(list(ips))
        
        # 常用端口
        common_ports = [
            21, 22, 23, 25, 53, 80, 81, 88, 110, 135, 139, 143,
            443, 445, 465, 587, 993, 995, 1433, 1521, 3306,
            3389, 5432, 5900, 6379, 7001, 8000, 8080, 8443,
            8888, 9000, 9090, 27017, 9200, 11211
        ]
        
        results = {'hosts': {}}
        
        async def scan_port(host: str, port: int) -> tuple:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=3
                )
                writer.close()
                await writer.wait_closed()
                return (port, True)
            except:
                return (port, False)
        
        for host in hosts[:10]:
            tasks = [scan_port(host, port) for port in common_ports]
            done = await asyncio.gather(*tasks)
            
            open_ports = [port for port, is_open in done if is_open]
            results['hosts'][host] = {'open_ports': open_ports}
        
        self.results['port'] = results
        return results
    
    async def run_cdn_detect(self) -> Dict:
        """CDN检测"""
        from core.async_engine import AsyncHTTPClient
        
        results = {'domain': self.target, 'cdn': None, 'ips': []}
        
        # 解析IP
        ips = await self.dns.resolve_all(self.target)
        results['ips'] = ips
        
        # CDN IP特征检测
        cdn_ranges = {
            'CloudFlare': ['103.21.', '103.22.', '104.16.', '172.64.', '188.114.'],
            'Akamai': ['23.', '104.', '184.', '2.16.', '88.'],
            '阿里云CDN': ['47.', '59.', '110.', '120.'],
            '腾讯云CDN': ['14.', '42.', '49.', '101.', '119.'],
        }
        
        for ip in ips:
            for cdn, ranges in cdn_ranges.items():
                for r in ranges:
                    if ip.startswith(r):
                        results['cdn'] = cdn
                        break
        
        # HTTP头检测
        if not results['cdn']:
            async with AsyncHTTPClient() as client:
                resp = await client.get(f"http://{self.target}")
                headers = {k.lower(): v.lower() for k, v in resp.get('headers', {}).items()}
                
                cdn_headers = {
                    'CloudFlare': ['cf-ray', 'cloudflare'],
                    'Akamai': ['akamai'],
                    '阿里云CDN': ['ali-swift'],
                    '腾讯云CDN': ['x-cdn'],
                }
                
                for cdn, indicators in cdn_headers.items():
                    for ind in indicators:
                        for h, v in headers.items():
                            if ind in h or ind in v:
                                results['cdn'] = cdn
                                break
        
        self.results['cdn'] = results
        return results
    
    async def run_sensitive(self) -> Dict:
        """敏感信息检测"""
        import re
        from core.async_engine import AsyncHTTPClient
        
        patterns = {
            'AWS Key': r'AKIA[0-9A-Z]{16}',
            'GitHub Token': r'ghp_[A-Za-z0-9]{36}',
            'Private Key': r'-----BEGIN.*PRIVATE KEY-----',
            'API Key': r'[aA][pP][iI][_\-]?[kK][eE][yY].{16,}',
            'Password': r'[pP][aA][sS][sS][wW][oO][rR][dD].{6,}',
            'JWT': r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*',
        }
        
        results = {'url': f"http://{self.target}", 'findings': []}
        
        async with AsyncHTTPClient() as client:
            resp = await client.get(f"http://{self.target}")
            body = resp.get('body', '')
            
            for name, pattern in patterns.items():
                matches = re.findall(pattern, body)
                if matches:
                    results['findings'].append({
                        'type': name,
                        'count': len(matches),
                        'sample': matches[0][:50] if matches else None
                    })
        
        self.results['sensitive'] = results
        return results
    
    async def run_fingerprint(self) -> Dict:
        """指纹识别"""
        from core.async_engine import AsyncHTTPClient
        from data.fingerprints import ALL_FINGERPRINTS
        
        results = {'fingerprints': []}
        
        async with AsyncHTTPClient() as client:
            resp = await client.get(f"http://{self.target}")
            body = resp.get('body', '')
            headers = resp.get('headers', {})
            
            for name, fingerprints in ALL_FINGERPRINTS.items():
                matched = False
                
                # HTML特征
                for pattern in fingerprints.get('html', []):
                    if pattern.lower() in body.lower():
                        matched = True
                        break
                
                # Header特征
                if not matched:
                    for pattern in fingerprints.get('headers', []):
                        for h, v in headers.items():
                            if pattern.lower() in f"{h}: {v}".lower():
                                matched = True
                                break
                
                if matched:
                    results['fingerprints'].append(name)
        
        self.results['fingerprint'] = results
        return results
    
    async def run_vuln(self) -> Dict:
        """漏洞扫描"""
        from modules.vuln_scanner import VulnerabilityScanner
        
        scanner = VulnerabilityScanner(self.target, threads=self.threads)
        await scanner.run_all()
        
        self.results['vulnerabilities'] = scanner.get_results()
        return self.results['vulnerabilities']
    
    async def run_sqli(self) -> Dict:
        """SQL注入扫描 - 使用 sqlmap 集成模块"""
        from modules.sqlmap_integration import SQLMapAutoScanner
        
        scanner = SQLMapAutoScanner(
            self.target,
            threads=min(self.threads, 5),  # sqlmap 不需要太多线程
            use_api=False,  # 使用命令行方式
            timeout=180
        )
        
        await scanner.run_full_scan()
        
        results = scanner.get_results()
        self.results['sqli'] = results
        return self.results['sqli']
    
    async def run_all(self) -> Dict:
        """执行所有选中的模块"""
        self.start_time = time.time()
        
        # 模块映射
        module_funcs = {
            'subdomain': self.run_subdomain,
            'port': self.run_port_scan,
            'cdn': self.run_cdn_detect,
            'sensitive': self.run_sensitive,
            'fingerprint': self.run_fingerprint,
            'vuln': self.run_vuln,
            'sqli': self.run_sqli,
        }
        
        total = len(self.modules)
        
        for i, module in enumerate(self.modules):
            if module not in module_funcs:
                continue
            
            module_name = self.MODULE_CONFIG.get(module, {}).get('name', module)
            
            # 计算进度 (执行前)
            progress = int((i / total) * 100)
            await self.broadcast_progress(module_name, progress)
            
            try:
                await module_funcs[module]()
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.results[module] = {'error': str(e)}
        
        # 完成
        self.end_time = time.time()
        await self.broadcast_progress('完成', 100)
        
        # 保存报告
        self._save_report()
        
        return self.results
    
    def _save_report(self):
        """保存扫描报告"""
        try:
            report_data = {
                'target': self.target,
                'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'elapsed': self.end_time - self.start_time,
                **self.results
            }
            
            self.store.save_json(self.target, report_data)
        except Exception as e:
            print(f"保存报告失败: {e}")


async def run_scan_task(scan_id: str, request: ScanRequest):
    """后台扫描任务"""
    try:
        scan_tasks[scan_id].status = "running"
        
        # 广播开始
        await manager.broadcast(scan_id, {
            'type': 'status',
            'status': 'running',
            'message': '扫描开始'
        })
        
        # 创建扫描器
        runner = WebScanRunner(
            scan_id=scan_id,
            target=request.target,
            modules=request.modules,
            threads=request.threads
        )
        
        # 执行扫描
        results = await runner.run_all()
        
        # 更新状态
        elapsed = runner.end_time - runner.start_time
        scan_tasks[scan_id].status = "completed"
        scan_tasks[scan_id].results = results
        scan_tasks[scan_id].progress = 100
        scan_tasks[scan_id].elapsed = elapsed
        
        # 广播完成
        await manager.broadcast(scan_id, {
            'type': 'status',
            'status': 'completed',
            'results': results,
            'elapsed': elapsed
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        if scan_id in scan_tasks:
            scan_tasks[scan_id].status = "failed"
            scan_tasks[scan_id].error = str(e)
        
        await manager.broadcast(scan_id, {
            'type': 'status',
            'status': 'failed',
            'error': str(e)
        })


# ============ API 路由 ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    html_file = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding='utf-8'))


@app.get("/favicon.ico")
async def favicon():
    """返回空 favicon 避免控制台报错"""
    return JSONResponse(content={}, status_code=204)


@app.post("/api/scan")
async def create_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """创建扫描任务"""
    # 清理过期任务
    cleanup_expired_tasks()
    
    scan_id = str(uuid.uuid4())[:8]
    
    # 初始化状态
    scan_tasks[scan_id] = ScanStatus(
        scan_id=scan_id,
        target=request.target,
        status="pending",
        progress=0,
        current_module="初始化",
        results={},
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # 启动后台任务
    background_tasks.add_task(run_scan_task, scan_id, request)
    
    return {"scan_id": scan_id, "status": "created"}


@app.delete("/api/scan/{scan_id}")
async def cancel_scan(scan_id: str):
    """取消扫描任务"""
    if scan_id not in scan_tasks:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    task = scan_tasks[scan_id]
    
    if task.status == "completed":
        raise HTTPException(status_code=400, detail="Scan already completed")
    
    if task.status == "failed":
        raise HTTPException(status_code=400, detail="Scan already failed")
    
    # 标记为已取消
    task.status = "cancelled"
    task.error = "用户取消"
    
    # 广播取消消息
    await manager.broadcast(scan_id, {
        'type': 'status',
        'status': 'cancelled',
        'error': '用户取消'
    })
    
    return {"scan_id": scan_id, "status": "cancelled"}


@app.get("/api/scan/{scan_id}")
async def get_scan_status(scan_id: str):
    """获取扫描状态"""
    if scan_id not in scan_tasks:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return scan_tasks[scan_id]


@app.get("/api/scans")
async def list_scans():
    """列出所有扫描任务"""
    return list(scan_tasks.values())


@app.get("/api/reports")
async def list_reports():
    """列出所有报告"""
    reports_dir = ROOT_DIR / "reports"
    if not reports_dir.exists():
        return []
    
    reports = []
    for f in reports_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            reports.append({
                "file": f.name,
                "target": data.get("target", "unknown"),
                "scan_time": data.get("scan_time", ""),
                "size": f.stat().st_size
            })
        except:
            pass
    
    return sorted(reports, key=lambda x: x["scan_time"], reverse=True)


@app.get("/api/reports/{filename}")
async def get_report(filename: str):
    """获取报告详情"""
    report_file = ROOT_DIR / "reports" / filename
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    return JSONResponse(content=json.loads(report_file.read_text(encoding='utf-8')))


@app.get("/api/download/{filename}")
async def download_report(filename: str):
    """下载报告"""
    report_file = ROOT_DIR / "reports" / filename
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    return FileResponse(
        path=report_file,
        filename=filename,
        media_type='application/octet-stream'
    )


@app.websocket("/ws/{scan_id}")
async def websocket_endpoint(websocket: WebSocket, scan_id: str):
    """WebSocket 实时进度"""
    await manager.connect(websocket, scan_id)
    
    try:
        while True:
            # 等待客户端消息（主要用于保持连接）
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, scan_id)


@app.post("/api/sqlmap")
async def sqlmap_scan(request: dict):
    """
    单独的 sqlmap 扫描接口
    
    请求体:
    - url: 目标 URL
    - options: sqlmap 选项 (可选)
    - timeout: 超时时间，默认 180 秒
    """
    from modules.sqlmap_integration import SQLMapCommandLine
    
    url = request.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    options = request.get("options", {})
    timeout = request.get("timeout", 180)
    
    client = SQLMapCommandLine()
    result = await client.scan_url(url, options=options, timeout=timeout)
    
    return {
        "url": result.url,
        "vulnerable": result.vulnerable,
        "parameter": result.parameter,
        "injection_type": result.injection_type,
        "dbms": result.dbms,
        "database": result.database,
        "user": result.user,
        "payload": result.payload,
        "log": result.log[-20:] if result.log else []  # 只返回最后 20 条日志
    }


@app.get("/api/sqlmap/status")
async def sqlmap_status():
    """检查 sqlmap 是否可用"""
    import shutil
    
    sqlmap_path = shutil.which("sqlmap")
    
    return {
        "available": sqlmap_path is not None,
        "path": sqlmap_path or ""
    }


# ============ 压力测试 API ============

from modules.stress_test import StressTestConfig, StressTester
from modules.stress_advanced import run_stress_test, IntelligentStressTest


class StressTestRequest(BaseModel):
    url: str
    mode: str = "quick"  # quick, intelligent, capacity
    concurrent: int = 10
    duration: int = 10
    timeout: int = 30


class StressTestStatus(BaseModel):
    test_id: str
    url: str
    mode: str
    status: str  # pending, running, completed, failed
    progress: int
    current_phase: str
    results: Dict
    error: Optional[str] = None


# 压力测试任务存储
stress_tasks: Dict[str, StressTestStatus] = {}

# 压力测试过期时间（秒）
STRESS_EXPIRY_SECONDS = 1800  # 30分钟后清理


def cleanup_expired_stress_tasks():
    """清理过期的压力测试任务"""
    now = datetime.now()
    expired = []
    
    for test_id, task in stress_tasks.items():
        if task.status in ['completed', 'failed']:
            expired.append(test_id)
    
    for test_id in expired[:10]:  # 每次最多清理10个
        del stress_tasks[test_id]
    
    return len(expired[:10])


@app.post("/api/stress")
async def create_stress_test(request: StressTestRequest, background_tasks: BackgroundTasks):
    """创建压力测试任务"""
    # 清理过期任务
    cleanup_expired_stress_tasks()
    
    test_id = str(uuid.uuid4())[:8]
    
    # 初始化状态
    stress_tasks[test_id] = StressTestStatus(
        test_id=test_id,
        url=request.url,
        mode=request.mode,
        status="pending",
        progress=0,
        current_phase="初始化",
        results={}
    )
    
    # 启动后台任务
    background_tasks.add_task(run_stress_test_task, test_id, request)
    
    return {"test_id": test_id, "status": "created"}


async def run_stress_test_task(test_id: str, request: StressTestRequest):
    """后台压力测试任务（带实时更新，无上限支持）"""
    from modules.stress_test import StressTester, StressTestConfig
    
    try:
        stress_tasks[test_id].status = "running"
        stress_tasks[test_id].current_phase = "测试中"
        
        # 创建配置（无上限）
        config = StressTestConfig(
            target_url=request.url,
            concurrent_users=request.concurrent,
            duration=request.duration,
            timeout=request.timeout if hasattr(request, 'timeout') else 30,
            max_concurrent=request.max_concurrent if hasattr(request, 'max_concurrent') else 10000
        )
        
        tester = StressTester(config)
        
        # 设置进度回调
        async def on_progress(phase, current, total):
            if test_id in stress_tasks:
                metrics = tester.get_current_metrics()
                stress_tasks[test_id].progress = int((current / total) * 100) if total > 0 else 0
                stress_tasks[test_id].current_phase = f"{phase}: {metrics['total_requests']} 请求"
                stress_tasks[test_id].results = {
                    "metrics": {
                        "throughput": {"qps": metrics['qps']},
                        "response_time": {"avg": metrics['avg_response_time']},
                        "errors": {"error_rate": metrics['error_rate']},
                        "total_requests": metrics['total_requests'],
                        "successful_requests": metrics['successful_requests'],
                        "failed_requests": metrics['failed_requests']
                    }
                }
        
        tester.on_progress = on_progress
        
        # 运行测试
        await tester.run()
        
        # 获取最终结果
        result = tester.get_results()
        
        # 更新状态
        stress_tasks[test_id].status = "completed"
        stress_tasks[test_id].progress = 100
        stress_tasks[test_id].current_phase = "完成"
        stress_tasks[test_id].results = result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        if test_id in stress_tasks:
            stress_tasks[test_id].status = "failed"
            stress_tasks[test_id].error = str(e)


@app.get("/api/stress/{test_id}")
async def get_stress_test_status(test_id: str):
    """获取压力测试状态"""
    if test_id not in stress_tasks:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return stress_tasks[test_id]


@app.get("/api/stress")
async def list_stress_tests():
    """列出所有压力测试任务"""
    return list(stress_tasks.values())


@app.post("/api/stress/quick")
async def quick_stress_test(request: StressTestRequest):
    """快速压力测试 (同步，直接返回结果，无上限支持)"""
    try:
        result = await run_stress_test(
            url=request.url,
            mode="quick",
            concurrent=request.concurrent,
            duration=request.duration,
            max_concurrent=request.max_concurrent if hasattr(request, 'max_concurrent') else 10000
        )
        # 使用 JSONResponse 确保正确计算 Content-Length
        return JSONResponse(content=result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 静态文件 ============

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
