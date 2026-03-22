/**
 * AutoRecon Web UI - 主应用
 * 整合所有模块
 */

import { WebSocketManager } from './modules/websocket.js';
import { Scanner } from './modules/scanner.js';
import { ReportManager } from './modules/reports.js';
import { HistoryManager } from './modules/history.js';
import { LogManager } from './modules/log.js';
import { UIManager } from './modules/ui.js';
import { StressTester, renderStressResults, renderAnalysis } from './modules/stress.js';

class App {
    constructor() {
        // 初始化模块
        this.ui = new UIManager();
        this.log = new LogManager('logContainer');
        this.scanner = new Scanner({
            onProgress: (data) => this.onProgress(data),
            onLog: (msg, type) => this.log.add(msg, type),
            onComplete: (results, elapsed) => this.onScanComplete(results, elapsed),
            onError: (error) => this.onScanError(error)
        });
        this.reports = new ReportManager({
            onViewReport: (filename) => this.viewReport(filename)
        });
        this.history = new HistoryManager();
        this.stressTester = new StressTester({
            onProgress: (data) => this.onStressProgress(data),
            onComplete: (results) => this.onStressComplete(results),
            onError: (error) => this.onStressError(error)
        });
        this.ws = null;

        // 初始化
        this.init();
    }

    /**
     * 初始化应用
     */
    init() {
        // 绑定全局函数（供 HTML onclick 使用）
        window.startScan = () => this.startScan();
        window.cancelScan = () => this.cancelScan();
        window.selectAll = () => this.scanner.selectAll();
        window.selectNone = () => this.scanner.selectNone();
        window.selectQuick = () => this.scanner.selectQuick();
        window.clearLog = () => this.log.clear();
        window.loadHistory = () => this.loadHistory();
        window.loadReports = () => this.loadReports();
        window.startStressTest = () => this.startStressTest();

        // 绑定标签页事件
        this.bindTabEvents();

        // 初始化压力测试滑块
        this.initStressSliders();

        console.log('AutoRecon Web UI 初始化完成');
    }

    /**
     * 绑定标签页切换事件
     */
    bindTabEvents() {
        const historyTab = document.querySelector('[href="#history"]');
        const reportsTab = document.querySelector('[href="#reports"]');

        if (historyTab) {
            historyTab.addEventListener('click', () => this.loadHistory());
        }
        if (reportsTab) {
            reportsTab.addEventListener('click', () => this.loadReports());
        }
    }

    /**
     * 开始扫描
     */
    async startScan() {
        const target = this.ui.getTarget();
        const threads = this.ui.getThreads();

        if (!target) {
            alert('请输入目标域名或IP');
            return;
        }

        try {
            // 准备 UI
            this.ui.showProgress();
            this.ui.hideResults();
            this.ui.updateStatus('running');
            this.log.clear();

            this.log.add(`开始扫描目标: ${target}`, 'info');
            
            // 开始扫描
            const result = await this.scanner.start(target, threads);
            
            this.log.add(`扫描任务已创建: ${result.scanId}`, 'success');
            this.log.add(`模块: ${result.modules.join(', ')}`, 'info');
            
            this.ui.disableStart();

            // 连接 WebSocket
            this.connectWebSocket(result.scanId);

        } catch (error) {
            this.log.add(`错误: ${error.message}`, 'error');
            this.ui.enableStart();
        }
    }

    /**
     * 连接 WebSocket
     */
    connectWebSocket(scanId) {
        this.ws = new WebSocketManager(
            // onMessage
            (data) => this.handleWebSocketMessage(data),
            // onOpen
            () => {},
            // onClose
            () => {
                // WebSocket 断开时启用轮询
                if (!this.scanner.scanCompleted && this.scanner.currentScanId) {
                    this.log.add('WebSocket 断开，启用轮询模式', 'warning');
                    this.scanner.startPolling(scanId);
                }
            },
            // onError
            () => {
                this.log.add('WebSocket 连接错误', 'error');
            }
        );

        this.ws.connect(scanId);
    }

    /**
     * 取消扫描
     */
    async cancelScan() {
        const cancelled = await this.scanner.cancel();
        if (cancelled) {
            this.log.add('扫描已取消', 'warning');
            this.ui.updateStatus('cancelled');
            this.ui.enableStart();
        }
    }

    /**
     * 处理 WebSocket 消息
     */
    handleWebSocketMessage(data) {
        if (data.type === 'progress') {
            this.ui.updateProgress(data.progress, data.module);
            this.log.add(`正在执行: ${data.module} (${data.progress}%)`, 'info');

        } else if (data.type === 'status') {
            if (data.status === 'completed') {
                this.onScanComplete(data.results, data.elapsed);
            } else if (data.status === 'running') {
                this.ui.updateStatus('running');
            } else if (data.status === 'failed') {
                this.onScanError(data.error);
            } else if (data.status === 'cancelled') {
                this.onScanCancelled();
            }
        }
    }

    /**
     * 进度更新回调
     */
    onProgress(data) {
        this.ui.updateProgress(data.progress, data.module);
        this.ui.updateStatus(data.status);
    }

    /**
     * 扫描完成回调
     */
    onScanComplete(results, elapsed) {
        this.scanner.scanCompleted = true;
        this.scanner.currentScanId = null;

        this.ui.updateProgress(100, '完成');
        this.ui.updateStatus('completed');
        this.log.add('扫描完成!', 'success');
        this.log.add(`耗时: ${elapsed.toFixed(2)} 秒`, 'info');

        this.reports.renderResults(results, 'resultsContainer');
        this.ui.showResults();
        this.ui.enableStart();
    }

    /**
     * 扫描错误回调
     */
    onScanError(error) {
        this.scanner.scanCompleted = true;
        this.scanner.currentScanId = null;

        this.ui.updateStatus('failed');
        this.log.add(`扫描失败: ${error}`, 'error');
        this.ui.enableStart();
    }

    /**
     * 扫描取消回调
     */
    onScanCancelled() {
        this.scanner.scanCompleted = true;
        this.scanner.currentScanId = null;

        this.ui.updateStatus('cancelled');
        this.log.add('扫描已取消', 'warning');
        this.ui.enableStart();
    }

    /**
     * 加载历史记录
     */
    async loadHistory() {
        try {
            const scans = await this.history.load();
            this.history.render(scans, 'historyTable');
        } catch (error) {
            console.error('加载历史失败:', error);
        }
    }

    /**
     * 加载报告列表
     */
    async loadReports() {
        try {
            const reports = await this.reports.loadList();
            this.reports.renderList(reports, 'reportsTable');
        } catch (error) {
            console.error('加载报告失败:', error);
        }
    }

    /**
     * 查看报告
     */
    async viewReport(filename) {
        try {
            const data = await this.reports.get(filename);
            this.ui.switchToScanTab();
            this.ui.setTarget(data.target || '');
            this.reports.renderResults(data, 'resultsContainer');
            this.ui.showResults();
        } catch (error) {
            alert('加载报告失败: ' + error.message);
        }
    }

    // ============ 压力测试功能 ============

    /**
     * 初始化压力测试滑块
     */
    initStressSliders() {
        // 并发数 - 输入框和滑块联动
        const concurrentInput = document.getElementById('stressConcurrentInput');
        const concurrentSlider = document.getElementById('stressConcurrent');
        
        if (concurrentInput && concurrentSlider) {
            // 输入框变化时更新滑块
            concurrentInput.addEventListener('input', (e) => {
                const val = Math.min(200, Math.max(1, parseInt(e.target.value) || 1));
                concurrentSlider.value = val;
            });
            
            // 滑块变化时更新输入框
            concurrentSlider.addEventListener('input', (e) => {
                concurrentInput.value = e.target.value;
            });
        }

        // 持续时间 - 输入框和滑块联动
        const durationInput = document.getElementById('stressDurationInput');
        const durationSlider = document.getElementById('stressDuration');
        
        if (durationInput && durationSlider) {
            durationInput.addEventListener('input', (e) => {
                const val = Math.min(120, Math.max(5, parseInt(e.target.value) || 10));
                durationSlider.value = val;
            });
            
            durationSlider.addEventListener('input', (e) => {
                durationInput.value = e.target.value;
            });
        }
    }

    /**
     * 开始压力测试
     */
    async startStressTest() {
        // 从输入框获取值（优先使用输入框，滑块作为备用）
        const url = document.getElementById('stressUrl')?.value.trim();
        const mode = document.getElementById('stressMode')?.value || 'quick';
        
        // 优先使用输入框的值
        const concurrentInput = document.getElementById('stressConcurrentInput');
        const concurrentSlider = document.getElementById('stressConcurrent');
        const concurrent = parseInt(concurrentInput?.value || concurrentSlider?.value || 10);
        
        const durationInput = document.getElementById('stressDurationInput');
        const durationSlider = document.getElementById('stressDuration');
        const duration = parseInt(durationInput?.value || durationSlider?.value || 10);
        
        const timeoutInput = document.getElementById('stressTimeoutInput');
        const timeout = parseInt(timeoutInput?.value || 30);

        if (!url) {
            alert('请输入目标 URL');
            return;
        }

        // 验证参数范围
        if (concurrent < 1 || concurrent > 500) {
            alert('并发数应在 1-500 之间');
            return;
        }
        
        if (duration < 1 || duration > 600) {
            alert('持续时间应在 1-600 秒之间');
            return;
        }

        // 禁用按钮
        const btn = document.getElementById('startStressBtn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 测试中...';
        }

        // 显示状态卡片
        document.getElementById('stressStatusCard').style.display = 'block';
        document.getElementById('stressResultsCard').style.display = 'none';
        document.getElementById('stressAnalysisCard').style.display = 'none';

        // 重置显示
        document.getElementById('stressQps').textContent = '...';
        document.getElementById('stressAvgTime').textContent = '...';
        document.getElementById('stressErrorRate').textContent = '...';
        document.getElementById('stressLevel').textContent = '-';

        try {
            // 快速测试直接返回结果
            if (mode === 'quick') {
                const results = await this.stressTester.quickTest(url, concurrent, duration);
                this.onStressComplete(results);
            } else {
                // 其他模式使用异步任务
                const result = await this.stressTester.start(url, mode, concurrent, duration);
                this.stressTester.startPolling(result.testId);
            }
        } catch (error) {
            alert('测试失败: ' + error.message);
            this.onStressError(error.message);
        }
    }

    /**
     * 压力测试进度回调
     */
    onStressProgress(data) {
        if (data.results && data.results.metrics) {
            const m = data.results.metrics;
            document.getElementById('stressQps').textContent = m.throughput?.qps?.toFixed(1) || '0';
            document.getElementById('stressAvgTime').textContent = m.response_time?.avg?.toFixed(0) || '0';
            document.getElementById('stressErrorRate').textContent = (m.errors?.error_rate || 0).toFixed(1) + '%';
            
            if (m.stress_level) {
                document.getElementById('stressLevel').textContent = m.stress_level;
            }
        }
    }

    /**
     * 压力测试完成回调
     */
    onStressComplete(results) {
        console.log('压力测试结果:', results);
        
        const metrics = results.metrics || results;
        
        // 更新实时状态
        const qpsEl = document.getElementById('stressQps');
        const avgTimeEl = document.getElementById('stressAvgTime');
        const errorRateEl = document.getElementById('stressErrorRate');
        const levelEl = document.getElementById('stressLevel');
        
        if (qpsEl) qpsEl.textContent = (metrics.throughput?.qps || 0).toFixed(1);
        if (avgTimeEl) avgTimeEl.textContent = (metrics.response_time?.avg || 0).toFixed(0);
        if (errorRateEl) errorRateEl.textContent = (metrics.errors?.error_rate || 0).toFixed(1) + '%';
        if (levelEl) levelEl.textContent = metrics.stress_level || '-';

        // 显示详细结果
        const resultsCard = document.getElementById('stressResultsCard');
        if (resultsCard) resultsCard.style.display = 'block';
        renderStressResults(results, 'stressResultsContainer');

        // 显示瓶颈分析
        if (results.analysis) {
            const analysisCard = document.getElementById('stressAnalysisCard');
            if (analysisCard) analysisCard.style.display = 'block';
            renderAnalysis(results.analysis, 'stressAnalysisContainer');
        }

        // 恢复按钮
        this.restoreStressButton();
    }

    /**
     * 压力测试错误回调
     */
    onStressError(error) {
        // 恢复按钮
        this.restoreStressButton();
    }

    /**
     * 恢复压力测试按钮状态
     */
    restoreStressButton() {
        const btn = document.getElementById('startStressBtn');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-play-fill"></i> 开始测试';
        }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
