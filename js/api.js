const API = {
    OPENROUTER_URL: 'https://openrouter.ai/api/v1/chat/completions',
    BACKEND_URL: 'http://localhost:5000',

    API_KEYS: [
        '',
    ],

    _keyState: { currentIndex: 0, exhausted: [] },
    MODELS: { fast: 'poolside/laguna-xs.2:free', smart: 'openrouter/owl-alpha' },
    TIMEOUTS: { fast: 10000, smart: 25000 },

    _chatHistory: [],
    _profile: {},
    _graph: {},
    _completedNodes: [],
    _currentNodeId: null,
    _state: 'interview',
    _coursesDb: [],
    _testsDb: {},

    // ═══════════════════════════════════════════════════════════════
    // 🚀 ИНИЦИАЛИЗАЦИЯ
    // ═══════════════════════════════════════════════════════════════
    init: async function() {
        this.loadState();
        this.updateApiStatus();
        await this.loadDatabases();
    },

    // ═══════════════════════════════════════════════════════════════
    // 📚 ЗАГРУЗКА БАЗ ДАННЫХ
    // ═══════════════════════════════════════════════════════════════
    loadDatabases: async function() {
        try {
            const coursesResponse = await fetch(this.BACKEND_URL + '/api/courses');
            if (coursesResponse.ok) {
                this._coursesDb = await coursesResponse.json();
                console.log('✅ База курсов загружена: ' + this._coursesDb.length + ' записей');
            }

            const testsResponse = await fetch(this.BACKEND_URL + '/api/tests');
            if (testsResponse.ok) {
                this._testsDb = await testsResponse.json();
                console.log('✅ База тестов загружена: ' + Object.keys(this._testsDb).length + ' тем');
            }
        } catch (error) {
            console.warn('⚠️ Бэкенд недоступен:', error.message);
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔑 РОТАЦИЯ КЛЮЧЕЙ
    // ═══════════════════════════════════════════════════════════════
    getCurrentApiKey: function() {
        return this.API_KEYS[this._keyState.currentIndex];
    },

    rotateApiKey: function() {
        this._keyState.exhausted.push(this._keyState.currentIndex);
        for (let idx = 0; idx < this.API_KEYS.length; idx++) {
            if (this._keyState.exhausted.indexOf(idx) === -1) {
                this._keyState.currentIndex = idx;
                console.log('🔑 Переключение на API ключ #' + (idx + 1));
                return true;
            }
        }
        return false;
    },

    // ═══════════════════════════════════════════════════════════════
    // 💾 СОСТОЯНИЕ
    // ═══════════════════════════════════════════════════════════════
    saveState: function() {
        var state = {
            profile: this._profile,
            graph: this._graph,
            completedNodes: this._completedNodes,
            currentNodeId: this._currentNodeId,
            chatHistory: this._chatHistory.slice(-20),
            state: this._state
        };
        localStorage.setItem('progressor_state', JSON.stringify(state));
    },

    loadState: function() {
        var saved = localStorage.getItem('progressor_state');
        if (saved) {
            try {
                var state = JSON.parse(saved);
                this._profile = state.profile || {};
                this._graph = state.graph || {};
                this._completedNodes = state.completedNodes || [];
                this._currentNodeId = state.currentNodeId || null;
                this._chatHistory = state.chatHistory || [];
                this._state = state.state || 'interview';
            } catch (e) { console.error(e); }
        }
    },

    resetState: function() {
        this._profile = {};
        this._graph = {};
        this._completedNodes = [];
        this._currentNodeId = null;
        this._chatHistory = [];
        this._state = 'interview';
        this.saveState();
    },

    // ═══════════════════════════════════════════════════════════════
    // 😴 СОН
    // ═══════════════════════════════════════════════════════════════
    sleep: function(ms) {
        return new Promise(function(resolve) { setTimeout(resolve, ms); });
    },

    // ═══════════════════════════════════════════════════════════════
    // 🤖 ВЫЗОВ LLM
    // ═══════════════════════════════════════════════════════════════
    callLLM: async function(messages, mode, temperature, expectJson, retries) {
        mode = mode || 'fast';
        temperature = temperature || 0.2;
        expectJson = (expectJson !== undefined) ? expectJson : true;
        retries = retries || 2;

        var model = this.MODELS[mode] || this.MODELS.fast;
        var timeout = this.TIMEOUTS[mode] || 15000;

        var payload = {
            model: model,
            messages: messages,
            temperature: temperature
        };

        if (expectJson && mode === 'fast') {
            payload.response_format = { type: 'json_object' };
        }

        for (var attempt = 0; attempt < retries; attempt++) {
            try {
                var controller = new AbortController();
                var timeoutId = setTimeout(function() { controller.abort(); }, timeout);

                var self = this;
                var response = await fetch(this.OPENROUTER_URL, {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + this.getCurrentApiKey(),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (response.ok) {
                    var data = await response.json();
                    var choices = data.choices || [];
                    if (choices.length > 0 && choices[0].message) {
                        return (choices[0].message.content || '').trim();
                    }
                    return '';
                }

                if (response.status === 429) {
                    if (this.rotateApiKey()) {
                        await this.sleep(1000);
                        continue;
                    }
                    throw new Error('Все ключи исчерпаны');
                }

                if ([500, 502, 503, 504].indexOf(response.status) !== -1) {
                    await this.sleep(2000);
                    continue;
                }

                throw new Error('Ошибка API: ' + response.status);

            } catch (error) {
                if (attempt < retries - 1) {
                    await this.sleep(2000);
                    continue;
                }
                throw error;
            }
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // ⚡ БЫСТРЫЙ И УМНЫЙ ВЫЗОВЫ
    // ═══════════════════════════════════════════════════════════════
    askFast: async function(messages, temperature, expectJson) {
        temperature = temperature || 0.2;
        expectJson = (expectJson !== undefined) ? expectJson : true;
        return await this.callLLM(messages, 'fast', temperature, expectJson);
    },

    askSmart: async function(messages, temperature) {
        temperature = temperature || 0.3;
        return await this.callLLM(messages, 'smart', temperature, false);
    },

    // ═══════════════════════════════════════════════════════════════
    // 📦 ПАРСИНГ JSON
    // ═══════════════════════════════════════════════════════════════
    extractJson: function(content) {
        if (!content) return null;

        content = content.replace(/```json/g, '').replace(/```/g, '').trim();

        var match = content.match(/[\{\[][\s\S]*[\}\]]/);
        if (match) {
            content = match[0].trim();
        }

        try {
            return JSON.parse(content);
        } catch (e) {
            try {
                return JSON.parse(content.replace(/'/g, '"'));
            } catch (e2) {
                return null;
            }
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // 🚫 БЕЗОПАСНОСТЬ
    // ═══════════════════════════════════════════════════════════════
    BANNED_ROOTS: [],

    isInputSafe: function(text) {
        if (this.BANNED_ROOTS.length === 0) return true;
        var lower = (text || '').toLowerCase();
        for (var i = 0; i < this.BANNED_ROOTS.length; i++) {
            if (lower.indexOf(this.BANNED_ROOTS[i]) !== -1) return false;
        }
        return true;
    },

    // ═══════════════════════════════════════════════════════════════
    // 📊 УРОВНИ
    // ═══════════════════════════════════════════════════════════════
    LEVEL_MAPPING: {
        'beginner': 'новичок', 'начинающий': 'новичок',
        'intermediate': 'базовый', 'средний': 'базовый',
        'advanced': 'продвинутый', 'опытный': 'продвинутый',
        'unknown': 'любой'
    },

    normalizeLevel: function(raw) {
        if (!raw) return 'любой';
        var key = raw.toLowerCase().trim();
        return this.LEVEL_MAPPING[key] || 'любой';
    },

    getAllowedLevels: function(userLevel) {
        if (userLevel === 'новичок') return ['новичок', 'любой'];
        if (userLevel === 'базовый') return ['новичок', 'базовый', 'любой'];
        return ['новичок', 'базовый', 'продвинутый', 'любой'];
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔍 КЛАСТЕРЫ ТЕМ
    // ═══════════════════════════════════════════════════════════════
    TOPIC_CLUSTERS: {
        'python': ['python', 'питон', 'пайтон'],
        'javascript': ['javascript', 'js', 'джаваскрипт', 'фронтенд'],
        'java': ['java', 'джава'],
        'data science': ['data science', 'данные', 'pandas', 'ml'],
        'design': ['design', 'дизайн', 'figma', 'ui', 'ux'],
        'qa': ['qa', 'testing', 'тестирование']
    },

    getTopicSynonyms: function(topic) {
        var t = (topic || '').toLowerCase().trim();
        var keys = Object.keys(this.TOPIC_CLUSTERS);
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i];
            var syns = this.TOPIC_CLUSTERS[key];
            if (syns.indexOf(t) !== -1 || t === key || t.indexOf(key) !== -1 || key.indexOf(t) !== -1) {
                return syns.concat([key]);
            }
        }
        return [t];
    },

    filterCoursesByProfile: function(profile, max) {
        max = max || 40;
        if (!this._coursesDb.length) return [];
        var topic = (profile.target_topic || '').toLowerCase().trim();
        var syns = this.getTopicSynonyms(topic);
        var self = this;

        var filtered = this._coursesDb.filter(function(c) {
            var title = (c.title || '').toLowerCase();
            for (var i = 0; i < syns.length; i++) {
                if (title.indexOf(syns[i]) !== -1) return true;
            }
            return false;
        });

        filtered = filtered.filter(function(c) { return self.isInputSafe(c.title); });
        filtered = filtered.filter(function(c) { return (c.url || '').toLowerCase().indexOf('/promo') === -1; });

        var allowed = this.getAllowedLevels(profile.current_level || 'новичок');
        filtered = filtered.filter(function(c) { return allowed.indexOf(c.level || 'любой') !== -1; });

        return filtered.slice(0, max);
    },

    // ═══════════════════════════════════════════════════════════════
    // 💬 ИНТЕРВЬЮЕР
    // ═══════════════════════════════════════════════════════════════
    INTERVIEWER_SYSTEM: 'ВНИМАНИЕ! Если тема образовательная (IT, дизайн, языки, кулинария), выясни ТЕМУ и УРОВЕНЬ.\n\nФОРМАТЫ JSON:\nУточнение: {"status": "need_more", "message": "Текст вопроса?", "collected": {"target_topic": "Тема"}}\nГотово: {"status": "ready", "message": "Супер! Сейчас соберу план", "profile": {"target_topic": "Тема", "current_level": "новичок", "goal": "саморазвитие", "timeline": "не важно"}}\n\nОтвечай ТОЛЬКО JSON.',

    runInterviewStep: async function(userMessage) {
        if (!this.isInputSafe(userMessage)) {
            return { status: 'blocked', message: 'Тема нарушает правила безопасности.' };
        }

        this._chatHistory.push({ role: 'user', content: userMessage });
        if (this._chatHistory.length > 8) {
            this._chatHistory = this._chatHistory.slice(-8);
        }

        var messages = [{ role: 'system', content: this.INTERVIEWER_SYSTEM }].concat(this._chatHistory);

        try {
            var raw = await this.askFast(messages, 0.1, true);
            var result = this.extractJson(raw);

            if (!result) {
                return { status: 'error', message: 'Ошибка понимания. Перефразируй.' };
            }

            if (result.status === 'ready' && result.profile) {
                this._profile = result.profile;
                this._state = 'learning';
                this.saveState();
            }

            return result;
        } catch (e) {
            return { status: 'error', message: e.message };
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // 🗺️ ПОСТРОЕНИЕ РОАДМАПА
    // ═══════════════════════════════════════════════════════════════
    GRAPH_ARCHITECT_SYSTEM: 'Ты — архитектор образовательных графов. Создай ИДЕАЛЬНЫЙ РОАДМАП.\nПРАВИЛА: 1. Одна стартовая точка (node_id "1", dependencies: []). 2. core_path из 4-6 этапов. 3. Если мало курсов — придумай сам (course_id: "custom"). 4. Напиши roadmap_motivation.\nФОРМАТ JSON:\n{"graph_title": "Трек", "roadmap_motivation": "Объяснение", "nodes": [{"node_id": "1", "course_id": "ID", "title": "Название", "level": "новичок", "is_core": true, "skills": ["навык"], "dependencies": []}], "core_path": ["1"], "branches": []}',

    buildRoadmap: async function() {
        var filtered = this.filterCoursesByProfile(this._profile, 40);
        var coursesForLLM = filtered.slice(0, 20).map(function(c) {
            return { id: c.id, title: c.title, level: c.level };
        });

        var prompt = 'Профиль: Тема "' + this._profile.target_topic + '", Уровень "' + this._profile.current_level + '".\nКурсы: ' + JSON.stringify(coursesForLLM);
        var messages = [
            { role: 'system', content: this.GRAPH_ARCHITECT_SYSTEM },
            { role: 'user', content: prompt }
        ];

        try {
            var raw = await this.askSmart(messages, 0.2);
            var graph = this.extractJson(raw);

            if (graph && graph.nodes) {
                var self = this;
                graph.nodes.forEach(function(node) {
                    var dbCourse = null;
                    for (var i = 0; i < filtered.length; i++) {
                        if (String(filtered[i].id) === String(node.course_id)) {
                            dbCourse = filtered[i];
                            break;
                        }
                    }

                    if (dbCourse) {
                        node.url = dbCourse.url;
                        node.description = dbCourse.description || 'Этап обучения.';
                        node.why_useful = node.why_useful || 'Важный шаг.';
                    } else {
                        node.url = 'https://www.youtube.com/results?search_query=' + encodeURIComponent((node.title || '') + ' обучение');
                        node.description = '🤖 Сгенерированный этап.';
                        node.why_useful = node.why_useful || 'Обязательный навык.';
                    }
                });

                this._graph = graph;
                this._currentNodeId = this.getStartNodeId();
                this.saveState();
                return graph;
            }
            return null;
        } catch (e) {
            console.error(e);
            return null;
        }
    },

    getStartNodeId: function() {
        var nodes = this._graph.nodes || [];
        if (this._graph.core_path && this._graph.core_path.length > 0) {
            var start = this._graph.core_path[0];
            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].node_id === start) return start;
            }
        }
        for (var i = 0; i < nodes.length; i++) {
            if (!nodes[i].dependencies || nodes[i].dependencies.length === 0) {
                return nodes[i].node_id;
            }
        }
        return nodes.length > 0 ? nodes[0].node_id : null;
    },

    getCurrentCourse: function() {
        var nodes = this._graph.nodes || [];
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].node_id === this._currentNodeId) return nodes[i];
        }
        return null;
    },

    getAvailableNodes: function() {
        var nodes = this._graph.nodes || [];
        var completed = {};
        for (var i = 0; i < this._completedNodes.length; i++) {
            completed[String(this._completedNodes[i])] = true;
        }

        var available = [];
        for (var i = 0; i < nodes.length; i++) {
            var n = nodes[i];
            if (completed[String(n.node_id)]) continue;

            var deps = n.dependencies || [];
            var allDepsDone = true;
            for (var j = 0; j < deps.length; j++) {
                if (!completed[String(deps[j])]) {
                    allDepsDone = false;
                    break;
                }
            }
            if (allDepsDone) available.push(n);
        }

        available.sort(function(a, b) {
            if (a.is_core && !b.is_core) return -1;
            if (!a.is_core && b.is_core) return 1;
            return String(a.node_id).localeCompare(String(b.node_id));
        });

        return available;
    },

    markCurrentComplete: function() {
        var id = String(this._currentNodeId);
        if (id && this._completedNodes.indexOf(id) === -1) {
            this._completedNodes.push(id);
            this.saveState();
        }
    },

    goToNode: function(id) {
        this._currentNodeId = String(id);
        this._state = 'learning';
        this.saveState();
    },

    // ═══════════════════════════════════════════════════════════════
    // 📝 ПРОВЕРКА ТЕСТОВ
    // ═══════════════════════════════════════════════════════════════
    evaluateTestAnswer: async function(q, a, userAns) {
        var sys = 'Ты добрый учитель. Оцени ответ. Верни JSON: {"passed": true/false, "feedback": "комментарий"}';
        var prompt = 'ВОПРОС: ' + q + '\nЭТАЛОН: ' + a + '\nОТВЕТ: ' + userAns;
        var messages = [
            { role: 'system', content: sys },
            { role: 'user', content: prompt }
        ];

        try {
            var raw = await this.callLLM(messages, 'smart', 0.1, true);
            var res = this.extractJson(raw);
            if (res && 'passed' in res) return res;
            return { passed: false, feedback: 'Попробуй ещё раз.' };
        } catch (e) {
            return { passed: false, feedback: 'Ошибка проверки.' };
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // 💬 ЧАТ С МЕНТОРОМ
    // ═══════════════════════════════════════════════════════════════
    chatWithMentor: async function(msg) {
        if (!this.isInputSafe(msg)) return 'Я не буду это обсуждать.';

        var curr = this.getCurrentCourse();
        var title = curr ? curr.title : 'обучение';
        var sys = 'Ты ИИ-ментор Прогрессор. Ученик проходит "' + title + '". Отвечай коротко (2-3 предложения). Мотивируй учиться по ссылке этапа.';

        this._chatHistory.push({ role: 'user', content: msg });
        if (this._chatHistory.length > 8) {
            this._chatHistory = this._chatHistory.slice(-8);
        }

        var messages = [{ role: 'system', content: sys }].concat(this._chatHistory);

        try {
            var res = await this.askFast(messages, 0.3, false);
            this._chatHistory.push({ role: 'assistant', content: res });
            this.saveState();
            return res || 'Давай вернемся к материалу!';
        } catch (e) {
            return 'Произошла ошибка. Попробуй ещё раз.';
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // 📈 ПРОГРЕСС
    // ═══════════════════════════════════════════════════════════════
    getProgress: function() {
        var total = (this._graph.nodes || []).length;
        var done = this._completedNodes.length;
        return {
            total: total,
            completed: done,
            percentage: total > 0 ? Math.round((done / total) * 100) : 0
        };
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔧 СТАТУС
    // ═══════════════════════════════════════════════════════════════
    hasApiKey: function() {
        return this.API_KEYS.length > 0;
    },

    updateApiStatus: function() {
        var el = document.getElementById('apiStatus');
        if (el) {
            el.textContent = '✓ Ключ #' + (this._keyState.currentIndex + 1);
            el.classList.add('active');
        }
    }
};

window.API = API;