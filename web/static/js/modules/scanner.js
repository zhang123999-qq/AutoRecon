/**
 * 扫描器模块
 * 处理扫描相关的业务逻辑
 */

export class Scanner {
    constructor(options = {}) {
        this.onProgress = options.onProgress || (() => {});
        this.onLog = options.onLog || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || (() => {});
        
        this.currentScanId = null;
        this.scanCompleted = false;
        this.pollTimer = null;
    }

    /**
     * 获取选中的模块
     */
    getSelectedModules() {
        const modules = [];
        const mapping = {
            'mod-subdomain': 'subdomain',
            'mod-port': 'port',
            'mod-cdn': 'cdn',
            'mod-fingerprint': 'fingerprint',
            'mod-sensitive': 'sensitive',
            'mod-vuln': 'vuln',
            'mod-sqli': 'sqli'
        };
        
        for (const [id, mod] of Object.entries(mapping)) {
            const el = document.getElementById(id);
            if (el && el.checked) {
                modules.push(mod);
            }
        }
        
        return modules;
    }

    /**
     * 选择所有模块
     */
    selectAll() {
        document.querySelectorAll('[id^="mod-"]').forEach(el => el.checked = true);
    }

    /**
     * 清空选择
     */
    selectNone() {
        document.querySelectorAll('[id^="mod-"]').forEach(el => el.checked = false);
    }

    /**
     * 快速扫描预设
     */
    selectQuick() {
        this.selectNone();
        const quickModules = ['mod-subdomain', 'mod-cdn', 'mod-sensitive'];
        quickModules.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.checked = true;
        });
    }

    /**
     * 开始扫描
     */
    async start(target, threads) {
        const modules = this.getSelectedModules();
        
        if (!target) {
            throw new Error('请输入目标域名或IP');
        }
        
        if (modules.length === 0) {
            throw new Error('请至少选择一个扫描模块');
        }

        // 重置状态
        this.scanCompleted = false;
        this.currentScanId = null;

        // 发起扫描请求
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target, modules, threads })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || '创建扫描任务失败');
        }

        const data = await response.json();
        this.currentScanId = data.scan_id;

        return {
            scanId: data.scan_id,
            modules,
            status: 'created'
        };
    }

    /**
     * 取消扫描
     */
    async cancel() {
        if (!this.currentScanId) {
            return false;
        }

        try {
            const response = await fetch(`/api/scan/${this.currentScanId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.scanCompleted = true;
                this.stopPolling();
                return true;
            }
            return false;
        } catch (error) {
            console.error('取消扫描失败:', error);
            return false;
        }
    }

    /**
     * 获取扫描状态
     */
    async getStatus(scanId) {
        const response = await fetch(`/api/scan/${scanId}`);
        if (!response.ok) {
            throw new Error('获取扫描状态失败');
        }
        return await response.json();
    }

    /**
     * 开始轮询
     */
    startPolling(scanId, interval = 1000) {
        this.stopPolling();
        
        const poll = async () => {
            // 检查是否已完成
            if (this.scanCompleted || this.currentScanId !== scanId) {
                return;
            }

            try {
                const status = await this.getStatus(scanId);
                
                this.onProgress({
                    progress: status.progress,
                    module: status.current_module,
                    status: status.status
                });

                if (status.status === 'completed') {
                    this.scanCompleted = true;
                    this.currentScanId = null;
                    this.onComplete(status.results, status.elapsed);
                } else if (status.status === 'failed') {
                    this.scanCompleted = true;
                    this.currentScanId = null;
                    this.onError(status.error);
                } else if (status.status === 'running') {
                    this.pollTimer = setTimeout(poll, interval);
                }
            } catch (error) {
                this.onLog(`轮询错误: ${error.message}`, 'error');
                // 重试
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
        this.scanCompleted = false;
        this.currentScanId = null;
    }
}
