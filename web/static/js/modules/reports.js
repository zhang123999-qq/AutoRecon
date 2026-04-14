/**
 * 报告模块
 * 处理报告加载、显示和下载
 */

export class ReportManager {
    constructor(options = {}) {
        this.onViewReport = options.onViewReport || (() => {});
    }

    /**
     * 加载报告列表
     */
    async loadList() {
        const response = await fetch('/api/reports');
        if (!response.ok) {
            throw new Error('加载报告列表失败');
        }
        return await response.json();
    }

    /**
     * 获取报告详情
     */
    async get(filename) {
        const response = await fetch(`/api/reports/${filename}`);
        if (!response.ok) {
            throw new Error('加载报告失败');
        }
        return await response.json();
    }

    /**
     * 获取下载链接
     */
    getDownloadUrl(filename) {
        return `/api/download/${filename}`;
    }

    /**
     * 渲染报告列表
     */
    renderList(reports, containerId) {
        const tbody = document.getElementById(containerId);
        
        if (!reports || reports.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary">暂无报告</td></tr>';
            return;
        }

        tbody.innerHTML = reports.map(r => `
            <tr>
                <td><code>${r.file}</code></td>
                <td>${r.target}</td>
                <td>${r.scan_time}</td>
                <td>${(r.size / 1024).toFixed(1)} KB</td>
                <td>
                    <a href="${this.getDownloadUrl(r.file)}" class="btn btn-sm btn-outline-light">
                        <i class="bi bi-download"></i> 下载
                    </a>
                    <button class="btn btn-sm btn-outline-light ms-1" data-report="${r.file}">
                        <i class="bi bi-eye"></i> 查看
                    </button>
                </td>
            </tr>
        `).join('');

        // 绑定查看按钮事件
        tbody.querySelectorAll('button[data-report]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.onViewReport(btn.dataset.report);
            });
        });
    }

    /**
     * 渲染扫描结果
     */
    renderResults(results, containerId) {
        const container = document.getElementById(containerId);
        
        let html = '';

        // 子域名
        if (results.subdomain) {
            html += this._renderSubdomain(results.subdomain);
        }

        // 开放端口
        if (results.port?.hosts) {
            html += this._renderPorts(results.port);
        }

        // CDN
        if (results.cdn) {
            html += this._renderCDN(results.cdn);
        }

        // 指纹
        if (results.fingerprint?.fingerprints?.length) {
            html += this._renderFingerprint(results.fingerprint);
        }

        // 敏感信息
        if (results.sensitive?.findings?.length) {
            html += this._renderSensitive(results.sensitive);
        }

        // 漏洞
        if (results.vulnerabilities?.length) {
            html += this._renderVulnerabilities(results.vulnerabilities);
        }

        // SQL注入
        if (results.sqli?.length) {
            html += this._renderSQLi(results.sqli);
        }

        container.innerHTML = html || '<p class="text-secondary">暂无结果</p>';
    }

    _renderSubdomain(data) {
        const subs = data.details || [];
        return `
            <div class="result-section">
                <h6><i class="bi bi-globe"></i> 子域名 (${data.count || 0})</h6>
                <div class="row">
                    ${subs.slice(0, 20).map(s => `
                        <div class="col-md-4 mb-1">
                            <small>${s.subdomain}</small>
                            ${s.ip ? `<span class="text-secondary">(${s.ip})</span>` : ''}
                        </div>
                    `).join('')}
                </div>
                ${subs.length > 20 ? `<small class="text-secondary">还有 ${subs.length - 20} 个...</small>` : ''}
            </div>
        `;
    }

    _renderPorts(data) {
        const hosts = Object.entries(data.hosts);
        return `
            <div class="result-section">
                <h6><i class="bi bi-plug"></i> 开放端口</h6>
                ${hosts.map(([host, info]) => `
                    <div class="mb-2">
                        <strong>${host}</strong>: 
                        ${info.open_ports?.length ? info.open_ports.join(', ') : '无开放端口'}
                    </div>
                `).join('')}
            </div>
        `;
    }

    _renderCDN(data) {
        return `
            <div class="result-section">
                <h6><i class="bi bi-cloud"></i> CDN检测</h6>
                <p>CDN: <strong>${data.cdn || '未检测到'}</strong></p>
                <small class="text-secondary">IP: ${data.ips?.join(', ') || 'N/A'}</small>
            </div>
        `;
    }

    _renderFingerprint(data) {
        return `
            <div class="result-section">
                <h6><i class="bi bi-fingerprint"></i> 指纹识别 (${data.fingerprints.length})</h6>
                <div>${data.fingerprints.map(f => 
                    `<span class="badge bg-secondary me-1">${f}</span>`
                ).join('')}</div>
            </div>
        `;
    }

    _renderSensitive(data) {
        return `
            <div class="result-section">
                <h6 class="text-warning"><i class="bi bi-exclamation-triangle"></i> 敏感信息 (${data.findings.length})</h6>
                <ul>
                    ${data.findings.map(f => `<li>${f.type}: ${f.count} 处</li>`).join('')}
                </ul>
            </div>
        `;
    }

    _renderVulnerabilities(data) {
        const high = data.filter(v => v.severity === 'high').length;
        return `
            <div class="result-section">
                <h6 class="text-danger"><i class="bi bi-bug"></i> 漏洞 (${data.length}, 高危: ${high})</h6>
                <ul>
                    ${data.slice(0, 10).map(v => `
                        <li>
                            <span class="badge ${v.severity === 'high' ? 'bg-danger' : 'bg-warning'}">${v.severity}</span>
                            ${v.name || v.type} - ${v.url || ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    _renderSQLi(data) {
        const vulnerable = data.filter(s => s.vulnerable);
        
        if (vulnerable.length === 0) {
            return `
                <div class="result-section">
                    <h6><i class="bi bi-database"></i> SQL注入扫描</h6>
                    <p class="text-success">未发现 SQL 注入漏洞</p>
                    <small class="text-secondary">共扫描 ${data.length} 个 URL</small>
                </div>
            `;
        }
        
        return `
            <div class="result-section">
                <h6 class="text-danger"><i class="bi bi-database"></i> SQL注入 (${vulnerable.length} 个漏洞)</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>URL</th>
                                <th>参数</th>
                                <th>类型</th>
                                <th>数据库</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${vulnerable.map(s => `
                                <tr>
                                    <td><code>${s.url}</code></td>
                                    <td><strong>${s.parameter || '-'}</strong></td>
                                    <td><span class="badge bg-warning">${s.injection_type || 'unknown'}</span></td>
                                    <td><span class="badge bg-info">${s.dbms || 'unknown'}</span></td>
                                </tr>
                                ${s.payload ? `
                                <tr>
                                    <td colspan="4" class="text-secondary">
                                        <small>Payload: <code>${s.payload.substring(0, 100)}${s.payload.length > 100 ? '...' : ''}</code></small>
                                    </td>
                                </tr>
                                ` : ''}
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                <small class="text-secondary">共扫描 ${data.length} 个 URL</small>
            </div>
        `;
    }
}
