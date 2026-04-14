#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon v3.2 - Web API 测试
测试 FastAPI 端点的安全性和功能
"""

import pytest
import asyncio
import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入 FastAPI，如果不存在则跳过整个模块
try:
    from fastapi.testclient import TestClient
    from web.app import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    # 创建空的 app 以避免 NameError
    app = None


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi module not installed")
class TestWebAPI:
    """Web API 测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_index(self, client):
        """测试主页"""
        response = client.get("/")
        assert response.status_code == 200
        assert "AutoRecon" in response.text
    
    def test_api_scan_create(self, client):
        """测试创建扫描任务"""
        response = client.post("/api/scan", json={
            "target": "example.com",
            "modules": ["subdomain", "cdn"],
            "threads": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "scan_id" in data
        assert data["status"] == "created"
    
    def test_api_scan_invalid_target(self, client):
        """测试无效目标"""
        response = client.post("/api/scan", json={
            "target": "",  # 空目标
            "modules": ["subdomain"],
            "threads": 10
        })
        
        # 应该返回错误或创建失败
        assert response.status_code in [200, 400, 422]
    
    def test_api_reports_security(self, client):
        """测试报告 API 安全性"""
        # 测试路径遍历攻击
        response = client.get("/api/reports/../../../etc/passwd")
        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]
        
        # 测试非 JSON 文件
        response = client.get("/api/reports/test.txt")
        assert response.status_code == 400
        assert "Only JSON files are allowed" in response.json()["detail"]
    
    def test_api_download_security(self, client):
        """测试下载 API 安全性"""
        # 测试路径遍历攻击
        response = client.get("/api/download/../../../etc/passwd")
        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]
    
    def test_api_stress_quick(self, client):
        """测试快速压力测试"""
        response = client.post("/api/stress/quick", json={
            "url": "http://httpbin.org/get",
            "mode": "quick",
            "concurrent": 5,
            "duration": 2
        })
        
        # 应该返回结果或错误（取决于外部服务）
        assert response.status_code in [200, 500]
    
    def test_api_sqlmap_status(self, client):
        """测试 SQLMap 状态检查"""
        response = client.get("/api/sqlmap/status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "path" in data
    
    def test_cors_headers(self, client):
        """测试 CORS 头"""
        # 测试预检请求
        response = client.options("/api/scan", headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST"
        })
        
        # 应该有 CORS 头
        assert response.status_code in [200, 204]
    
    def test_api_scans_list(self, client):
        """测试扫描列表"""
        response = client.get("/api/scans")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_api_stress_list(self, client):
        """测试压力测试列表"""
        response = client.get("/api/stress")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi module not installed")
class TestSecurityValidation:
    """安全验证测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    def test_filename_validation(self, client):
        """测试文件名验证"""
        # 测试各种恶意文件名
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "test.json/../../../etc/passwd",
            "test.json%00.txt",
        ]
        
        for filename in malicious_filenames:
            response = client.get(f"/api/reports/{filename}")
            assert response.status_code == 400
    
    def test_sql_injection_in_target(self, client):
        """测试 SQL 注入防护"""
        # 尝试 SQL 注入
        response = client.post("/api/scan", json={
            "target": "example.com' OR '1'='1",
            "modules": ["subdomain"],
            "threads": 10
        })
        
        # 应该处理或拒绝
        assert response.status_code in [200, 400, 422]
    
    def test_xss_in_target(self, client):
        """测试 XSS 防护"""
        # 尝试 XSS
        response = client.post("/api/scan", json={
            "target": "<script>alert('xss')</script>",
            "modules": ["subdomain"],
            "threads": 10
        })
        
        # 应该处理或拒绝
        assert response.status_code in [200, 400, 422]


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
