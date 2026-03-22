/**
 * 历史记录模块
 * 管理扫描历史
 */

export class HistoryManager {
    /**
     * 加载扫描历史
     */
    async load() {
        const response = await fetch('/api/scans');
        if (!response.ok) {
            throw new Error('加载历史记录失败');
        }
        return await response.json();
    }

    /**
     * 渲染历史列表
     */
    render(scans, containerId) {
        const tbody = document.getElementById(containerId);
        
        if (!scans || scans.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary">暂无扫描记录</td></tr>';
            return;
        }

        const statusMap = {
            'pending': '等待中',
            'running': '运行中',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        };

        tbody.innerHTML = scans.map(s => `
            <tr>
                <td><code>${s.scan_id}</code></td>
                <td>${s.target}</td>
                <td><span class="status-badge status-${s.status}">${statusMap[s.status] || s.status}</span></td>
                <td>
                    <div class="progress" style="width: 100px; height: 6px;">
                        <div class="progress-bar" style="width: ${s.progress}%"></div>
                    </div>
                </td>
                <td>${s.created_at}</td>
                <td>${s.elapsed ? s.elapsed.toFixed(2) + 's' : '-'}</td>
            </tr>
        `).join('');
    }
}
