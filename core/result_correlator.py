#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoRecon - 结果关联分析器
关联多模块扫描结果，发现攻击面、暴露链、高价值目标
"""

import json
import ipaddress
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class AssetType(Enum):
    """资产类型"""
    DOMAIN = "domain"
    IP = "ip"
    URL = "url"
    SERVICE = "service"
    VULNERABILITY = "vulnerability"
    TECHNOLOGY = "technology"
    CERTIFICATE = "certificate"


class RelationType(Enum):
    """关系类型"""
    RESOLVES_TO = "resolves_to"           # 域名 -> IP
    HOSTS_SERVICE = "hosts_service"       # IP/域名 -> 服务
    RUNS_TECHNOLOGY = "runs_technology"   # 服务/URL -> 技术
    HAS_VULNERABILITY = "has_vulnerability"  # 资产 -> 漏洞
    SAME_IP = "same_ip"                   # 域名 <-> 域名 (共享IP)
    CNAME_CHAIN = "cname_chain"           # 域名 -> CNAME -> ...
    REDIRECTS_TO = "redirects_to"         # URL -> URL
    CONTAINS = "contains"                 # 目录/页面包含关系
    CERTIFICATE_FOR = "certificate_for"   # 证书 -> 域名


@dataclass
class Asset:
    """资产模型"""
    id: str                    # 唯一标识
    type: AssetType
    value: str                 # 显示值
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_modules: List[str] = field(default_factory=list)
    confidence: float = 1.0
    tags: Set[str] = field(default_factory=set)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Asset):
            return self.id == other.id
        return False
    
    def add_source(self, module: str):
        if module not in self.source_modules:
            self.source_modules.append(module)
    
    def merge(self, other: "Asset"):
        """合并另一个资产"""
        self.attributes.update(other.attributes)
        self.add_source(*other.source_modules)
        self.confidence = max(self.confidence, other.confidence)
        self.tags.update(other.tags)


@dataclass
class Relation:
    """资产关系"""
    source: str               # 源资产 ID
    target: str               # 目标资产 ID
    type: RelationType
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_module: str = ""


@dataclass
class AttackPath:
    """攻击路径"""
    steps: List[Dict[str, Any]]
    risk_score: float
    description: str
    assets_involved: List[str]


class AssetGraph:
    """资产知识图谱"""
    
    def __init__(self):
        self.assets: Dict[str, Asset] = {}
        self.relations: List[Relation] = []
        self._adjacency: Dict[str, List[Tuple[str, RelationType]]] = defaultdict(list)
        self._reverse_adjacency: Dict[str, List[Tuple[str, RelationType]]] = defaultdict(list)
    
    def add_asset(self, asset: Asset) -> Asset:
        """添加资产，自动去重合并"""
        if asset.id in self.assets:
            existing = self.assets[asset.id]
            existing.merge(asset)
            return existing
        self.assets[asset.id] = asset
        return asset
    
    def add_relation(self, relation: Relation):
        """添加关系"""
        self.relations.append(relation)
        self._adjacency[relation.source].append((relation.target, relation.type))
        self._reverse_adjacency[relation.target].append((relation.source, relation.type))
    
    def get_asset(self, asset_id: str) -> Optional[Asset]:
        return self.assets.get(asset_id)
    
    def get_neighbors(self, asset_id: str, relation_type: RelationType = None) -> List[Tuple[Asset, Relation]]:
        """获取邻居资产"""
        results = []
        for target_id, rel_type in self._adjacency.get(asset_id, []):
            if relation_type is None or rel_type == relation_type:
                target_asset = self.assets.get(target_id)
                if target_asset:
                    # 找到对应的关系对象
                    for rel in self.relations:
                        if rel.source == asset_id and rel.target == target_id and rel.type == rel_type:
                            results.append((target_asset, rel))
                            break
        return results
    
    def get_reverse_neighbors(self, asset_id: str, relation_type: RelationType = None) -> List[Tuple[Asset, Relation]]:
        """获取反向邻居"""
        results = []
        for source_id, rel_type in self._reverse_adjacency.get(asset_id, []):
            if relation_type is None or rel_type == relation_type:
                source_asset = self.assets.get(source_id)
                if source_asset:
                    for rel in self.relations:
                        if rel.source == source_id and rel.target == asset_id and rel.type == rel_type:
                            results.append((source_asset, rel))
                            break
        return results
    
    def find_paths(self, start_id: str, end_id: str, max_depth: int = 5) -> List[List[Tuple[Asset, Relation]]]:
        """查找两个资产间的路径 (BFS)"""
        if start_id not in self.assets or end_id not in self.assets:
            return []
        
        queue = [(start_id, [])]
        visited = {start_id}
        paths = []
        
        while queue:
            current_id, path = queue.pop(0)
            
            if len(path) >= max_depth:
                continue
            
            if current_id == end_id:
                paths.append(path)
                continue
            
            for neighbor_id, rel_type in self._adjacency.get(current_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    # 找到关系对象
                    rel_obj = None
                    for rel in self.relations:
                        if rel.source == current_id and rel.target == neighbor_id and rel.type == rel_type:
                            rel_obj = rel
                            break
                    if rel_obj:
                        new_path = path + [(self.assets[current_id], rel_obj)]
                        queue.append((neighbor_id, new_path))
        
        return paths
    
    def get_subgraph(self, asset_ids: List[str], depth: int = 1) -> "AssetGraph":
        """提取子图"""
        subgraph = AssetGraph()
        visited = set()
        
        def traverse(aid: str, d: int):
            if aid in visited or d > depth:
                return
            visited.add(aid)
            asset = self.assets.get(aid)
            if asset:
                subgraph.add_asset(asset)
            
            if d < depth:
                for neighbor_id, _ in self._adjacency.get(aid, []):
                    traverse(neighbor_id, d + 1)
                for neighbor_id, _ in self._reverse_adjacency.get(aid, []):
                    traverse(neighbor_id, d + 1)
        
        for aid in asset_ids:
            traverse(aid, 0)
        
        return subgraph
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "assets": {aid: {
                "id": a.id,
                "type": a.type.value,
                "value": a.value,
                "attributes": a.attributes,
                "source_modules": a.source_modules,
                "confidence": a.confidence,
                "tags": list(a.tags),
            } for aid, a in self.assets.items()},
            "relations": [{
                "source": r.source,
                "target": r.target,
                "type": r.type.value,
                "attributes": r.attributes,
                "confidence": r.confidence,
                "source_module": r.source_module,
            } for r in self.relations],
        }


class ResultCorrelator:
    """结果关联分析器
    
    摄入多模块扫描结果，构建资产图谱，识别：
    - 高价值目标 (敏感服务、漏洞、配置错误)
    - 暴露链 (域名 -> IP -> 服务 -> 漏洞)
    - 攻击路径
    - 资产聚类
    """
    
    def __init__(self):
        self.graph = AssetGraph()
        self.scan_metadata: Dict[str, Any] = {}
    
    def ingest(self, module: str, results: Dict[str, Any]):
        """摄入模块结果"""
        handlers = {
            "subdomain": self._ingest_subdomain,
            "port": self._ingest_port,
            "cdn": self._ingest_cdn,
            "fingerprint": self._ingest_fingerprint,
            "vuln": self._ingest_vuln,
            "sqli": self._ingest_sqli,
            "sensitive": self._ingest_sensitive,
            "stress": self._ingest_stress,
            "ssl": self._ingest_ssl,
            "whois": self._ingest_whois,
            "dir": self._ingest_dir,
            "takeover": self._ingest_takeover,
        }
        
        handler = handlers.get(module)
        if handler:
            try:
                handler(results)
            except Exception as e:
                logger.warning(f"摄入 {module} 结果失败: {e}")
        else:
            logger.debug(f"无处理器的模块: {module}")
    
    def _make_asset_id(self, asset_type: AssetType, value: str, **kwargs) -> str:
        """生成资产 ID"""
        if asset_type == AssetType.SERVICE:
            host = kwargs.get("host", "")
            port = kwargs.get("port", 0)
            return f"service:{host}:{port}"
        elif asset_type == AssetType.URL:
            return f"url:{value}"
        elif asset_type == AssetType.VULNERABILITY:
            vuln_type = kwargs.get("vuln_type", "unknown")
            url = kwargs.get("url", "")
            return f"vuln:{vuln_type}:{hash(url) % 1000000}"
        else:
            return f"{asset_type.value}:{value}"
    
    # ============ 摄入处理器 ============
    
    def _ingest_subdomain(self, results: Dict):
        """摄入子域名结果"""
        for detail in results.get("details", []):
            domain = detail.get("subdomain")
            ip = detail.get("ip")
            source = detail.get("source", "unknown")
            
            if not domain:
                continue
            
            # 域名资产
            domain_id = self._make_asset_id(AssetType.DOMAIN, domain)
            domain_asset = Asset(
                id=domain_id,
                type=AssetType.DOMAIN,
                value=domain,
                attributes={"source": source, "resolved": bool(ip)},
                source_modules=["subdomain"],
            )
            self.graph.add_asset(domain_asset)
            
            # IP 资产及关联
            if ip:
                ip_id = self._make_asset_id(AssetType.IP, ip)
                ip_asset = Asset(
                    id=ip_id,
                    type=AssetType.IP,
                    value=ip,
                    attributes={"type": "resolved"},
                    source_modules=["subdomain"],
                )
                self.graph.add_asset(ip_asset)
                
                # 域名 -> IP 关系
                self.graph.add_relation(Relation(
                    source=domain_id,
                    target=ip_id,
                    type=RelationType.RESOLVES_TO,
                    attributes={"source": source},
                    source_module="subdomain",
                ))
                
                # 记录 IP 上的域名
                ip_asset.attributes.setdefault("domains", []).append(domain)
    
    def _ingest_port(self, results: Dict):
        """摄入端口扫描结果"""
        for host, data in results.get("hosts", {}).items():
            for port in data.get("open_ports", []):
                service_id = self._make_asset_id(AssetType.SERVICE, "", host=host, port=port)
                service_asset = Asset(
                    id=service_id,
                    type=AssetType.SERVICE,
                    value=f"{host}:{port}",
                    attributes={"host": host, "port": port, "protocol": "tcp"},
                    source_modules=["port"],
                )
                self.graph.add_asset(service_asset)
                
                # 关联到主机 (IP 或域名)
                host_asset_id = None
                # 尝试作为 IP 查找
                try:
                    ipaddress.ip_address(host)
                    host_asset_id = self._make_asset_id(AssetType.IP, host)
                except ValueError:
                    # 作为域名查找
                    host_asset_id = self._make_asset_id(AssetType.DOMAIN, host)
                
                if host_asset_id and host_asset_id in self.graph.assets:
                    self.graph.add_relation(Relation(
                        source=host_asset_id,
                        target=service_id,
                        type=RelationType.HOSTS_SERVICE,
                        source_module="port",
                    ))
    
    def _ingest_cdn(self, results: Dict):
        """摄入 CDN 检测结果"""
        domain = results.get("domain", "")
        cdn = results.get("cdn")
        ips = results.get("ips", [])
        
        if domain:
            domain_id = self._make_asset_id(AssetType.DOMAIN, domain)
            domain_asset = self.graph.get_asset(domain_id)
            if domain_asset:
                if cdn:
                    domain_asset.attributes["cdn"] = cdn
                    domain_asset.tags.add("cdn")
                if ips:
                    domain_asset.attributes["resolved_ips"] = ips
    
    def _ingest_fingerprint(self, results: Dict):
        """摄入指纹识别结果"""
        # 指纹通常关联到主域名或 URL
        fingerprints = results.get("fingerprints", [])
        
        # 这里简化处理，实际应该关联到具体的 URL/服务
        for fp in fingerprints:
            tech_id = self._make_asset_id(AssetType.TECHNOLOGY, fp)
            tech_asset = Asset(
                id=tech_id,
                type=AssetType.TECHNOLOGY,
                value=fp,
                attributes={"category": "fingerprint"},
                source_modules=["fingerprint"],
            )
            self.graph.add_asset(tech_asset)
    
    def _ingest_vuln(self, results: Dict):
        """摄入漏洞扫描结果"""
        for vuln in results:
            if isinstance(vuln, dict):
                url = vuln.get("url", "")
                vuln_type = vuln.get("type", "unknown")
                severity = vuln.get("severity", "medium")
                
                if not url:
                    continue
                
                vuln_id = self._make_asset_id(
                    AssetType.VULNERABILITY, "", vuln_type=vuln_type, url=url
                )
                vuln_asset = Asset(
                    id=vuln_id,
                    type=AssetType.VULNERABILITY,
                    value=f"{vuln_type} @ {url}",
                    attributes={
                        "url": url,
                        "type": vuln_type,
                        "severity": severity,
                        "details": vuln,
                    },
                    source_modules=["vuln"],
                    tags={"vulnerability", severity},
                )
                self.graph.add_asset(vuln_asset)
                
                # 关联到 URL
                url_id = self._make_asset_id(AssetType.URL, url)
                url_asset = self.graph.get_asset(url_id)
                if not url_asset:
                    url_asset = Asset(
                        id=url_id,
                        type=AssetType.URL,
                        value=url,
                        source_modules=["vuln"],
                    )
                    self.graph.add_asset(url_asset)
                
                self.graph.add_relation(Relation(
                    source=url_id,
                    target=vuln_id,
                    type=RelationType.HAS_VULNERABILITY,
                    attributes={"severity": severity},
                    source_module="vuln",
                ))
    
    def _ingest_sqli(self, results: Dict):
        """摄入 SQL 注入结果"""
        for sqli in results:
            if isinstance(sqli, dict) and sqli.get("vulnerable"):
                url = sqli.get("url", "")
                param = sqli.get("parameter", "")
                dbms = sqli.get("dbms", "")
                
                if not url:
                    continue
                
                vuln_id = self._make_asset_id(
                    AssetType.VULNERABILITY, "", vuln_type="sqli", url=url
                )
                vuln_asset = Asset(
                    id=vuln_id,
                    type=AssetType.VULNERABILITY,
                    value=f"SQLi @ {url} ({param})",
                    attributes={
                        "url": url,
                        "parameter": param,
                        "dbms": dbms,
                        "type": "sqli",
                        "severity": "high",
                        "details": sqli,
                    },
                    source_modules=["sqli"],
                    tags={"vulnerability", "sqli", "high"},
                )
                self.graph.add_asset(vuln_asset)
                
                # 关联到 URL
                url_id = self._make_asset_id(AssetType.URL, url)
                url_asset = self.graph.get_asset(url_id)
                if not url_asset:
                    url_asset = Asset(
                        id=url_id,
                        type=AssetType.URL,
                        value=url,
                        source_modules=["sqli"],
                    )
                    self.graph.add_asset(url_asset)
                
                self.graph.add_relation(Relation(
                    source=url_id,
                    target=vuln_id,
                    type=RelationType.HAS_VULNERABILITY,
                    attributes={"severity": "high", "type": "sqli"},
                    source_module="sqli",
                ))
    
    def _ingest_sensitive(self, results: Dict):
        """摄入敏感信息结果"""
        findings = results.get("findings", [])
        url = results.get("url", "")
        
        if not findings:
            return
        
        for finding in findings:
            info_type = finding.get("type", "unknown")
            count = finding.get("count", 0)
            
            # 创建敏感信息资产
            sens_id = self._make_asset_id(
                AssetType.VULNERABILITY, "", vuln_type=f"sensitive_{info_type}", url=url
            )
            sens_asset = Asset(
                id=sens_id,
                type=AssetType.VULNERABILITY,
                value=f"敏感信息: {info_type} @ {url}",
                attributes={
                    "url": url,
                    "type": f"sensitive_{info_type}",
                    "severity": "medium",
                    "count": count,
                    "sample": finding.get("sample", ""),
                },
                source_modules=["sensitive"],
                tags={"sensitive", info_type.lower().replace(" ", "_")},
            )
            self.graph.add_asset(sens_asset)
            
            # 关联到 URL
            url_id = self._make_asset_id(AssetType.URL, url)
            url_asset = self.graph.get_asset(url_id)
            if not url_asset:
                url_asset = Asset(
                    id=url_id,
                    type=AssetType.URL,
                    value=url,
                    source_modules=["sensitive"],
                )
                self.graph.add_asset(url_asset)
            
            self.graph.add_relation(Relation(
                source=url_id,
                target=sens_id,
                type=RelationType.HAS_VULNERABILITY,
                attributes={"severity": "medium"},
                source_module="sensitive",
            ))
    
    def _ingest_stress(self, results: Dict):
        """摄入压力测试结果"""
        metrics = results.get("metrics", {})
        url = results.get("config", {}).get("target_url", "")
        
        if url:
            url_id = self._make_asset_id(AssetType.URL, url)
            url_asset = self.graph.get_asset(url_id)
            if not url_asset:
                url_asset = Asset(
                    id=url_id,
                    type=AssetType.URL,
                    value=url,
                    source_modules=["stress"],
                )
                self.graph.add_asset(url_asset)
            
            url_asset.attributes["stress_metrics"] = metrics
            url_asset.tags.add("stress_tested")
    
    def _ingest_ssl(self, results: Dict):
        """摄入 SSL 证书结果"""
        # 证书信息关联到域名
        pass
    
    def _ingest_whois(self, results: Dict):
        """摄入 Whois 结果"""
        # Whois 信息丰富域名资产
        pass
    
    def _ingest_dir(self, results: Dict):
        """摄入目录扫描结果"""
        pass
    
    def _ingest_takeover(self, results: Dict):
        """摄入子域名接管结果"""
        pass
    
    # ============ 分析方法 ============
    
    def analyze_attack_surface(self) -> Dict[str, Any]:
        """攻击面分析"""
        analysis = {
            "total_assets": len(self.graph.assets),
            "by_type": defaultdict(int),
            "high_value_targets": [],
            "exposure_chains": [],
            "vulnerability_summary": defaultdict(int),
            "recommendations": [],
        }
        
        # 统计资产类型
        for asset in self.graph.assets.values():
            analysis["by_type"][asset.type.value] += 1
        
        # 识别高价值目标
        for asset in self.graph.assets.values():
            if asset.type == AssetType.SERVICE:
                port = asset.attributes.get("port", 0)
                if port in [22, 23, 3389, 3306, 5432, 6379, 27017, 9200, 11211]:
                    analysis["high_value_targets"].append({
                        "asset": asset.id,
                        "value": asset.value,
                        "reason": f"敏感服务端口暴露 ({port})",
                        "severity": "high" if port in [22, 3389, 3306, 5432, 6379] else "medium",
                    })
            
            elif asset.type == AssetType.VULNERABILITY:
                severity = asset.attributes.get("severity", "medium")
                analysis["high_value_targets"].append({
                    "asset": asset.id,
                    "value": asset.value,
                    "reason": f"漏洞: {asset.attributes.get('type', 'unknown')}",
                    "severity": severity,
                })
                analysis["vulnerability_summary"][severity] += 1
        
        # 发现暴露链
        analysis["exposure_chains"] = self._find_exposure_chains()
        
        # 生成建议
        analysis["recommendations"] = self._generate_recommendations()
        
        return analysis
    
    def _find_exposure_chains(self) -> List[Dict]:
        """发现暴露链: 域名 -> IP -> 服务 -> 漏洞"""
        chains = []
        
        # 遍历所有域名
        for asset in self.graph.assets.values():
            if asset.type != AssetType.DOMAIN:
                continue
            
            # 域名 -> IP
            ip_relations = self.graph.get_neighbors(asset.id, RelationType.RESOLVES_TO)
            for ip_asset, rel in ip_relations:
                # IP -> 服务
                service_relations = self.graph.get_neighbors(ip_asset.id, RelationType.HOSTS_SERVICE)
                for service_asset, srel in service_relations:
                    # 服务 -> 漏洞 (通过 URL 关联)
                    # 这里需要通过 URL 关联，简化处理
                    vuln_relations = self.graph.get_neighbors(service_asset.id, RelationType.HAS_VULNERABILITY)
                    
                    chain = {
                        "domain": asset.value,
                        "ip": ip_asset.value,
                        "service": service_asset.value,
                        "vulnerabilities": [v.value for v, _ in vuln_relations],
                    }
                    
                    if chain["vulnerabilities"]:
                        chains.append(chain)
        
        return chains
    
    def _generate_recommendations(self) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        # 检查敏感端口暴露
        sensitive_ports = [22, 23, 3389, 3306, 5432, 6379, 27017]
        exposed = []
        for asset in self.graph.assets.values():
            if asset.type == AssetType.SERVICE:
                port = asset.attributes.get("port", 0)
                if port in sensitive_ports:
                    exposed.append(f"{asset.value} (端口 {port})")
        
        if exposed:
            recommendations.append(
                f"发现 {len(exposed)} 个敏感服务端口暴露: {', '.join(exposed[:5])}"
                f"{'...' if len(exposed) > 5 else ''}。建议配置防火墙限制访问或使用 VPN。"
            )
        
        # 检查高危漏洞
        critical_vulns = sum(1 for a in self.graph.assets.values() 
                           if a.type == AssetType.VULNERABILITY and a.attributes.get("severity") == "high")
        if critical_vulns > 0:
            recommendations.append(f"发现 {critical_vulns} 个高危漏洞，建议优先修复。")
        
        # 检查 CDN 配置
        domains_without_cdn = 0
        for asset in self.graph.assets.values():
            if asset.type == AssetType.DOMAIN and "cdn" not in asset.attributes:
                domains_without_cdn += 1
        
        if domains_without_cdn > 0:
            recommendations.append(f"{domains_without_cdn} 个域名未检测到 CDN，建议考虑启用 CDN 以提高安全性和性能。")
        
        return recommendations
    
    def find_attack_paths(self, target_types: List[AssetType] = None) -> List[AttackPath]:
        """查找攻击路径"""
        if target_types is None:
            target_types = [AssetType.VULNERABILITY]
        
        paths = []
        
        # 找到所有目标资产
        targets = [a for a in self.graph.assets.values() if a.type in target_types]
        
        # 从每个目标向上追溯到入口点 (域名/IP)
        for target in targets:
            entry_points = self._trace_to_entry(target.id)
            
            for entry_path in entry_points:
                risk_score = self._calculate_path_risk(entry_path)
                path = AttackPath(
                    steps=entry_path,
                    risk_score=risk_score,
                    description=self._describe_path(entry_path),
                    assets_involved=[step["asset"] for step in entry_path],
                )
                paths.append(path)
        
        # 按风险评分排序
        paths.sort(key=lambda p: p.risk_score, reverse=True)
        return paths
    
    def _trace_to_entry(self, asset_id: str, max_depth: int = 5) -> List[List[Dict]]:
        """追溯到入口点 (域名/IP)"""
        entry_types = {AssetType.DOMAIN, AssetType.IP}
        paths = []
        
        def dfs(current_id: str, path: List[Dict], depth: int):
            if depth > max_depth:
                return
            
            asset = self.graph.get_asset(current_id)
            if not asset:
                return
            
            new_path = path + [{
                "asset": current_id,
                "type": asset.type.value,
                "value": asset.value,
                "attributes": asset.attributes,
            }]
            
            if asset.type in entry_types:
                paths.append(new_path)
                return
            
            # 向上追溯
            for source_asset, rel in self.graph.get_reverse_neighbors(current_id):
                dfs(source_asset.id, new_path, depth + 1)
        
        dfs(asset_id, [], 0)
        return paths
    
    def _calculate_path_risk(self, path: List[Dict]) -> float:
        """计算路径风险评分"""
        score = 0.0
        for step in path:
            asset = self.graph.get_asset(step["asset"])
            if asset and asset.type == AssetType.VULNERABILITY:
                severity = asset.attributes.get("severity", "medium")
                score += {"critical": 10, "high": 7, "medium": 4, "low": 1}.get(severity, 4)
            elif asset and asset.type == AssetType.SERVICE:
                port = asset.attributes.get("port", 0)
                if port in [22, 23, 3389, 3306, 5432, 6379]:
                    score += 3
        return score
    
    def _describe_path(self, path: List[Dict]) -> str:
        """描述攻击路径"""
        steps = []
        for step in path:
            asset = self.graph.get_asset(step["asset"])
            if asset:
                steps.append(f"{asset.type.value}:{asset.value}")
        return " -> ".join(steps)
    
    def get_asset_clusters(self, min_size: int = 2) -> List[List[Asset]]:
        """获取资产聚类 (基于共享 IP)"""
        ip_to_domains = defaultdict(list)
        
        for asset in self.graph.assets.values():
            if asset.type == AssetType.DOMAIN:
                # 查找关联的 IP
                for _, rel in self.graph.get_neighbors(asset.id, RelationType.RESOLVES_TO):
                    ip_to_domains[rel.target].append(asset)
        
        clusters = []
        for ip_id, domains in ip_to_domains.items():
            if len(domains) >= min_size:
                cluster = [self.graph.get_asset(ip_id)] + domains
                clusters.append([a for a in cluster if a])
        
        return clusters
    
    def export_graph(self, format: str = "json") -> str:
        """导出图谱"""
        if format == "json":
            return json.dumps(self.graph.to_dict(), indent=2, ensure_ascii=False)
        elif format == "graphml":
            # 简化的 GraphML 导出
            return self._export_graphml()
        else:
            raise ValueError(f"不支持的格式: {format}")
    
    def _export_graphml(self) -> str:
        """导出 GraphML 格式"""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
                 '  <graph id="assetGraph" edgedefault="directed">']
        
        # 节点
        for asset in self.graph.assets.values():
            lines.append(f'    <node id="{asset.id}">')
            lines.append(f'      <data key="type">{asset.type.value}</data>')
            lines.append(f'      <data key="value">{asset.value}</data>')
            lines.append(f'      <data key="modules">{",".join(asset.source_modules)}</data>')
            lines.append('    </node>')
        
        # 边
        for rel in self.graph.relations:
            lines.append(f'    <edge source="{rel.source}" target="{rel.target}">')
            lines.append(f'      <data key="type">{rel.type.value}</data>')
            lines.append('    </edge>')
        
        lines.extend(['  </graph>', '</graphml>'])
        return '\n'.join(lines)
    
    def generate_report(self) -> str:
        """生成关联分析报告"""
        analysis = self.analyze_attack_surface()
        
        lines = [
            "=" * 60,
            "攻击面关联分析报告",
            "=" * 60,
            f"总资产数: {analysis['total_assets']}",
            "",
            "资产分布:",
        ]
        
        for typ, count in analysis["by_type"].items():
            lines.append(f"  {typ}: {count}")
        
        if analysis["high_value_targets"]:
            lines.extend(["", "高价值目标:"])
            for target in analysis["high_value_targets"][:10]:
                lines.append(f"  [{target['severity'].upper()}] {target['asset']} - {target['reason']}")
        
        if analysis["exposure_chains"]:
            lines.extend(["", "暴露链:"])
            for chain in analysis["exposure_chains"][:5]:
                lines.append(f"  {chain['domain']} -> {chain['ip']} -> {chain['service']} -> {len(chain['vulnerabilities'])} 个漏洞")
        
        if analysis["recommendations"]:
            lines.extend(["", "修复建议:"])
            for rec in analysis["recommendations"]:
                lines.append(f"  • {rec}")
        
        lines.extend(["", "=" * 60])
        return "\n".join(lines)


# ============ 使用示例 ============

if __name__ == "__main__":
    correlator = ResultCorrelator()
    
    # 模拟摄入子域名结果
    correlator.ingest("subdomain", {
        "details": [
            {"subdomain": "www.example.com", "ip": "1.2.3.4", "source": "dns"},
            {"subdomain": "api.example.com", "ip": "1.2.3.4", "source": "dns"},
            {"subdomain": "admin.example.com", "ip": "5.6.7.8", "source": "certificate"},
        ]
    })
    
    # 模拟摄入端口扫描
    correlator.ingest("port", {
        "hosts": {
            "1.2.3.4": {"open_ports": [80, 443, 3306]},
            "5.6.7.8": {"open_ports": [22, 80]},
        }
    })
    
    # 模拟摄入漏洞
    correlator.ingest("vuln", [
        {"url": "http://www.example.com/admin", "type": "unauthorized_access", "severity": "high"},
        {"url": "http://api.example.com/users", "type": "idor", "severity": "medium"},
    ])
    
    # 模拟摄入 SQLi
    correlator.ingest("sqli", [
        {"url": "http://www.example.com/product?id=1", "vulnerable": True, 
         "parameter": "id", "dbms": "MySQL", "injection_type": "UNION query"},
    ])
    
    # 生成报告
    print(correlator.generate_report())
    
    # 导出图谱
    print("\n--- GraphML 导出示例 ---")
    print(correlator.export_graph("graphml")[:500] + "...")