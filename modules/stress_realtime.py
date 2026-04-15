#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.2 - 压力测试实时广播模块
WebSocket 实时进度推送，替代轮询机制
"""

import asyncio
import json
import time
import logging
from typing import Set, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from weakref import WeakSet

logger = logging.getLogger(__name__)


@dataclass
class BroadcastMessage:
    """广播消息"""
    type: str  # progress, complete, error, metrics
    test_id: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "test_id": self.test_id,
            "data": self.data,
            "timestamp": self.timestamp
        })


class StressTestBroadcaster:
    """
    压力测试实时广播器
    
    功能:
    - WebSocket 连接管理
    - 实时进度推送
    - 多客户端广播
    - 自动断线清理
    """
    
    def __init__(self, max_connections: int = 100):
        self._connections: Set = WeakSet()
        self._connection_data: Dict = {}  # 存储连接元数据
        self._max_connections = max_connections
        self._lock = asyncio.Lock()
        
        # 统计
        self._total_messages = 0
        self._total_broadcasts = 0
    
    @property
    def connection_count(self) -> int:
        """当前连接数"""
        return len(self._connection_data)
    
    async def connect(self, websocket, test_id: str = None) -> bool:
        """
        添加 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接对象
            test_id: 可选，订阅特定测试
        
        Returns:
            是否成功添加
        """
        async with self._lock:
            if len(self._connection_data) >= self._max_connections:
                logger.warning(f"连接数达到上限: {self._max_connections}")
                return False
            
            self._connections.add(websocket)
            self._connection_data[id(websocket)] = {
                "test_id": test_id,
                "connected_at": time.time(),
                "messages_sent": 0
            }
            
            logger.info(f"WebSocket 连接建立, 当前连接数: {len(self._connection_data)}")
            return True
    
    async def disconnect(self, websocket):
        """移除 WebSocket 连接"""
        async with self._lock:
            self._connection_data.pop(id(websocket), None)
            logger.info(f"WebSocket 连接断开, 当前连接数: {len(self._connection_data)}")
    
    async def broadcast(self, message: BroadcastMessage):
        """
        广播消息到所有连接
        
        Args:
            message: 广播消息对象
        """
        if not self._connections:
            return
        
        json_msg = message.to_json()
        self._total_broadcasts += 1
        
        # 获取所有连接
        connections = list(self._connections)
        
        for ws in connections:
            try:
                await ws.send_text(json_msg)
                self._total_messages += 1
                
                # 更新统计
                conn_id = id(ws)
                if conn_id in self._connection_data:
                    self._connection_data[conn_id]["messages_sent"] += 1
                    
            except Exception as e:
                logger.debug(f"发送消息失败: {e}")
                # 连接已断开，清理
                self._connection_data.pop(id(ws), None)
    
    async def broadcast_to_test(self, test_id: str, message: BroadcastMessage):
        """
        广播消息到订阅特定测试的连接
        
        Args:
            test_id: 测试 ID
            message: 广播消息对象
        """
        if not self._connections:
            return
        
        json_msg = message.to_json()
        
        for ws in list(self._connections):
            conn_id = id(ws)
            conn_data = self._connection_data.get(conn_id)
            
            # 只发送给订阅该测试的连接，或订阅所有测试的连接
            if conn_data and (conn_data["test_id"] == test_id or conn_data["test_id"] is None):
                try:
                    await ws.send_text(json_msg)
                    conn_data["messages_sent"] += 1
                    self._total_messages += 1
                except Exception:
                    self._connection_data.pop(conn_id, None)
    
    async def send_progress(self, test_id: str, phase: str, progress: int, 
                            metrics: Dict[str, Any]):
        """
        发送进度更新
        
        Args:
            test_id: 测试 ID
            phase: 当前阶段
            progress: 进度百分比 (0-100)
            metrics: 实时指标
        """
        message = BroadcastMessage(
            type="progress",
            test_id=test_id,
            data={
                "phase": phase,
                "progress": progress,
                "metrics": {
                    "total_requests": metrics.get("total_requests", 0),
                    "successful_requests": metrics.get("successful_requests", 0),
                    "failed_requests": metrics.get("failed_requests", 0),
                    "qps": round(metrics.get("qps", 0), 2),
                    "avg_response_time": round(metrics.get("avg_response_time", 0), 2),
                    "error_rate": round(metrics.get("error_rate", 0), 2),
                }
            }
        )
        
        await self.broadcast_to_test(test_id, message)
    
    async def send_complete(self, test_id: str, results: Dict[str, Any]):
        """
        发送测试完成消息
        
        Args:
            test_id: 测试 ID
            results: 完整测试结果
        """
        message = BroadcastMessage(
            type="complete",
            test_id=test_id,
            data={
                "status": "completed",
                "results": results
            }
        )
        
        await self.broadcast_to_test(test_id, message)
    
    async def send_error(self, test_id: str, error: str):
        """
        发送错误消息
        
        Args:
            test_id: 测试 ID
            error: 错误信息
        """
        message = BroadcastMessage(
            type="error",
            test_id=test_id,
            data={
                "status": "failed",
                "error": error
            }
        )
        
        await self.broadcast_to_test(test_id, message)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取广播器统计信息"""
        return {
            "active_connections": len(self._connection_data),
            "max_connections": self._max_connections,
            "total_messages_sent": self._total_messages,
            "total_broadcasts": self._total_broadcasts
        }


# 全局广播器实例
_global_broadcaster: Optional[StressTestBroadcaster] = None


def get_broadcaster() -> StressTestBroadcaster:
    """获取全局广播器实例"""
    global _global_broadcaster
    if _global_broadcaster is None:
        _global_broadcaster = StressTestBroadcaster()
    return _global_broadcaster


def set_broadcaster(broadcaster: StressTestBroadcaster):
    """设置全局广播器实例"""
    global _global_broadcaster
    _global_broadcaster = broadcaster


# ============ 增强版 StressTester ============

class BroadcastEnabledStressTester:
    """
    支持实时广播的压力测试器
    
    在原 StressTester 基础上添加 WebSocket 实时推送
    """
    
    def __init__(self, config, test_id: str = None, broadcaster: StressTestBroadcaster = None):
        """
        Args:
            config: StressTestConfig 配置
            test_id: 测试 ID (用于广播)
            broadcaster: 广播器实例
        """
        from modules.stress_test import StressTester, StressTestConfig
        
        self._inner_tester = StressTester(config)
        self._test_id = test_id or f"test_{int(time.time())}"
        self._broadcaster = broadcaster or get_broadcaster()
        self._config = config
        
        # 设置进度回调
        self._inner_tester.on_progress = self._on_progress_callback
        self._inner_tester.on_complete = self._on_complete_callback
    
    async def _on_progress_callback(self, phase: str, current: int, total: int):
        """进度回调"""
        progress = int((current / total) * 100) if total > 0 else 0
        metrics = self._inner_tester.get_current_metrics()
        
        await self._broadcaster.send_progress(
            test_id=self._test_id,
            phase=phase,
            progress=progress,
            metrics=metrics
        )
    
    async def _on_complete_callback(self, metrics):
        """完成回调"""
        results = self._inner_tester.get_results()
        
        await self._broadcaster.send_complete(
            test_id=self._test_id,
            results=results
        )
    
    async def run(self):
        """运行测试"""
        try:
            return await self._inner_tester.run()
        except Exception as e:
            await self._broadcaster.send_error(
                test_id=self._test_id,
                error=str(e)
            )
            raise
    
    def stop(self):
        """停止测试"""
        self._inner_tester.stop()
    
    def get_results(self) -> Dict:
        """获取测试结果"""
        return self._inner_tester.get_results()
    
    def get_current_metrics(self) -> Dict:
        """获取当前指标"""
        return self._inner_tester.get_current_metrics()


# ============ FastAPI WebSocket 端点 ============

def setup_stress_websocket(app, path: str = "/ws/stress"):
    """
    为 FastAPI 应用添加 WebSocket 端点
    
    Args:
        app: FastAPI 应用
        path: WebSocket 路径
    
    用法:
        from fastapi import FastAPI
        from modules.stress_realtime import setup_stress_websocket
        
        app = FastAPI()
        setup_stress_websocket(app)
    """
    from fastapi import WebSocket, WebSocketDisconnect
    
    broadcaster = get_broadcaster()
    
    @app.websocket(path)
    async def stress_test_websocket(websocket: WebSocket, test_id: str = None):
        """
        压力测试 WebSocket 端点
        
        参数:
            test_id: 可选，订阅特定测试的进度
        
        消息格式:
            {"type": "progress", "test_id": "xxx", "data": {...}}
            {"type": "complete", "test_id": "xxx", "data": {...}}
            {"type": "error", "test_id": "xxx", "data": {...}}
        """
        await websocket.accept()
        
        if not await broadcaster.connect(websocket, test_id):
            await websocket.close(code=1013, reason="连接数达到上限")
            return
        
        try:
            # 保持连接，监听客户端消息
            while True:
                try:
                    # 接收客户端消息 (心跳或订阅)
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    
                    # 处理心跳
                    if data == "ping":
                        await websocket.send_text("pong")
                    
                    # 处理订阅请求
                    elif data.startswith("subscribe:"):
                        new_test_id = data.split(":", 1)[1]
                        broadcaster._connection_data[id(websocket)]["test_id"] = new_test_id
                        await websocket.send_text(f"subscribed:{new_test_id}")
                    
                except asyncio.TimeoutError:
                    # 超时发送心跳检测
                    try:
                        await websocket.send_text("heartbeat")
                    except (WebSocketDisconnect, RuntimeError, OSError):
                        break
                        
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket 错误: {e}")
        finally:
            await broadcaster.disconnect(websocket)
    
    # 添加统计端点
    @app.get("/api/stress/broadcast-stats")
    async def get_broadcast_stats():
        """获取广播器统计信息"""
        return broadcaster.get_stats()
    
    return broadcaster


# 导出
__all__ = [
    'StressTestBroadcaster',
    'BroadcastMessage',
    'BroadcastEnabledStressTester',
    'get_broadcaster',
    'set_broadcaster',
    'setup_stress_websocket',
]
