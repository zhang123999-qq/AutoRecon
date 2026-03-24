/**
 * 压力测试模块（优化版 v2）
 * 处理网站压力测试相关功能，支持无上限配置和智能测试
 */

export class StressTester {
    constructor(options = {}) {
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || (() => {});
        
        this.currentTestId = null;
        this.testCompleted = false;
        this.pollTimer = null;
    }

    /**
     * 开始压力测试
     */
    async start(url, mode, concurrent, duration, maxConcurrent = 10000) {
        if (!url) {
            throw new Error('请输入目标 URL');
        }

        // 验证 URL
        try {
            new URL(url);
        } catch {
            throw new Error('请输入有效的 URL（包含 http:// 或 https://）');
        }

        // 重置状态
        this.testCompleted = false;
        this.currentTestId = null;

        // 发起测试请求
        const response = await fetch('/api/stress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                mode,
                concurrent,
                duration,
                max_concurrent: maxConcurrent
            })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || '创建测试任务失败');
        }

        const data = await response.json();
        this.currentTestId = data.test_id;

        return {
            testId: data.test_id,
            status: 'created'
        };
    }

    /**
     * 快速测试（同步返回）
     */
    async quickTest(url, concurrent, duration, maxConcurrent = 10000) {
        if (!url) {
            throw new Error('请输入目标 URL');
        }

        const response = await fetch('/api/stress/quick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                mode: 'quick',
                concurrent,
                duration,
                max_concurrent: maxConcurrent
            })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || '测试失败');
        }

        return await response.json();
    }

    /**
     * 智能测试
     */
    async intelligentTest(url, maxConcurrent = 1000) {
        if (!url) {
            throw new Error('请输入目标 URL');
        }

        const response = await fetch('/api/stress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                mode: 'intelligent',
                concurrent: 10,
                duration: 30,
                max_concurrent: maxConcurrent
            })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || '创建智能测试任务失败');
        }

        const data = await response.json();
        this.currentTestId = data.test_id;
        this.testCompleted = false;

        return {
            testId: data.test_id,
            status: 'created'
        };
    }

    /**
     * 容量极限测试
     */
    async capacityTest(url, maxConcurrent = 1000) {
        if (!url) {
            throw new Error('请输入目标 URL');
        }

        const response = await fetch('/api/stress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                mode: 'capacity',
                concurrent: 10,
                duration: 30,
                max_concurrent: maxConcurrent
            })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || '创建容量测试任务失败');
        }

        const data = await response.json();
        this.currentTestId = data.test_id;
        this.testCompleted = false;

        return {
            testId: data.test_id,
            status: 'created'
        };
    }

    /**
     * 获取测试状态
     */
    async getStatus(testId) {
        const response = await fetch(`/api/stress/${testId}`);
        if (!response.ok) {
            throw new Error('获取测试状态失败');
        }
        return await response.json();
    }

    /**
     * 开始轮询
     */
    startPolling(testId, interval = 500) {
        this.stopPolling();
        
        const poll = async () => {
            if (this.testCompleted || this.currentTestId !== testId) {
                return;
            }

            try {
                const status = await this.getStatus(testId);
                
                // 实时更新进度
                this.onProgress({
                    status: status.status,
                    progress: status.progress,
                    phase: status.current_phase,
                    results: status.results
                });

                if (status.status === 'completed') {
                    this.testCompleted = true;
                    this.currentTestId = null;
                    this.onComplete(status.results);
                } else if (status.status === 'failed') {
                    this.testCompleted = true;
                    this.currentTestId = null;
                    this.onError(status.error);
                } else if (status.status === 'running') {
                    this.pollTimer = setTimeout(poll, interval);
                }
            } catch (error) {
                this.onError(error.message);
                this.pollTimer = setTimeout(poll, interval * 2);
            }
        };

        poll();
    }

    /**
     * 停止轮询
     */
    stopPolling() {
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }

    /**
     * 重置状态
     */
    reset() {
        this.stopPolling();
        this.testCompleted = false;
        this.currentTestId = null;
    }
}

/**
 * 渲染压力测试结果
 */
export function renderStressResults(results, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const metrics = results.metrics || results;
    
    let html = '';

    // 抗压等级
    if (metrics.stress_level) {
        const levelColors = {
            '优秀': 'success',
            '良好': 'primary',
            '一般': 'warning',
            '较差': 'secondary',
            '危险': 'danger'
        };
        const color = levelColors[metrics.stress_level] || 'secondary';
        html += `
            <div class="result-section">
                <h6>抗压等级: <span class="badge bg-${color}">${metrics.stress_level}</span></h6>
            </div>
        `;
    }

    // 性能评分（如果有）
    if (results.performance_score !== undefined) {
        const scoreColor = results.performance_score >= 80 ? 'success' : 
                          results.performance_score >= 60 ? 'primary' :
                          results.performance_score >= 40 ? 'warning' : 'danger';
        html += `
            <div class="result-section">
                <h6>性能评分: <span class="badge bg-${scoreColor}">${results.performance_score}/100</span></h6>
            </div>
        `;
    }

    // 请求统计
    if (metrics.total_requests !== undefined) {
        html += `
            <div class="result-section">
                <h6><i class="bi bi-hash"></i> 请求统计</h6>
                <div class="row">
                    <div class="col-4">
                        <div class="text-secondary small">总请求数</div>
                        <strong>${metrics.total_requests}</strong>
                    </div>
                    <div class="col-4">
                        <div class="text-secondary small">成功</div>
                        <strong class="text-success">${metrics.successful_requests || 0}</strong>
                    </div>
                    <div class="col-4">
                        <div class="text-secondary small">失败</div>
                        <strong class="text-danger">${metrics.failed_requests || 0}</strong>
                    </div>
                </div>
            </div>
        `;
    }

    // 响应时间
    if (metrics.response_time) {
        const rt = metrics.response_time;
        html += `
            <div class="result-section">
                <h6><i class="bi bi-clock"></i> 响应时间</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <tr>
                            <td>最小</td><td>${rt.min?.toFixed(2) || '-'} ms</td>
                            <td>P50</td><td>${rt.p50?.toFixed(2) || '-'} ms</td>
                        </tr>
                        <tr>
                            <td>平均</td><td><strong>${rt.avg?.toFixed(2) || '-'}</strong> ms</td>
                            <td>P90</td><td>${rt.p90?.toFixed(2) || '-'} ms</td>
                        </tr>
                        <tr>
                            <td>P95</td><td>${rt.p95?.toFixed(2) || '-'} ms</td>
                            <td>P99</td><td>${rt.p99?.toFixed(2) || '-'} ms</td>
                        </tr>
                    </table>
                </div>
            </div>
        `;
    }

    // 吞吐量
    if (metrics.throughput) {
        html += `
            <div class="result-section">
                <h6><i class="bi bi-lightning"></i> 吞吐量</h6>
                <div class="row">
                    <div class="col-6">
                        <div class="text-secondary small">QPS</div>
                        <strong class="text-primary fs-5">${metrics.throughput.qps?.toFixed(2) || 0}</strong>
                        <small class="text-secondary"> 请求/秒</small>
                    </div>
                    <div class="col-6">
                        <div class="text-secondary small">带宽</div>
                        <strong>${metrics.throughput.throughput_mbps?.toFixed(2) || 0}</strong>
                        <small class="text-secondary"> MB/s</small>
                    </div>
                </div>
            </div>
        `;
    }

    // 错误统计
    if (metrics.errors) {
        html += `
            <div class="result-section">
                <h6><i class="bi bi-exclamation-triangle"></i> 错误统计</h6>
                <div class="mb-2">
                    错误率: <strong class="${metrics.errors.error_rate > 10 ? 'text-danger' : 'text-warning'}">${metrics.errors.error_rate?.toFixed(2) || 0}%</strong>
                </div>
                ${metrics.errors.status_codes ? `
                    <div class="small text-secondary">
                        状态码: ${Object.entries(metrics.errors.status_codes).map(([code, count]) => `${code}: ${count}`).join(', ')}
                    </div>
                ` : ''}
            </div>
        `;
    }

    container.innerHTML = html || '<p class="text-secondary">暂无结果</p>';
}

/**
 * 渲染瓶颈分析
 */
export function renderAnalysis(analysis, containerId) {
    const container = document.getElementById(containerId);
    if (!container || !analysis) return;

    const severityColors = {
        'critical': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'secondary'
    };
    const color = severityColors[analysis.severity] || 'secondary';

    let html = `
        <div class="result-section">
            <h6>
                <i class="bi bi-search"></i> 瓶颈类型: 
                <span class="badge bg-info">${analysis.bottleneck_type || '未知'}</span>
                <span class="badge bg-${color} ms-1">${analysis.severity || 'low'}</span>
            </h6>
            <p class="mb-2">${analysis.description || ''}</p>
            <div class="small text-secondary">置信度: ${analysis.confidence || 0}%</div>
        </div>
    `;

    if (analysis.suggestions && analysis.suggestions.length > 0) {
        html += `
            <div class="result-section">
                <h6><i class="bi bi-lightbulb"></i> 优化建议</h6>
                <ul class="mb-0">
                    ${analysis.suggestions.map(s => `<li>${s}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    container.innerHTML = html;
}

/**
 * 渲染容量测试结果
 */
export function renderCapacityResults(results, containerId) {
    const container = document.getElementById(containerId);
    if (!container || !results) return;

    let html = '';

    // 摘要
    if (results.summary) {
        const s = results.summary;
        html += `
            <div class="result-section">
                <h6><i class="bi bi-speedometer2"></i> 容量分析</h6>
                <div class="row text-center">
                    <div class="col-3">
                        <div class="display-6 text-primary">${s.max_qps?.toFixed(0) || 0}</div>
                        <small class="text-secondary">最大 QPS</small>
                    </div>
                    <div class="col-3">
                        <div class="display-6 text-success">${s.optimal_concurrent || 0}</div>
                        <small class="text-secondary">最优并发</small>
                    </div>
                    <div class="col-3">
                        <div class="display-6 text-warning">${s.safe_concurrent || 0}</div>
                        <small class="text-secondary">安全并发</small>
                    </div>
                    <div class="col-3">
                        <div class="display-6 ${s.breaking_concurrent ? 'text-danger' : 'text-success'}">${s.breaking_concurrent || '未达到'}</div>
                        <small class="text-secondary">崩溃点</small>
                    </div>
                </div>
            </div>
        `;
    }

    // 容量曲线表格
    if (results.capacity_curve && results.capacity_curve.length > 0) {
        html += `
            <div class="result-section">
                <h6><i class="bi bi-graph-up"></i> 容量曲线</h6>
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>并发</th>
                                <th>QPS</th>
                                <th>响应时间</th>
                                <th>错误率</th>
                                <th>状态</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${results.capacity_curve.map(p => `
                                <tr class="${p.is_breaking ? 'table-danger' : p.is_optimal ? 'table-success' : ''}">
                                    <td>${p.concurrent}</td>
                                    <td>${p.qps?.toFixed(1)}</td>
                                    <td>${p.avg_time?.toFixed(0)} ms</td>
                                    <td>${p.error_rate?.toFixed(1)}%</td>
                                    <td>
                                        ${p.is_optimal ? '<span class="badge bg-success">最优</span>' : ''}
                                        ${p.is_breaking ? '<span class="badge bg-danger">崩溃</span>' : ''}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 容量等级
    if (results.capacity_level) {
        const levelColors = {
            '高容量': 'success',
            '中等容量': 'primary',
            '标准容量': 'info',
            '低容量': 'warning',
            '受限容量': 'danger'
        };
        html += `
            <div class="result-section">
                <h6>容量等级: <span class="badge bg-${levelColors[results.capacity_level] || 'secondary'}">${results.capacity_level}</span></h6>
            </div>
        `;
    }

    // 建议
    if (results.recommendations && results.recommendations.length > 0) {
        html += `
            <div class="result-section">
                <h6><i class="bi bi-lightbulb"></i> 建议</h6>
                <ul class="mb-0">
                    ${results.recommendations.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    container.innerHTML = html || '<p class="text-secondary">暂无结果</p>';
}

/**
 * 渲染负载测试结果
 */
export function renderLoadTestResults(loadTest, containerId) {
    const container = document.getElementById(containerId);
    if (!container || !loadTest || loadTest.length === 0) return;

    let html = `
        <div class="result-section">
            <h6><i class="bi bi-graph-up"></i> 负载测试结果</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>并发</th>
                            <th>QPS</th>
                            <th>平均响应</th>
                            <th>P99</th>
                            <th>错误率</th>
                            <th>等级</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${loadTest.map(p => `
                            <tr>
                                <td>${p.concurrent}</td>
                                <td>${p.qps?.toFixed(1)}</td>
                                <td>${p.avg_time?.toFixed(0)} ms</td>
                                <td>${p.p99_time?.toFixed(0)} ms</td>
                                <td class="${p.error_rate > 10 ? 'text-danger' : ''}">${p.error_rate?.toFixed(1)}%</td>
                                <td><span class="badge bg-secondary">${p.stress_level || '-'}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    container.innerHTML = html;
}
