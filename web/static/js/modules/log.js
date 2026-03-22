/**
 * 日志模块
 * 管理扫描日志显示
 */

export class LogManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.maxLines = 100;
    }

    /**
     * 添加日志
     */
    add(message, type = 'info') {
        // 清除初始提示
        if (this.container.querySelector('.text-center')) {
            this.container.innerHTML = '';
        }

        const time = new Date().toLocaleTimeString();
        const line = document.createElement('div');
        line.className = `log-line log-${type}`;
        line.innerHTML = `<span class="text-secondary">[${time}]</span> ${message}`;

        this.container.appendChild(line);
        
        // 限制最大行数
        while (this.container.children.length > this.maxLines) {
            this.container.removeChild(this.container.firstChild);
        }

        // 滚动到底部
        this.container.scrollTop = this.container.scrollHeight;
    }

    /**
     * 清空日志
     */
    clear() {
        this.container.innerHTML = '<div class="text-secondary text-center py-4">等待扫描开始...</div>';
    }

    /**
     * 获取日志内容
     */
    getText() {
        return Array.from(this.container.querySelectorAll('.log-line'))
            .map(el => el.textContent)
            .join('\n');
    }
}
