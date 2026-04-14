/**
 * WebSocket 管理模块
 * 处理实时通信和连接管理
 */

export class WebSocketManager {
    constructor(onMessage, onOpen, onClose, onError) {
        this.ws = null;
        this.onMessage = onMessage;
        this.onOpen = onOpen;
        this.onClose = onClose;
        this.onError = onError;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
    }

    /**
     * 连接 WebSocket
     */
    connect(scanId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/${scanId}`;
        
        this.ws = new WebSocket(url);
        
        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            if (this.onOpen) this.onOpen();
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (this.onMessage) this.onMessage(data);
            } catch (e) {
                console.error('WebSocket 消息解析错误:', e);
            }
        };
        
        this.ws.onclose = () => {
            if (this.onClose) this.onClose();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket 错误:', error);
            if (this.onError) this.onError(error);
        };
    }

    /**
     * 发送消息
     */
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    /**
     * 关闭连接
     */
    close() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * 检查连接状态
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}
