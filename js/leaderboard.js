const LeaderboardModule = {
    init: function() {
        this.render();
    },

    async fetchLeaderboard() {
        try {
            const response = await App.apiFetch(`${App.API_URL}/leaderboard`);
            if (response.ok) return await response.json();
        } catch (e) {
            console.warn('Leaderboard fetch error:', e);
        }
        return { top: [], user_rank: null };
    },

    render: async function() {
        const container = document.getElementById('leaderboardContainer');
        if (!container) return;

        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">⏳ Загрузка рейтинга...</div>';

        const data = await this.fetchLeaderboard();
        const top = data.top || [];
        const userRank = data.user_rank;
        const userPoints = window.appState?.points || 0;

        if (top.length === 0) {
            container.innerHTML = `
                <div style="text-align:center;padding:60px 20px;">
                    <div style="font-size:64px;margin-bottom:16px;">🏆</div>
                    <h3>Рейтинг пока пуст</h3>
                    <p>Будь первым — пройди этапы и набери очки!</p>
                </div>
            `;
            return;
        }

        let html = `
            <div class="leaderboard-header">
                <h2>🏆 Рейтинг учеников</h2>
                <p>Топ ${top.length} самых активных</p>
            </div>
            <div class="user-stats">
                <div class="points" id="leaderboardPoints">${userPoints}</div>
                <div class="label">Твои очки • Место #${userRank || '—'}</div>
            </div>
            <div class="leaderboard-list">
        `;

        top.forEach((user, i) => {
            const rank = i + 1;
            const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : '';
            const rankEmoji = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;

            html += `
                <div class="leaderboard-item" style="animation-delay:${i * 0.05}s">
                    <div class="rank ${rankClass}">${rankEmoji}</div>
                    <div class="user-info">
                        <div class="user-name">${App.escapeHtml(user.name)} ${user.streak > 0 ? '🔥' + user.streak : ''}</div>
                        <div class="user-level">${App.escapeHtml(user.level || 'Ученик')} • ${user.badges || 0} 🏅</div>
                    </div>
                    <div class="user-points">${user.points} ✨</div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }
};

window.LeaderboardModule = LeaderboardModule;