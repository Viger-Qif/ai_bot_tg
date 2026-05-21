const App = {
    API_URL: 'http://localhost:5000/api',
    currentPage: 'chat',
    sessionId: null,
    _isNavigating: false,

    init: function() {
        this.sessionId = localStorage.getItem('progressor_session_id');
        if (!this.sessionId) {
            this.sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('progressor_session_id', this.sessionId);
        }
        console.log('🆔 Session ID:', this.sessionId);

        var self = this;
        this.syncState().then(function() {
            var hash = window.location.hash.slice(1) || 'chat';
            self.navigate(hash);
        });

        window.addEventListener('hashchange', function() {
            var page = window.location.hash.slice(1) || 'chat';
            self.navigate(page);
        });
    },

    escapeHtml: function(text) {
        if (!text) return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    apiFetch: async function(url, options, retries) {
        options = options || {};
        retries = retries || 3;
        var headers = {
            'Content-Type': 'application/json',
            'X-Session-Id': this.sessionId
        };

        for (var attempt = 0; attempt < retries; attempt++) {
            try {
                var response = await fetch(url, {
                    method: options.method || 'GET',
                    headers: headers,
                    body: options.body || null
                });

                if (response.ok) return response;

                if (response.status >= 500 && attempt < retries - 1) {
                    await new Promise(function(r) { setTimeout(r, 1000 * (attempt + 1)); });
                    continue;
                }

                return response;
            } catch (error) {
                if (attempt < retries - 1) {
                    await new Promise(function(r) { setTimeout(r, 1000 * (attempt + 1)); });
                    continue;
                }
                throw error;
            }
        }
    },

    syncState: async function() {
        try {
            var response = await this.apiFetch(this.API_URL + '/session');
            if (response.ok) {
                var oldPoints = window.appState ? (window.appState.points || 0) : 0;
                window.appState = await response.json();
                var newPoints = window.appState.points || 0;

                this.updatePointsDisplay();

                if (newPoints > oldPoints && oldPoints > 0) {
                    this.showPointsAnimation(newPoints - oldPoints);
                }
            }
        } catch (error) {
            console.warn('⚠️ Sync error:', error);
        }
    },

    updatePointsDisplay: function() {
        var points = window.appState ? (window.appState.points || 0) : 0;
        var roadmapPoints = document.getElementById('userPoints');
        if (roadmapPoints) roadmapPoints.textContent = points;
    },

    navigate: async function(page) {
        if (this._isNavigating) return;
        this._isNavigating = true;

        try {
            this.currentPage = page;
            window.location.hash = page;

            document.querySelectorAll('.nav-btn').forEach(function(btn) {
                btn.classList.toggle('active', btn.dataset.page === page);
            });

            await this.syncState();
            await this.loadPage(page);
        } finally {
            this._isNavigating = false;
        }
    },

    loadPage: async function(page) {
        var content = document.getElementById('appContent');
        if (!content) return;

        try {
            var response = await fetch('pages/' + page + '.html');
            if (response.ok) {
                content.innerHTML = await response.text();

                // 🔥 ВАЖНО: вызываем init модулей ПОСЛЕ вставки HTML
                var self = this;
                setTimeout(function() {
                    if (page === 'chat' && typeof ChatModule !== 'undefined') {
                        ChatModule.init();
                    } else if (page === 'roadmap' && typeof RoadmapModule !== 'undefined') {
                        RoadmapModule.init();
                    } else if (page === 'leaderboard' && typeof LeaderboardModule !== 'undefined') {
                        LeaderboardModule.init();
                    }
                }, 50);
            }
        } catch (error) {
            content.innerHTML = '<p class="error">Ошибка загрузки</p>';
        }
    },

    sendMessage: async function(message) {
        try {
            var response = await this.apiFetch(this.API_URL + '/chat', {
                method: 'POST',
                body: JSON.stringify({ message: message })
            });
            if (!response.ok) throw new Error('Ошибка');
            return await response.json();
        } catch (error) {
            return { type: 'system', content: '❌ Ошибка соединения' };
        }
    },

    markComplete: async function() {
        try {
            var response = await this.apiFetch(this.API_URL + '/roadmap/next', { method: 'POST' });
            await this.syncState();
            return response.ok ? await response.json() : null;
        } catch (e) { return null; }
    },

    selectNode: async function(nodeId) {
        try {
            var response = await this.apiFetch(this.API_URL + '/roadmap/select/' + nodeId, { method: 'POST' });
            await this.syncState();
            return response.ok ? await response.json() : null;
        } catch (e) { return null; }
    },

    startTest: async function() {
        try {
            var response = await this.apiFetch(this.API_URL + '/test', { method: 'POST' });
            return response.ok ? await response.json() : null;
        } catch (e) { return null; }
    },

    submitTest: async function(answer) {
        try {
            var response = await this.apiFetch(this.API_URL + '/test/submit', {
                method: 'POST',
                body: JSON.stringify({ answer: answer })
            });
            await this.syncState();
            return response.ok ? await response.json() : null;
        } catch (e) { return null; }
    },

    resetSession: async function() {
        try {
            await this.apiFetch(this.API_URL + '/reset', { method: 'POST' });
            localStorage.removeItem('progressor_session_id');
            this.sessionId = null;
            this.init();
        } catch (e) {}
    },

    showPointsAnimation: function(points) {
        var anim = document.createElement('div');
        anim.className = 'points-animation';
        anim.textContent = '+' + points + ' 💎';
        anim.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);font-size:36px;font-weight:800;color:#fbbf24;z-index:9999;animation:pointsPop 1.5s ease-out forwards;';
        document.body.appendChild(anim);
        setTimeout(function() { anim.remove(); }, 1500);
    },

    showRewardsAnimation: function(rewards) {
        if (!rewards || rewards.length === 0) return;
        var container = document.createElement('div');
        container.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:9999;display:flex;flex-direction:column;gap:10px;align-items:center;pointer-events:none;';

        rewards.forEach(function(reward, i) {
            var el = document.createElement('div');
            el.textContent = reward;
            el.style.cssText = 'padding:12px 24px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;border-radius:12px;font-size:16px;font-weight:700;box-shadow:0 8px 25px rgba(102,126,234,0.5);animation:rewardPop 0.5s ease ' + (i * 0.2) + 's backwards;';
            container.appendChild(el);
        });

        document.body.appendChild(container);
        setTimeout(function() { container.remove(); }, 2000 + rewards.length * 200);
    },

    showToast: function(message, type) {
        type = type || 'success';
        var toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);padding:14px 24px;background:' + (type === 'error' ? 'linear-gradient(135deg,#ef4444,#dc2626)' : 'linear-gradient(135deg,#10b981,#059669)') + ';color:white;border-radius:12px;font-size:14px;font-weight:600;z-index:2000;';
        document.body.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 3000);
    }
};

window.App = App;

// Стили для анимаций
var style = document.createElement('style');
style.textContent = '@keyframes pointsPop{0%{opacity:0;transform:translate(-50%,-50%) scale(0.5)}30%{opacity:1;transform:translate(-50%,-50%) scale(1.3)}60%{opacity:1;transform:translate(-50%,-70%) scale(1)}100%{opacity:0;transform:translate(-50%,-120%) scale(0.8)}} @keyframes rewardPop{0%{opacity:0;transform:scale(0.5) translateY(20px)}60%{transform:scale(1.1) translateY(-5px)}100%{opacity:1;transform:scale(1) translateY(0)}}';
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', function() { App.init(); });