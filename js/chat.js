const ChatModule = {
    _isLoading: false,

    init: function() {
        console.log('💬 ChatModule.init()');
        this.renderMessages();
        this.setupInput();
    },

    renderMessages: function() {
        var container = document.getElementById('chatMessages');
        if (!container) {
            console.error('❌ chatMessages не найден');
            return;
        }

        container.innerHTML = '';
        var history = window.appState ? (window.appState.chat_history || []) : [];

        if (history.length === 0) {
            this._addMsg(container, 'assistant', '👋 Привет! Я Прогрессор — твой AI-навигатор обучения.\n\nРасскажи, чему ты хочешь научиться?');
        } else {
            for (var i = 0; i < history.length; i++) {
                var msg = history[i];
                if (msg.role === 'system' && msg.content && msg.content.indexOf('Подбираю курсы') !== -1) {
                    continue;
                }
                this._addMsg(container, msg.role, msg.content);
            }
        }
        this._scrollBottom(container);
    },

    _addMsg: function(container, role, content) {
        var el = document.createElement('div');
        el.className = 'message ' + role;
        el.textContent = content;
        container.appendChild(el);
    },

    _scrollBottom: function(container) {
        setTimeout(function() {
            container.scrollTop = container.scrollHeight;
        }, 100);
    },

    setupInput: function() {
        var self = this;
        var input = document.getElementById('chatInput');
        var sendBtn = document.getElementById('chatSendBtn');

        if (!input || !sendBtn) {
            console.error('❌ chatInput или chatSendBtn не найден');
            return;
        }

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                self.sendMessage();
            }
        });

        sendBtn.addEventListener('click', function() {
            self.sendMessage();
        });
    },

    sendMessage: async function() {
        if (this._isLoading) return;

        var input = document.getElementById('chatInput');
        var sendBtn = document.getElementById('chatSendBtn');
        var container = document.getElementById('chatMessages');
        var message = input.value.trim();

        if (!message) return;

        this._isLoading = true;
        input.value = '';
        sendBtn.disabled = true;

        this._addMsg(container, 'user', message);
        this._scrollBottom(container);

        var loader = document.createElement('div');
        loader.className = 'message assistant';
        loader.textContent = '⏳ Думаю...';
        container.appendChild(loader);
        this._scrollBottom(container);

        try {
            var result = await App.sendMessage(message);
            if (loader.parentNode) container.removeChild(loader);
            await App.syncState();

            if (result.type === 'assistant') {
                this._addMsg(container, 'assistant', result.content);
                if (result.roadmap_built) {
                    this._addMsg(container, 'system', '✅ Роадмап построен! Перейди на вкладку "Маршрут" 🗺️');
                }
            } else if (result.type === 'system') {
                this._addMsg(container, 'system', result.content);
            }
        } catch (error) {
            if (loader.parentNode) container.removeChild(loader);
            this._addMsg(container, 'system', '❌ Ошибка соединения');
        } finally {
            this._isLoading = false;
            sendBtn.disabled = false;
            input.focus();
            this._scrollBottom(container);
        }
    }
};

window.ChatModule = ChatModule;