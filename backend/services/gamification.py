"""
Система геймификации: прокоины, бейджи, стрики, квесты
"""

from datetime import date  # ← Оставили только date, datetime убрали
from typing import Dict, List, Tuple
from models import UserSession

# ═══════════════════════════════════════════════════════════════
# ПРОКОИНЫ ЗА ДЕЙСТВИЯ
# ═══════════════════════════════════════════════════════════════

POINTS = {
    'complete_node': 50,  # Пройти этап
    'pass_test': 100,  # Сдать тест
    'pass_test_first_try': 50,  # Бонус за первую попытку
    'daily_login': 10,  # Ежедневный вход
    'streak_3_days': 30,  # 3 дня подряд
    'streak_7_days': 100,  # 7 дней подряд
    'streak_30_days': 500,  # 30 дней подряд
    'graph_modify': 20,  # Изменить граф
    'chat_interaction': 5,  # Сообщение в чат
    'first_course': 200,  # Первый пройденный курс
    'badge_unlocked': 50,  # Разблокировка бейджа
}

# ═══════════════════════════════════════════════════════════════
# БЕЙДЖИ
# ═══════════════════════════════════════════════════════════════

BADGES = {
    'first_steps': {
        'id': 'first_steps',
        'title': '🎯 Первые шаги',
        'description': 'Пройди свой первый этап',
        'icon': '🎯',
        'condition': lambda s: len(s.completed_nodes) >= 1
    },
    'knowledge_seeker': {
        'id': 'knowledge_seeker',
        'title': '📚 Искатель знаний',
        'description': 'Пройди 5 этапов',
        'icon': '📚',
        'condition': lambda s: len(s.completed_nodes) >= 5
    },
    'test_master': {
        'id': 'test_master',
        'title': '📝 Мастер тестов',
        'description': 'Сдай 3 теста',
        'icon': '📝',
        'condition': lambda s: len(s.completed_tests) >= 3
    },
    'perfectionist': {
        'id': 'perfectionist',
        'title': '💎 Перфекционист',
        'description': 'Сдай 5 тестов с первой попытки',
        'icon': '💎',
        'condition': lambda s: len(s.completed_tests) >= 5
    },
    'dedicated': {
        'id': 'dedicated',
        'title': '🔥 Упорный',
        'description': 'Учись 3 дня подряд',
        'icon': '🔥',
        'condition': lambda s: s.streak_days >= 3
    },
    'marathon_runner': {
        'id': 'marathon_runner',
        'title': '🏃 Марафонец',
        'description': 'Учись 7 дней подряд',
        'icon': '🏃',
        'condition': lambda s: s.streak_days >= 7
    },
    'graph_architect': {
        'id': 'graph_architect',
        'title': '🏗️ Архитектор',
        'description': 'Измени свой план обучения',
        'icon': '🏗️',
        'condition': lambda s: False  # Выдаётся при modify_graph
    },
    'centurion': {
        'id': 'centurion',
        'title': '💯 Центурион',
        'description': 'Набери 100 прокоинов',
        'icon': '💯',
        'condition': lambda s: s.points >= 100
    },
    'thousand': {
        'id': 'thousand',
        'title': '🏆 Тысячник',
        'description': 'Набери 1000 прокоинов',
        'icon': '🏆',
        'condition': lambda s: s.points >= 1000
    },
}

# ═══════════════════════════════════════════════════════════════
# УРОВНИ
# ═══════════════════════════════════════════════════════════════

LEVELS = [
    {'name': 'Новичок', 'min_points': 0, 'icon': '🌱'},
    {'name': 'Ученик', 'min_points': 100, 'icon': '📖'},
    {'name': 'Исследователь', 'min_points': 300, 'icon': '🔍'},
    {'name': 'Знаток', 'min_points': 600, 'icon': '🎓'},
    {'name': 'Эксперт', 'min_points': 1000, 'icon': '⭐'},
    {'name': 'Мастер', 'min_points': 2000, 'icon': '👑'},
]


def get_level(points: int) -> Dict:
    """Определяет уровень по очкам"""
    current = LEVELS[0]
    for level in LEVELS:
        if points >= level['min_points']:
            current = level
        else:
            break
    return current


def get_next_level(points: int) -> Dict:
    """Следующий уровень"""
    for level in LEVELS:
        if points < level['min_points']:
            return level
    return LEVELS[-1]


# ═══════════════════════════════════════════════════════════════
# СТРИКИ
# ═══════════════════════════════════════════════════════════════

def update_streak(session: UserSession) -> Tuple[int, int]:
    """
    Обновляет стрик. Возвращает (новый_стрик, бонусные_прокоины)
    """
    today = date.today().isoformat()
    bonus = 0

    if session.last_activity_date == today:
        return session.streak_days, 0

    if session.last_activity_date:
        try:
            from datetime import timedelta
            yesterday = (date.today() - timedelta(days=1)).isoformat()
        except Exception:
            yesterday = None

        if session.last_activity_date == yesterday:
            session.streak_days += 1
            bonus = POINTS['daily_login']

            if session.streak_days == 3:
                bonus += POINTS['streak_3_days']
            elif session.streak_days == 7:
                bonus += POINTS['streak_7_days']
            elif session.streak_days == 30:
                bonus += POINTS['streak_30_days']
        else:
            session.streak_days = 1
            bonus = POINTS['daily_login']
    else:
        session.streak_days = 1
        bonus = POINTS['daily_login']

    session.last_activity_date = today
    return session.streak_days, bonus  # ← bonus теперь возвращается

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА БЕЙДЖЕЙ
# ═══════════════════════════════════════════════════════════════

def check_new_badges(session: UserSession) -> List[Dict]:
    """Проверяет и выдаёт новые бейджи"""
    new_badges = []

    for badge_id, badge in BADGES.items():
        if badge_id not in session.badges:
            try:
                # Проверяем условие
                if badge['condition'](session):
                    session.badges.append(badge_id)
                    session.points += POINTS['badge_unlocked']
                    new_badges.append(badge)
                    print(f"🏅 Новый бейдж: {badge['title']}")
            except Exception as e:
                print(f"⚠️ Ошибка проверки бейджа {badge_id}: {e}")

    return new_badges


# ═══════════════════════════════════════════════════════════════
# ЕЖЕДНЕВНЫЕ КВЕСТЫ
# ═══════════════════════════════════════════════════════════════

DAILY_QUESTS = [
    {'id': 'daily_chat', 'title': '💬 Задай вопрос ментору', 'points': 10, 'action': 'chat'},
    {'id': 'daily_stage', 'title': '📚 Пройди этап', 'points': 30, 'action': 'complete_node'},
    {'id': 'daily_test', 'title': '📝 Сдай тест', 'points': 20, 'action': 'pass_test'},
]


def get_daily_quests(session: UserSession) -> List[Dict]:
    """Возвращает ежедневные квесты с прогрессом"""
    today = date.today().isoformat()

    # 🔧 Сбрасываем квесты если новый день
    if session.daily_quest_progress.get('date') != today:
        session.daily_quest_progress = {'date': today, 'completed': []}

    quests = []
    for q in DAILY_QUESTS:
        quests.append({
            'id': q['id'],
            'title': q['title'],
            'points': q['points'],
            'action': q['action'],
            'completed': q['id'] in session.daily_quest_progress.get('completed', [])
        })

    return quests


def complete_daily_quest(session: UserSession, action: str) -> int:
    """Отмечает квест как выполненный. Возвращает бонус"""
    today = date.today().isoformat()

    # 🔧 Инициализируем если новый день
    if session.daily_quest_progress.get('date') != today:
        session.daily_quest_progress = {'date': today, 'completed': []}

    for quest in DAILY_QUESTS:
        if quest['action'] == action and quest['id'] not in session.daily_quest_progress['completed']:
            session.daily_quest_progress['completed'].append(quest['id'])
            print(f"✅ Квест выполнен: {quest['title']} (+{quest['points']})")
            return quest['points']

    return 0