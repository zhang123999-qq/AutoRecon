/**
 * UI 模块
 * 管理界面元素状态
 */

export class UIManager {
    constructor() {
        this.elements = {
            target: document.getElementById('target'),
            threads: document.getElementById('threads'),
            threadsValue: document.getElementById('threadsValue'),
            startBtn: document.getElementById('startBtn'),
            cancelBtn: document.getElementById('cancelBtn'),
            progressCard: document.getElementById('progressCard'),
            resultsCard: document.getElementById('resultsCard'),
            progressBar: document.getElementById('progressBar'),
            progressPercent: document.getElementById('progressPercent'),
            currentModule: document.getElementById('currentModule'),
            statusBadge: document.getElementById('statusBadge')
        };

        this.statusMap = {
            'pending': '等待中',
            'running': '运行中',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        };

        this._initEventListeners();
    }

    /**
     * 初始化事件监听
     */
    _initEventListeners() {
        // 并发数滑块
        if (this.elements.threads) {
            this.elements.threads.addEventListener('input', (e) => {
                if (this.elements.threadsValue) {
                    this.elements.threadsValue.textContent = e.target.value;
                }
            });
        }
    }

    /**
     * 获取目标
     */
    getTarget() {
        return this.elements.target?.value.trim() || '';
    }

    /**
     * 获取并发数
     */
    getThreads() {
        return parseInt(this.elements.threads?.value || 50);
    }

    /**
     * 设置目标
     */
    setTarget(value) {
        if (this.elements.target) {
            this.elements.target.value = value;
        }
    }

    /**
     * 显示进度卡片
     */
    showProgress() {
        if (this.elements.progressCard) {
            this.elements.progressCard.style.display = 'block';
        }
    }

    /**
     * 隐藏进度卡片
     */
    hideProgress() {
        if (this.elements.progressCard) {
            this.elements.progressCard.style.display = 'none';
        }
    }

    /**
     * 显示结果卡片
     */
    showResults() {
        if (this.elements.resultsCard) {
            this.elements.resultsCard.style.display = 'block';
        }
    }

    /**
     * 隐藏结果卡片
     */
    hideResults() {
        if (this.elements.resultsCard) {
            this.elements.resultsCard.style.display = 'none';
        }
    }

    /**
     * 更新进度
     */
    updateProgress(percent, module) {
        if (this.elements.progressBar) {
            this.elements.progressBar.style.width = percent + '%';
        }
        if (this.elements.progressPercent) {
            this.elements.progressPercent.textContent = percent + '%';
        }
        if (this.elements.currentModule) {
            this.elements.currentModule.textContent = module;
        }
    }

    /**
     * 更新状态
     */
    updateStatus(status) {
        if (this.elements.statusBadge) {
            this.elements.statusBadge.className = `status-badge status-${status}`;
            this.elements.statusBadge.textContent = this.statusMap[status] || status;
        }
    }

    /**
     * 禁用开始按钮
     */
    disableStart() {
        if (this.elements.startBtn) {
            this.elements.startBtn.disabled = true;
        }
        if (this.elements.cancelBtn) {
            this.elements.cancelBtn.style.display = 'inline-block';
        }
    }

    /**
     * 启用开始按钮
     */
    enableStart() {
        if (this.elements.startBtn) {
            this.elements.startBtn.disabled = false;
        }
        if (this.elements.cancelBtn) {
            this.elements.cancelBtn.style.display = 'none';
        }
    }

    /**
     * 切换到扫描标签页
     */
    switchToScanTab() {
        const tab = document.querySelector('[href="#scan"]');
        if (tab) {
            tab.click();
        }
    }
}
