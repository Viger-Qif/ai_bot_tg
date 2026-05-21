const RoadmapModule = {
    init: function() {
        this.render();
    },

    escapeHtml: function(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    truncate: function(text, maxLen) {
        if (!text) return '';
        return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
    },

    // ═══════════════════════════════════════════════════════════════
    // ГЛАВНЫЙ РЕНДЕР
    // ═══════════════════════════════════════════════════════════════

    render: function() {
        const container = document.getElementById('roadmapContainer');
        if (!container) return;

        const state = window.appState;
        const graph = state ? state.graph : null;

        if (!graph || !graph.nodes || graph.nodes.length === 0) {
            container.innerHTML = '<div class="roadmap-empty">' +
                '<div style="font-size:64px;margin-bottom:16px;animation:float 3s ease-in-out infinite;">🗺️</div>' +
                '<h3>Маршрут ещё не построен</h3>' +
                '<p>Перейди в Чат и расскажи, чему хочешь учиться</p>' +
                '</div>';
            return;
        }

        const completedNodes = state.completed_nodes || [];
        const currentNodeId = state.current_node_id;
        const total = graph.nodes.length;
        const completed = completedNodes.length;
        const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
        const points = state.points || 0;
        const level = state.level || {name: 'Новичок', icon: '🌱'};
        const streak = state.streak_days || 0;
        const badges = state.badges || [];
        const dailyQuests = state.daily_quests || [];

        const treeData = this.buildTreeLayout(graph);

        let html = '';

        // Шапка
        html += '<div class="roadmap-header">';
        html += '<div class="roadmap-title">' + this.escapeHtml(graph.graph_title || 'Твой маршрут') + '</div>';
        html += '<div class="roadmap-actions">';
        if (streak > 0) {
            html += '<div class="streak-display">🔥 ' + streak + '</div>';
        }
        html += '<div class="level-display">' + level.icon + ' ' + this.escapeHtml(level.name) + '</div>';
        html += '<div class="points-display">💎 <span id="userPoints">' + points + '</span></div>';
        html += '<button onclick="RoadmapModule.showBadges()" title="Бейджи">🏅 ' + badges.length + '</button>';
        html += '<button onclick="RoadmapModule.reset()" title="Сбросить">🗑️</button>';
        html += '</div></div>';

        // Прогресс
        html += '<div class="roadmap-progress">';
        html += '<div class="progress-text"><span>Прогресс</span><span>' + completed + ' / ' + total + ' (' + percentage + '%)</span></div>';
        html += '<div class="progress-bar"><div class="progress-fill" style="width:' + percentage + '%"></div></div>';
        html += '</div>';

        // Квесты
        if (dailyQuests.length > 0) {
            html += '<div class="daily-quests-panel">';
            html += '<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">📋 Ежедневные квесты:</div>';
            for (let i = 0; i < dailyQuests.length; i++) {
                const q = dailyQuests[i];
                html += '<div class="quest-item ' + (q.completed ? 'completed' : '') + '">';
                html += '<span>' + (q.completed ? '✅' : '⬜') + '</span>';
                html += '<span style="flex:1;">' + this.escapeHtml(q.title) + '</span>';
                html += '<span style="color:var(--gold);">+' + q.points + '</span>';
                html += '</div>';
            }
            html += '</div>';
        }

        // Подсказка
        html += '<div class="roadmap-hint">💡 Управляй графом через чат: "добавь блок про X", "удали Y", "перестрой план"</div>';

        // Дерево
        html += '<div class="tree-viewport">';
        html += '<div class="tree-container" style="height:' + treeData.height + 'px;">';
        html += '<svg class="tree-lines" width="' + treeData.width + '" height="' + treeData.height + '">';
        html += '<defs>';
        html += '<linearGradient id="coreGradient" x1="0%" y1="0%" x2="100%" y2="100%">';
        html += '<stop offset="0%" style="stop-color:#6366f1"/>';
        html += '<stop offset="100%" style="stop-color:#8b5cf6"/>';
        html += '</linearGradient>';
        html += '<linearGradient id="branchGradient" x1="0%" y1="0%" x2="100%" y2="100%">';
        html += '<stop offset="0%" style="stop-color:#475569"/>';
        html += '<stop offset="100%" style="stop-color:#64748b"/>';
        html += '</linearGradient>';
        html += '</defs>';
        html += this.renderLines(treeData, graph);
        html += '</svg>';
        html += this.renderNodes(treeData, completedNodes, currentNodeId);
        html += '</div></div>';

        container.innerHTML = html;
    },

    // ═══════════════════════════════════════════════════════════════
    // ПОСТРОЕНИЕ РАСКЛАДКИ
    // ═══════════════════════════════════════════════════════════════

    buildTreeLayout: function(graph) {
        const nodes = graph.nodes || [];
        const corePath = graph.core_path || [];
        const branches = graph.branches || [];

        if (nodes.length === 0) {
            return {nodes: [], height: 400, width: 480};
        }

        // Вычисление глубины
        const depths = {};
        const nodeMap = {};
        for (let i = 0; i < nodes.length; i++) {
            nodeMap[nodes[i].node_id] = nodes[i];
        }

        const computeDepth = function(nodeId, visited) {
            visited = visited || new Set();
            if (visited.has(nodeId)) return 0;
            visited.add(nodeId);
            if (depths[nodeId] !== undefined) return depths[nodeId];

            const node = nodeMap[nodeId];
            if (!node || !node.dependencies || node.dependencies.length === 0) {
                depths[nodeId] = 0;
                return 0;
            }

            let maxDep = 0;
            for (let j = 0; j < node.dependencies.length; j++) {
                const d = computeDepth(String(node.dependencies[j]), visited);
                if (d > maxDep) maxDep = d;
            }
            depths[nodeId] = maxDep + 1;
            return depths[nodeId];
        };

        for (let i = 0; i < nodes.length; i++) {
            computeDepth(String(nodes[i].node_id));
        }

        // Группировка по уровням
        const levels = {};
        for (let i = 0; i < nodes.length; i++) {
            const depth = depths[String(nodes[i].node_id)] || 0;
            if (!levels[depth]) levels[depth] = [];
            levels[depth].push(nodes[i]);
        }

        const levelKeys = Object.keys(levels).map(Number).sort(function(a, b) { return a - b; });
        const maxDepth = Math.max.apply(null, levelKeys);

        // Параметры
        const NODE_HEIGHT = 130;
        const LEVEL_GAP = 180;
        const NODE_WIDTH = 190;
        const VIEWPORT_WIDTH = 480;
        const PADDING_TOP = 80;
        const PADDING_BOTTOM = 60;
        const HORIZONTAL_VARIATION = 35;

        const positionedNodes = [];
        const totalHeight = PADDING_TOP + (maxDepth + 1) * LEVEL_GAP + PADDING_BOTTOM;

        // Псевдо-рандом для воспроизводимости
        let seed = 12345;
        const pseudoRandom = function() {
            seed = (seed * 1103515245 + 12345) & 0x7fffffff;
            return (seed / 0x7fffffff) * 2 - 1;
        };

        for (let li = 0; li < levelKeys.length; li++) {
            const depth = levelKeys[li];
            const levelNodes = levels[depth].slice();

            levelNodes.sort(function(a, b) {
                const aCore = corePath.indexOf(String(a.node_id)) !== -1 ? 0 : 1;
                const bCore = corePath.indexOf(String(b.node_id)) !== -1 ? 0 : 1;
                if (aCore !== bCore) return aCore - bCore;
                return String(a.node_id).localeCompare(String(b.node_id));
            });

            const count = levelNodes.length;
            const totalWidth = count * NODE_WIDTH + (count - 1) * 30;
            const startX = (VIEWPORT_WIDTH - totalWidth) / 2;
            const y = totalHeight - PADDING_BOTTOM - depth * LEVEL_GAP - NODE_HEIGHT / 2;

            for (let idx = 0; idx < count; idx++) {
                const node = levelNodes[idx];
                const isCore = corePath.indexOf(String(node.node_id)) !== -1;
                const isBranch = branches.indexOf(String(node.node_id)) !== -1 || !isCore;

                let x = startX + idx * (NODE_WIDTH + 30) + NODE_WIDTH / 2;

                if (isCore && count === 1) {
                    x += pseudoRandom() * HORIZONTAL_VARIATION;
                } else if (isBranch) {
                    const side = idx % 2 === 0 ? -1 : 1;
                    x += side * (HORIZONTAL_VARIATION + Math.abs(pseudoRandom()) * 20);
                } else {
                    x += pseudoRandom() * (HORIZONTAL_VARIATION * 0.6);
                }

                const minX = NODE_WIDTH / 2 + 15;
                const maxX = VIEWPORT_WIDTH - NODE_WIDTH / 2 - 15;
                if (x < minX) x = minX;
                if (x > maxX) x = maxX;

                positionedNodes.push({
                    node_id: node.node_id,
                    course_id: node.course_id,
                    title: node.title,
                    level: node.level,
                    is_core: node.is_core,
                    skills: node.skills,
                    dependencies: node.dependencies,
                    url: node.url,
                    description: node.description,
                    why_useful: node.why_useful,
                    x: x,
                    y: y,
                    depth: depth,
                    isCore: isCore,
                    isBranch: isBranch,
                    index: positionedNodes.length
                });
            }
        }

        return {nodes: positionedNodes, height: totalHeight, width: VIEWPORT_WIDTH};
    },

    // ═══════════════════════════════════════════════════════════════
    // ЛИНИИ
    // ═══════════════════════════════════════════════════════════════

    renderLines: function(treeData, graph) {
        const nodes = treeData.nodes;
        const nodeMap = {};
        for (let i = 0; i < nodes.length; i++) {
            nodeMap[String(nodes[i].node_id)] = nodes[i];
        }

        let lines = '';
        let lineIndex = 0;

        // Стартовые узлы (без зависимостей)
        for (let i = 0; i < nodes.length; i++) {
            const node = nodes[i];
            if (!node.dependencies || node.dependencies.length === 0) {
                const startX = node.x;
                const startY = treeData.height - 20;
                const endY = node.y + 40;

                lines += '<g class="line-group" style="animation: lineAppear 0.5s ease ' + (lineIndex * 0.15) + 's backwards;">';
                lines += '<line x1="' + startX + '" y1="' + startY + '" x2="' + startX + '" y2="' + endY + '" stroke="url(#coreGradient)" stroke-width="3" opacity="0.7" class="tree-line core-line"/>';
                lines += '<circle cx="' + startX + '" cy="' + startY + '" r="8" fill="#6366f1" class="start-point"><animate attributeName="r" values="8;10;8" dur="2s" repeatCount="indefinite"/></circle>';
                lines += '<text x="' + startX + '" y="' + (startY + 25) + '" text-anchor="middle" fill="#94a3b8" font-size="11" font-weight="500">СТАРТ</text>';
                lines += '</g>';
                lineIndex++;
            }
        }

        // Связи между узлами
        for (let i = 0; i < nodes.length; i++) {
            const node = nodes[i];
            const deps = node.dependencies || [];
            for (let j = 0; j < deps.length; j++) {
                const parent = nodeMap[String(deps[j])];
                if (!parent) continue;

                const x1 = parent.x;
                const y1 = parent.y - 40;
                const x2 = node.x;
                const y2 = node.y + 40;
                const midY = (y1 + y2) / 2;
                const isCoreLine = node.isCore && parent.isCore;
                const gradient = isCoreLine ? 'url(#coreGradient)' : 'url(#branchGradient)';
                const strokeWidth = isCoreLine ? 3 : 2;
                const dashArray = isCoreLine ? '' : '8,6';

                lines += '<path d="M ' + x1 + ' ' + y1 + ' C ' + x1 + ' ' + midY + ', ' + x2 + ' ' + midY + ', ' + x2 + ' ' + y2 + '" stroke="' + gradient + '" stroke-width="' + strokeWidth + '" fill="none" stroke-dasharray="' + dashArray + '" opacity="0.7" class="tree-line ' + (isCoreLine ? 'core-line' : 'branch-line') + '" style="animation: lineAppear 0.5s ease ' + (lineIndex * 0.15) + 's backwards;"/>';
                lineIndex++;
            }
        }

        return lines;
    },

    // ═══════════════════════════════════════════════════════════════
    // УЗЛЫ
    // ═══════════════════════════════════════════════════════════════

    renderNodes: function(treeData, completedNodes, currentNodeId) {
        let html = '';

        for (let i = 0; i < treeData.nodes.length; i++) {
            const node = treeData.nodes[i];
            const nodeId = String(node.node_id);
            const isCompleted = completedNodes.indexOf(nodeId) !== -1;
            const isCurrent = nodeId === String(currentNodeId);

            let badgeClass = node.isCore ? 'core' : 'branch';
            let badgeText = node.isCore ? '📍 ОСНОВА' : '🌿 ВЕТКА';
            if (isCompleted) {
                badgeClass = 'completed';
                badgeText = '✅';
            }

            const cardStyle = 'position:absolute;left:' + (node.x - 85) + 'px;top:' + (node.y - 50) + 'px;width:170px;z-index:10;cursor:pointer;animation: nodeAppear 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) ' + (i * 0.1 + 0.3) + 's backwards;';
            const cardClass = 'tree-node' + (isCompleted ? ' completed' : '') + (isCurrent ? ' current' : '');

            html += '<div class="' + cardClass + '" style="' + cardStyle + '" onclick="RoadmapModule.showNodeDetails(\'' + nodeId + '\')">';
            html += '<div class="tree-node-badge ' + badgeClass + '">' + badgeText + '</div>';
            html += '<div class="tree-node-title">' + this.escapeHtml(this.truncate(node.title || 'Без названия', 25)) + '</div>';

            if (node.skills && node.skills.length > 0) {
                html += '<div class="tree-node-skills">';
                const skillsToShow = node.skills.slice(0, 2);
                for (let s = 0; s < skillsToShow.length; s++) {
                    html += '<span>' + this.escapeHtml(this.truncate(skillsToShow[s], 10)) + '</span>';
                }
                html += '</div>';
            }

            if (isCurrent && !isCompleted) {
                html += '<div class="tree-node-actions">';
                html += '<button class="btn-mini" onclick="event.stopPropagation(); RoadmapModule.markNodeComplete(\'' + nodeId + '\')">✓</button>';
                html += '<button class="btn-mini" onclick="event.stopPropagation(); RoadmapModule.startTestForNode(\'' + nodeId + '\')">📝</button>';
                html += '</div>';
            }

            if (isCompleted) {
                html += '<div class="completed-overlay">✓</div>';
            }

            html += '</div>';
        }

        return html;
    },

    // ═══════════════════════════════════════════════════════════════
    // ВСПОМОГАТЕЛЬНЫЕ
    // ═══════════════════════════════════════════════════════════════

    _getAvailableNodes: function(graph, completedNodes) {
        if (!graph || !graph.nodes) return [];
        const completedSet = {};
        for (let i = 0; i < completedNodes.length; i++) {
            completedSet[String(completedNodes[i])] = true;
        }

        const available = [];
        for (let i = 0; i < graph.nodes.length; i++) {
            const n = graph.nodes[i];
            if (completedSet[String(n.node_id)]) continue;
            const deps = n.dependencies || [];
            let allDone = true;
            for (let j = 0; j < deps.length; j++) {
                if (!completedSet[String(deps[j])]) {
                    allDone = false;
                    break;
                }
            }
            if (allDone) available.push(n);
        }
        return available;
    },

    // ═══════════════════════════════════════════════════════════════
    // МОДАЛКА ДЕТАЛЕЙ УЗЛА
    // ═══════════════════════════════════════════════════════════════

    showNodeDetails: function(nodeId) {
        const state = window.appState;
        if (!state || !state.graph) return;

        let node = null;
        for (let i = 0; i < state.graph.nodes.length; i++) {
            if (String(state.graph.nodes[i].node_id) === String(nodeId)) {
                node = state.graph.nodes[i];
                break;
            }
        }
        if (!node) return;

        const completedNodes = state.completed_nodes || [];
        const currentNodeId = String(state.current_node_id || '');
        const isCompleted = completedNodes.indexOf(String(nodeId)) !== -1;
        const isCurrent = String(nodeId) === currentNodeId;
        const availableNodes = this._getAvailableNodes(state.graph, completedNodes);
        let isAvailable = false;
        for (let i = 0; i < availableNodes.length; i++) {
            if (String(availableNodes[i].node_id) === String(nodeId)) {
                isAvailable = true;
                break;
            }
        }

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';

        let html = '<div class="modal" style="max-width:500px;">';

        // Заголовок
        html += '<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:20px;">';
        html += '<div>';
        html += '<span class="tree-node-badge ' + (node.is_core ? 'core' : 'branch') + '" style="margin-bottom:10px;">';
        html += node.is_core ? '📍 ОСНОВА' : '🌿 ВЕТКА';
        html += '</span>';
        html += '<h3 style="margin:10px 0;font-size:20px;">' + this.escapeHtml(node.title) + '</h3>';
        html += '<div style="font-size:12px;color:var(--text-muted);">Уровень: ' + this.escapeHtml(node.level) + '</div>';
        html += '</div>';
        html += '<button onclick="RoadmapModule.closeModal()" style="background:none;border:none;color:var(--text-muted);font-size:28px;cursor:pointer;line-height:1;">&times;</button>';
        html += '</div>';

        // Описание
        if (node.description) {
            html += '<div style="background:var(--glass-bg);border-radius:12px;padding:14px;margin-bottom:14px;">';
            html += '<div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;">📖 Описание</div>';
            html += '<div style="font-size:14px;line-height:1.6;">' + this.escapeHtml(node.description) + '</div>';
            html += '</div>';
        }

        // Зачем нужно
        if (node.why_useful) {
            html += '<div style="background:linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15));border-radius:12px;padding:14px;margin-bottom:14px;">';
            html += '<div style="font-size:12px;color:var(--primary-light);margin-bottom:6px;">💡 Зачем это нужно</div>';
            html += '<div style="font-size:14px;line-height:1.6;">' + this.escapeHtml(node.why_useful) + '</div>';
            html += '</div>';
        }

        // Навыки
        if (node.skills && node.skills.length > 0) {
            html += '<div style="margin-bottom:16px;">';
            html += '<div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;">🎯 Навыки</div>';
            html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
            for (let s = 0; s < node.skills.length; s++) {
                html += '<span style="padding:6px 12px;background:var(--glass-bg);border:1px solid var(--glass-border);border-radius:12px;font-size:12px;">' + this.escapeHtml(node.skills[s]) + '</span>';
            }
            html += '</div></div>';
        }

        // Ссылка
        if (node.url) {
            html += '<a href="' + this.escapeHtml(node.url) + '" target="_blank" style="display:block;padding:14px;background:var(--gradient-primary);color:white;border-radius:12px;text-align:center;text-decoration:none;font-weight:600;margin-bottom:12px;box-shadow:0 4px 15px rgba(99,102,241,0.4);">🔗 Открыть материал</a>';
        }

        // Кнопки действий
        if (isCompleted) {
            html += '<div style="text-align:center;padding:14px;background:var(--gradient-success);color:white;border-radius:12px;font-weight:600;">✅ Этап пройден</div>';
        } else if (isAvailable || isCurrent) {
            html += '<div style="display:flex;gap:10px;">';
            html += '<button onclick="RoadmapModule.markNodeComplete(\'' + nodeId + '\'); RoadmapModule.closeModal();" style="flex:1;padding:14px;border-radius:12px;border:none;font-weight:600;cursor:pointer;background:var(--gradient-success);color:white;box-shadow:0 4px 15px rgba(16,185,129,0.4);">✓ Пройдено</button>';
            html += '<button onclick="RoadmapModule.startTestForNode(\'' + nodeId + '\'); RoadmapModule.closeModal();" style="flex:1;padding:14px;border-radius:12px;border:none;font-weight:600;cursor:pointer;background:var(--glass-bg);border:1px solid var(--glass-border);color:var(--text);">📝 Тест</button>';
            html += '</div>';
        } else {
            html += '<div style="text-align:center;padding:14px;background:var(--glass-bg);color:var(--text-muted);border-radius:12px;font-size:13px;">🔒 Пройди предыдущие этапы, чтобы открыть этот</div>';
        }

        html += '</div>';
        modal.innerHTML = html;
        document.body.appendChild(modal);

        const self = this;
        modal.onclick = function(e) {
            if (e.target === modal) self.closeModal();
        };
    },

    closeModal: function() {
        const modal = document.querySelector('.modal-overlay');
        if (modal) {
            modal.style.animation = 'fadeOut 0.2s ease';
            setTimeout(function() { modal.remove(); }, 200);
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // БЕЙДЖИ
    // ═══════════════════════════════════════════════════════════════

    showBadges: function() {
        const state = window.appState;
        if (!state) return;
        const allBadges = state.all_badges || [];
        const unlockedBadges = state.badges || [];

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';

        let html = '<div class="modal" style="max-width:500px;max-height:80vh;overflow-y:auto;">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">';
        html += '<h3 style="font-size:20px;">🏅 Бейджи (' + unlockedBadges.length + '/' + allBadges.length + ')</h3>';
        html += '<button onclick="RoadmapModule.closeModal()" style="background:none;border:none;color:var(--text-muted);font-size:28px;cursor:pointer;">&times;</button>';
        html += '</div>';
        html += '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">';

        for (let i = 0; i < allBadges.length; i++) {
            const b = allBadges[i];
            const unlocked = unlockedBadges.indexOf(b.id) !== -1;
            html += '<div class="badge-item ' + (unlocked ? 'unlocked' : 'locked') + '">';
            html += '<div style="font-size:32px;">' + b.icon + '</div>';
            html += '<div>';
            html += '<div style="font-size:13px;font-weight:600;">' + this.escapeHtml(b.title) + '</div>';
            html += '<div style="font-size:11px;color:var(--text-muted);">' + this.escapeHtml(b.description) + '</div>';
            html += '</div></div>';
        }

        html += '</div></div>';
        modal.innerHTML = html;
        document.body.appendChild(modal);

        const self = this;
        modal.onclick = function(e) {
            if (e.target === modal) self.closeModal();
        };
    },

    // ═══════════════════════════════════════════════════════════════
    // ДЕЙСТВИЯ
    // ═══════════════════════════════════════════════════════════════

    markComplete: async function() {
        const oldPoints = window.appState ? (window.appState.points || 0) : 0;
        const result = await App.markComplete();
        if (result) {
            if (result.rewards && result.rewards.length > 0) {
                App.showRewardsAnimation(result.rewards);
            }
            const newPoints = result.points || 0;
            const diff = newPoints - oldPoints;
            if (diff > 0) {
                setTimeout(function() { App.showPointsAnimation(diff); }, 500);
            }
            if (result.completed) {
                App.showToast('🏆 Маршрут пройден!', 'success');
            }
            this.render();
        }
    },

    markNodeComplete: async function(nodeId) {
        await App.selectNode(nodeId);
        await this.markComplete();
    },

    startTest: async function() {
        const test = await App.startTest();
        if (test && test.question) {
            this.showTestModal(test);
        } else {
            App.showToast('Теста нет — этап засчитан!', 'success');
            await this.markComplete();
        }
    },

    startTestForNode: async function(nodeId) {
        await App.selectNode(nodeId);
        await this.startTest();
    },

    // ═══════════════════════════════════════════════════════════════
    // ТЕСТ
    // ═══════════════════════════════════════════════════════════════

    showTestModal: function(test) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';

        let html = '<div class="modal" style="max-width:400px;">';
        html += '<h3 style="margin-bottom:18px;">📝 Проверка знаний</h3>';
        html += '<div style="font-size:16px;font-weight:600;margin-bottom:18px;line-height:1.5;">' + this.escapeHtml(test.question) + '</div>';
        html += '<textarea id="testAnswer" style="width:100%;padding:14px;background:rgba(15,23,42,0.6);border:1px solid var(--glass-border);border-radius:12px;color:var(--text);font-size:14px;margin-bottom:16px;resize:vertical;min-height:100px;" placeholder="Твой ответ..."></textarea>';
        html += '<div id="testFeedback" style="display:none;padding:14px;border-radius:12px;margin-bottom:16px;font-size:14px;"></div>';
        html += '<div style="display:flex;gap:12px;">';
        html += '<button onclick="RoadmapModule.submitTest()" style="flex:1;padding:14px;border-radius:12px;border:none;font-weight:600;cursor:pointer;background:var(--gradient-primary);color:white;box-shadow:0 4px 15px rgba(99,102,241,0.4);">Отправить</button>';
        html += '<button onclick="RoadmapModule.closeTestModal()" style="flex:1;padding:14px;border-radius:12px;border:none;font-weight:600;cursor:pointer;background:var(--glass-bg);border:1px solid var(--glass-border);color:var(--text);">Пропустить</button>';
        html += '</div></div>';

        modal.innerHTML = html;
        document.body.appendChild(modal);

        const self = this;
        modal.onclick = function(e) {
            if (e.target === modal) self.closeTestModal();
        };

        setTimeout(function() {
            const answerEl = document.getElementById('testAnswer');
            if (answerEl) answerEl.focus();
        }, 100);
    },

    submitTest: async function() {
        const answerEl = document.getElementById('testAnswer');
        const feedbackEl = document.getElementById('testFeedback');
        const answer = answerEl ? answerEl.value.trim() : '';

        if (!answer) {
            App.showToast('Введи ответ', 'error');
            return;
        }

        if (feedbackEl) {
            feedbackEl.style.display = 'block';
            feedbackEl.style.background = 'var(--glass-bg)';
            feedbackEl.style.color = 'var(--text-muted)';
            feedbackEl.textContent = '⚙️ Проверяю ответ...';
        }

        const oldPoints = window.appState ? (window.appState.points || 0) : 0;
        const result = await App.submitTest(answer);

        if (result && feedbackEl) {
            if (result.passed) {
                feedbackEl.style.background = 'linear-gradient(135deg, rgba(16,185,129,0.2), rgba(52,211,153,0.2))';
                feedbackEl.style.border = '1px solid var(--success)';
                feedbackEl.style.color = 'var(--success-light)';
                feedbackEl.textContent = '✅ ' + (result.feedback || 'Правильно!');

                const newPoints = result.points || 0;
                const diff = newPoints - oldPoints;
                if (diff > 0) {
                    setTimeout(function() { App.showPointsAnimation(diff); }, 500);
                }
                if (result.rewards && result.rewards.length > 0) {
                    App.showRewardsAnimation(result.rewards);
                }

                const self = this;
                setTimeout(function() {
                    self.closeTestModal();
                    self.render();
                }, 2000);
            } else {
                feedbackEl.style.background = 'linear-gradient(135deg, rgba(239,68,68,0.2), rgba(220,38,38,0.2))';
                feedbackEl.style.border = '1px solid var(--danger)';
                feedbackEl.style.color = '#fca5a5';
                feedbackEl.textContent = '❌ ' + (result.feedback || 'Попробуй ещё раз');
            }
        }
    },

    closeTestModal: function() {
        const modal = document.querySelector('.modal-overlay');
        if (modal) {
            modal.style.animation = 'fadeOut 0.2s ease';
            setTimeout(function() { modal.remove(); }, 200);
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // СБРОС
    // ═══════════════════════════════════════════════════════════════

    reset: async function() {
        if (!confirm('Сбросить весь прогресс и начать заново?')) return;
        await App.resetSession();
        App.navigate('chat');
    }
};

// ═══════════════════════════════════════════════════════════════
// АНИМАЦИИ
// ═══════════════════════════════════════════════════════════════

const roadmapStyle = document.createElement('style');
roadmapStyle.textContent = `
@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

@keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
}

@keyframes nodeAppear {
    0% { opacity: 0; transform: scale(0.5) translateY(30px); }
    60% { transform: scale(1.05) translateY(-5px); }
    100% { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes lineAppear {
    0% { opacity: 0; stroke-dashoffset: 200; }
    100% { opacity: 0.7; stroke-dashoffset: 0; }
}

.tree-line {
    stroke-dasharray: 200;
    stroke-dashoffset: 0;
    transition: opacity 0.3s ease;
}

.tree-line:hover {
    opacity: 1 !important;
    filter: drop-shadow(0 0 4px rgba(99, 102, 241, 0.5));
}

.start-point {
    filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.6));
}

.tree-node {
    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tree-node:hover {
    transform: translateY(-4px) scale(1.03) !important;
    z-index: 20 !important;
}

.tree-node.current {
    animation: pulseGlow 2s infinite;
}

@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3), 0 8px 25px rgba(99, 102, 241, 0.4); }
    50% { box-shadow: 0 0 0 6px rgba(99, 102, 241, 0.2), 0 8px 30px rgba(99, 102, 241, 0.5); }
}

.completed-overlay {
    position: absolute;
    top: -10px;
    right: -10px;
    width: 28px;
    height: 28px;
    background: var(--gradient-success);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    color: white;
    font-weight: bold;
    box-shadow: 0 4px 10px rgba(16, 185, 129, 0.4);
    animation: popIn 0.4s ease;
}

@keyframes popIn {
    0% { transform: scale(0); }
    50% { transform: scale(1.3); }
    100% { transform: scale(1); }
}

/* Квесты */
.daily-quests-panel {
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 16px;
}

.quest-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    background: var(--glass-bg);
    border-radius: 8px;
    margin-bottom: 6px;
    font-size: 13px;
}

.quest-item.completed {
    opacity: 0.5;
    text-decoration: line-through;
}

/* Бейджи */
.badge-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    transition: all 0.3s ease;
}

.badge-item.locked {
    opacity: 0.4;
    filter: grayscale(1);
}

.badge-item.unlocked {
    border-color: var(--gold);
    box-shadow: 0 0 15px rgba(251, 191, 36, 0.3);
}

/* Уровень и стрик */
.level-display {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: var(--glass-bg);
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.streak-display {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background: linear-gradient(135deg, #ef4444, #f59e0b);
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    color: white;
}
`;
document.head.appendChild(roadmapStyle);

window.RoadmapModule = RoadmapModule;