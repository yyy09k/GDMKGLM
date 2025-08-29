class GDMChat {
    constructor() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.chatForm = document.getElementById('chatForm');
        this.statusText = document.querySelector('.status-text');
        
        this.init();
    }
    
    init() {
        // 绑定事件
        this.chatForm.addEventListener('submit', (e) => this.handleSubmit(e));
        this.messageInput.addEventListener('keydown', (e) => this.handleKeydown(e));
        this.messageInput.addEventListener('input', () => this.adjustTextareaHeight());
        
        // 检查系统状态
        this.checkSystemStatus();
        
        // 聚焦输入框
        this.messageInput.focus();
    }
    
    async checkSystemStatus() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            if (data.status === 'healthy') {
                this.statusText.textContent = '在线';
                this.statusText.style.color = '#10a37f';
            } else {
                this.statusText.textContent = '系统准备中';
                this.statusText.style.color = '#f39c12';
            }
        } catch (error) {
            this.statusText.textContent = '连接失败';
            this.statusText.style.color = '#e74c3c';
        }
    }
    
    handleKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendCurrentMessage();
        }
    }
    
    handleSubmit(e) {
        e.preventDefault();
        this.sendCurrentMessage();
    }
    
    sendCurrentMessage() {
        const message = this.messageInput.value.trim();
        if (message) {
            this.sendMessage(message);
        }
    }
    
    async sendMessage(message) {
        // 添加用户消息
        this.addMessage(message, 'user');
        
        // 清空输入框
        this.messageInput.value = '';
        this.adjustTextareaHeight();
        
        // 显示加载状态
        this.showTypingIndicator();
        this.setInputDisabled(true);
        
        try {
            const formData = new FormData();
            formData.append('query', message);
            
            const response = await fetch('/chat', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            // 移除加载状态
            this.hideTypingIndicator();
            
            if (data.success) {
                this.addMessage(data.answer, 'assistant', {
                    confidence: data.confidence,
                    responseTime: data.response_time,
                    timestamp: data.timestamp
                });
            } else {
                this.addMessage(data.answer || '抱歉，出现了一些问题，请重试。', 'assistant');
            }
            
        } catch (error) {
            console.error('发送消息失败:', error);
            this.hideTypingIndicator();
            this.addMessage('网络连接出现问题，请检查网络后重试。', 'assistant');
        } finally {
            this.setInputDisabled(false);
            this.messageInput.focus();
        }
    }
    
    addMessage(content, type, metadata = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
    
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = type === 'user' ? '👤' : '🤖';
    
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
    
        // 修改：使用 textContent 而不是 innerHTML，让 CSS 的 white-space: pre-wrap 处理换行
        contentDiv.textContent = content;
    
        // 添加元数据
        if (type === 'assistant' && metadata.confidence) {
            const metaDiv = document.createElement('div');
            metaDiv.className = 'message-meta';
            metaDiv.innerHTML = `
                <span>置信度: ${(metadata.confidence * 100).toFixed(1)}%</span>
                <span>耗时: ${metadata.responseTime}</span>
                <span>${metadata.timestamp}</span>
            `;
            contentDiv.appendChild(metaDiv);
        }
    
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
    
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    
    showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant-message typing-message';
        typingDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        this.messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const typingMessage = this.messagesContainer.querySelector('.typing-message');
        if (typingMessage) {
            typingMessage.remove();
        }
    }
    
    setInputDisabled(disabled) {
        this.messageInput.disabled = disabled;
        this.sendButton.disabled = disabled;
    }
    
    adjustTextareaHeight() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
}

// 全局函数
window.sendMessage = function(message) {
    if (window.gdmChat) {
        window.gdmChat.sendMessage(message);
    }
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    window.gdmChat = new GDMChat();
});
