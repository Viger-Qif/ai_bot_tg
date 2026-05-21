"""
🚀 ПРОГРЕССОР — Backend v2.0
Полная версия с графом, тестами, очками и управлением через чат
"""

import os
import sys
import json
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

from functools import wraps
from datetime import date, datetime
import time
from services.analytics import analytics

# Добавляем backend в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import UserSession, ChatMessage, UserProfile
from services.llm_service import LLMService
from services.interview_service import InterviewService
from services.roadmap_service import RoadmapService
from services.test_service import TestService
from services.leaderboard_service import LeaderboardService

leaderboard_service = LeaderboardService()

from services.gamification import (
    POINTS, BADGES, update_streak, check_new_badges,
    get_daily_quests, complete_daily_quest, get_level, get_next_level
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ═══════════════════════════════════════════════════════════════
# ФАЙЛОВОЕ ХРАНИЛИЩЕ СЕССИЙ
# ═══════════════════════════════════════════════════════════════

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), 'sessions')
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ СЕРВИСОВ
# ═══════════════════════════════════════════════════════════════

llm_service = LLMService()
interview_service = InterviewService(llm_service)

# Загрузка баз данных
courses_df = None
tests_db = {}

request_timestamps = {}

def rate_limit(max_requests=5, window=10):
    """Декоратор для ограничения запросов"""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            session_id = request.headers.get('X-Session-Id', 'anonymous')
            endpoint = request.endpoint

            key = f"{session_id}:{endpoint}"
            now = time.time()

            if key not in request_timestamps:
                request_timestamps[key] = []

            # Удаляем старые запросы
            request_timestamps[key] = [t for t in request_timestamps[key] if now - t < window]

            if len(request_timestamps[key]) >= max_requests:
                return jsonify({'error': 'Слишком много запросов. Подожди немного.'}), 429

            request_timestamps[key].append(now)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def load_databases():
    global courses_df, tests_db

    # Курсы
    try:
        courses_path = os.path.join(os.path.dirname(__file__), 'cleaned_courses.csv')
        if os.path.exists(courses_path):
            courses_df = pd.read_csv(courses_path)
            courses_df.columns = courses_df.columns.str.lower().str.strip()
            print(f"✅ База курсов: {len(courses_df)} записей")
        else:
            print(f"⚠️ Файл курсов не найден: {courses_path}")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки курсов: {e}")

    # Тесты
    try:
        tests_path = os.path.join(os.path.dirname(__file__), 'hh_super_puper_update(1).csv')
        if os.path.exists(tests_path):
            df = pd.read_csv(tests_path, on_bad_lines='skip')
            df.columns = df.columns.str.lower().str.strip()

            if 'topic' in df.columns and 'question' in df.columns and 'answer' in df.columns:
                for _, row in df.iterrows():
                    topic = str(row['topic']).strip()
                    if topic:
                        if topic not in tests_db:
                            tests_db[topic] = []
                        tests_db[topic].append({
                            'question': str(row['question']).strip(),
                            'correct_answer': str(row['answer']).strip()
                        })
                print(f"✅ База тестов: {len(tests_db)} тем, {sum(len(v) for v in tests_db.values())} вопросов")
            else:
                print(f"⚠️ Неверный формат файла тестов. Колонки: {list(df.columns)}")
        else:
            print(f"⚠️ Файл тестов не найден: {tests_path}")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки тестов: {e}")


load_databases()

roadmap_service = RoadmapService(llm_service, courses_df)
test_service = TestService(llm_service, tests_db)


# ═══════════════════════════════════════════════════════════════
# УПРАВЛЕНИЕ СЕССИЯМИ
# ═══════════════════════════════════════════════════════════════

def get_session() -> UserSession:
    session_id = request.headers.get('X-Session-Id')
    if not session_id:
        session_id = 'anon_' + str(time.time())

    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")

    if os.path.exists(session_file):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return UserSession.from_dict(data)
        except Exception as e:
            print(f"⚠️ Ошибка чтения сессии: {e}")

    print(f"🆕 Новая сессия: {session_id[:20]}...")
    user_session = UserSession(session_id=session_id)
    save_session(user_session)
    return user_session


def save_session(user_session: UserSession):
    user_session.updated_at = time.time()
    session_file = os.path.join(SESSIONS_DIR, f"{user_session.session_id}.json")
    try:
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(user_session.to_dict(), f, ensure_ascii=False, indent=2)

        # 🔥 Синхронизация с лидербордом
        if user_session.points > 0:
            try:
                leaderboard_service.update_score(
                    session_id=user_session.session_id,
                    username=user_session.profile.target_topic or 'Аноним',
                    points=user_session.points,
                    topic=user_session.profile.target_topic,
                    badges_count=len(user_session.badges),
                    streak_days=user_session.streak_days
                )
            except Exception as e:
                print(f"⚠️ Ошибка обновления лидерборда: {e}")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения сессии: {e}")

# ═══════════════════════════════════════════════════════════════
# API ЭНДПОИНТЫ
# ═══════════════════════════════════════════════════════════════

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'courses_count': len(courses_df) if courses_df is not None else 0,
        'tests_count': sum(len(v) for v in tests_db.values()),
        'topics_count': len(tests_db)
    })


@app.route('/api/session', methods=['GET'])
def get_session_info():
    user_session = get_session()

    # 🔧 Обновляем стрик БЕЗ начисления очков (только проверка)
    today = date.today().isoformat()
    if user_session.last_activity_date != today:
        # Только обновляем дату, очки начисляются при реальных действиях
        user_session.last_activity_date = today
        save_session(user_session)

    data = user_session.to_dict()
    data['level'] = get_level(user_session.points)
    data['next_level'] = get_next_level(user_session.points)
    data['daily_quests'] = get_daily_quests(user_session)

    # Безопасные бейджи (без lambda)
    safe_badges = []
    for b in BADGES.values():
        safe_badges.append({
            'id': b['id'],
            'title': b['title'],
            'description': b['description'],
            'icon': b['icon']
        })
    data['all_badges'] = safe_badges

    return jsonify(data)


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Нет данных'}), 400

    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Пустое сообщение'}), 400

    user_session = get_session()
    analytics.log(user_session.session_id, 'chat_message', {'len': len(user_message), 'state': user_session.state})

    # ═══ ИНТЕРВЬЮ ═══
    if user_session.state == 'interview':
        result = interview_service.process_message(user_message, user_session.chat_history)
        user_session.chat_history.append(ChatMessage(role='user', content=user_message))

        if result.get('status') == 'blocked':
            user_session.chat_history.append(ChatMessage(role='system', content=result['message']))
            save_session(user_session)
            return jsonify({'type': 'system', 'content': result['message']})

        if result.get('status') == 'need_more':
            user_session.chat_history.append(ChatMessage(role='assistant', content=result['message']))
            save_session(user_session)
            return jsonify({'type': 'assistant', 'content': result['message']})

        if result.get('status') == 'ready':
            profile_data = result.get('profile', {})
            user_session.profile = UserProfile(
                target_topic=profile_data.get('target_topic', ''),
                current_level=profile_data.get('current_level', 'новичок'),
                goal=profile_data.get('goal', 'саморазвитие'),
                timeline=profile_data.get('timeline', 'не важно')
            )

            print(f"🚀 Строю граф для: {user_session.profile.target_topic}")
            graph = roadmap_service.build_graph(user_session.profile)

            if graph and graph.nodes:
                user_session.graph = graph
                user_session.current_node_id = roadmap_service.get_start_node_id(graph)
                user_session.state = 'learning'

                current_node = next((n for n in graph.nodes if n.node_id == user_session.current_node_id), None)
                course_title = current_node.title if current_node else 'обучение'

                motivation = graph.roadmap_motivation or ''
                welcome_msg = f"🗺️ План готов! Твой первый шаг: **{course_title}**.\n\n"
                if motivation:
                    welcome_msg += f"🧠 {motivation}\n\n"
                welcome_msg += "Перейди на вкладку **Маршрут** чтобы увидеть карту!\n\n💡 Можешь влиять на план: напиши 'добавь блок про X' или 'удали Y'."

                user_session.chat_history.append(ChatMessage(role='assistant', content=welcome_msg))
                save_session(user_session)
                print(f"✅ Граф построен: {len(graph.nodes)} узлов")

                return jsonify({
                    'type': 'assistant',
                    'content': welcome_msg,
                    'roadmap_built': True,
                    'motivation': motivation
                })
            else:
                user_session.chat_history.append(
                    ChatMessage(role='system', content='❌ Не удалось построить план. Попробуй уточнить тему.'))
                save_session(user_session)
                return jsonify({'type': 'system', 'content': '❌ Не удалось построить план.'})

        save_session(user_session)
        return jsonify({'type': 'system', 'content': 'Ошибка. Попробуй ещё раз.'})

    # ═══ ОБУЧЕНИЕ ═══
    elif user_session.state in ('learning', 'testing', 'choosing'):
        user_message_lower = user_message.lower()

        # Команды управления графом
        if any(cmd in user_message_lower for cmd in ['добавь', 'добавить', 'add', 'вставь', 'включи']):
            return handle_graph_modification(user_session, user_message, 'add')

        if any(cmd in user_message_lower for cmd in ['удали', 'убери', 'delete', 'remove', 'исключи']):
            return handle_graph_modification(user_session, user_message, 'remove')

        if any(cmd in user_message_lower for cmd in ['перестрой', 'пересобери', 'rebuild', 'заново']):
            return handle_rebuild(user_session, user_message)

        # Обычный чат с ментором
        user_session.chat_history.append(ChatMessage(role='user', content=user_message))
        if len(user_session.chat_history) > 10:
            user_session.chat_history = user_session.chat_history[-10:]

        current_course = next((n for n in user_session.graph.nodes if n.node_id == user_session.current_node_id), None)
        course_title = current_course.title if current_course else 'обучение'

        mentor_system = f"""Ты — ИИ-ментор Прогрессор. Ученик проходит этап: "{course_title}".

        ⛔ КРИТИЧЕСКИЕ ЗАПРЕТЫ:
        1. НЕ ПРИДУМЫВАЙ новые вкладки, функции, календари, практики — их не существует!
        2. НЕ пиши код, рецепты, инструкции
        3. НЕ обещай того, чего не можешь сделать

        ✅ РЕАЛЬНЫЕ ВОЗМОЖНОСТИ (знай о них):
        - Ученик может написать "добавь блок про X" — и граф обновится
        - Ученик может написать "удали Y" — и блок исчезнет
        - Ученик может написать "перестрой план" — и граф пересоберётся
        - Ученик может пройти тест (кнопка 📝) или отметить этап пройденным (кнопка ✓)
        - За прохождение этапов начисляются прокоины (очки)

        ✅ ТВОЯ ЗАДАЧА:
        - Отвечай КОРОТКО (1-2 предложения)
        - Мотивируй ученика перейти по ссылке этапа
        - Если просят изменить план — скажи: "Напиши 'добавь блок про [тему]' или 'перестрой план'"
        - Если спрашивают по теме — направь к материалу этапа

        Тон: дружелюбный, краткий, честный."""

        messages = [{'role': 'system', 'content': mentor_system}]
        for msg in user_session.chat_history:
            if msg.role != 'system':
                messages.append({'role': msg.role, 'content': msg.content})

        response = llm_service.ask_fast(messages, temperature=0.3, expect_json=False)
        response = response or 'Давай вернемся к материалу! Перейди по ссылке этапа 👆'

        user_session.chat_history.append(ChatMessage(role='assistant', content=response))
        save_session(user_session)
        analytics.log(user_session.session_id, 'node_completed', {'node_id': user_session.current_node_id})

        return jsonify({'type': 'assistant', 'content': response})

    return jsonify({'error': 'Неизвестное состояние'}), 400


reviews_db = {}  # {node_id: [reviews]}


@app.route('/api/reviews/<node_id>', methods=['GET'])
def get_reviews(node_id):
    return jsonify({'reviews': reviews_db.get(node_id, [])})


@app.route('/api/reviews/<node_id>', methods=['POST'])
def post_review(node_id):
    data = request.get_json()
    text = (data.get('text') or '').strip()
    rating = int(data.get('rating', 5))

    if not text or len(text) < 10:
        return jsonify({'error': 'Отзыв слишком короткий (мин. 10 символов)'}), 400

    if node_id not in reviews_db:
        reviews_db[node_id] = []

    review = {
        'text': text[:500],
        'rating': max(1, min(5, rating)),
        'timestamp': time.time()
    }
    reviews_db[node_id].append(review)

    # Награда за отзыв
    user_session = get_session()
    if len(text) > 50:
        user_session.points += 15
        save_session(user_session)
        return jsonify({'ok': True, 'bonus': 15, 'points': user_session.points})

    return jsonify({'ok': True})


@app.route('/api/daily-plan', methods=['GET'])
def get_daily_plan():
    """ИИ генерирует персональный план на день"""
    user_session = get_session()

    if not user_session.graph.nodes:
        return jsonify({'error': 'Роадмап не построен'}), 404

    current_node = next(
        (n for n in user_session.graph.nodes if n.node_id == user_session.current_node_id),
        None
    )

    if not current_node:
        return jsonify({'tasks': []})

    # Генерируем через LLM
    prompt = f"""Составь короткий персональный план на сегодня для ученика.
Текущий этап: {current_node.title}
Уровень: {user_session.profile.current_level}

Верни JSON с 3 задачами:
{{"tasks": [
  {{"title": "короткое название", "description": "что делать", "points": 10}},
  {{"title": "...", "description": "...", "points": 20}},
  {{"title": "...", "description": "...", "points": 30}}
]}}"""

    messages = [{'role': 'system', 'content': 'Ты — ИИ-ментор.'}, {'role': 'user', 'content': prompt}]
    raw = llm_service.ask_fast(messages, temperature=0.5)
    result = llm_service._extract_json(raw)

    if result and 'tasks' in result:
        return jsonify({'tasks': result['tasks'][:3]})

    # Fallback
    return jsonify({'tasks': [
        {'title': 'Изучи материал этапа', 'description': f'Открой "{current_node.title}" и прочитай', 'points': 20},
        {'title': 'Сделай заметки', 'description': 'Запиши 3 главных инсайта', 'points': 15},
        {'title': 'Пройди тест', 'description': 'Проверь свои знания', 'points': 30}
    ]})



def handle_graph_modification(user_session: UserSession, user_message: str, action: str):
    """Обработка команд изменения графа"""
    user_session.chat_history.append(ChatMessage(role='user', content=user_message))

    print(f"🔧 Модификация графа: {action}")

    new_graph = roadmap_service.modify_graph(user_session.graph, user_message, user_session.profile)

    if new_graph and new_graph.nodes:
        user_session.graph = new_graph
        user_session.chat_history.append(ChatMessage(
            role='assistant',
            content=f"✅ Граф обновлён! Теперь в нём {len(new_graph.nodes)} этапов. Перейди на вкладку **Маршрут**!"
        ))
        save_session(user_session)

        return jsonify({
            'type': 'assistant',
            'content': f"✅ Граф обновлён! Теперь {len(new_graph.nodes)} этапов.",
            'graph_modified': True
        })
    else:
        user_session.chat_history.append(ChatMessage(
            role='system',
            content='❌ Не удалось изменить граф. Попробуй сформулировать иначе.'
        ))
        save_session(user_session)
        return jsonify({'type': 'system', 'content': '❌ Не удалось изменить граф.'})


def handle_rebuild(user_session: UserSession, user_message: str):
    """Полная перестройка графа"""
    user_session.chat_history.append(ChatMessage(role='user', content=user_message))

    print(f"🔄 Перестройка графа")

    new_graph = roadmap_service.build_graph(user_session.profile)

    if new_graph and new_graph.nodes:
        user_session.graph = new_graph
        user_session.completed_nodes = []
        user_session.current_node_id = roadmap_service.get_start_node_id(new_graph)
        user_session.chat_history.append(ChatMessage(
            role='assistant',
            content=f"🔄 Граф перестроен! Новый план из {len(new_graph.nodes)} этапов готов."
        ))
        save_session(user_session)

        return jsonify({
            'type': 'assistant',
            'content': f"🔄 Граф перестроен! {len(new_graph.nodes)} этапов готово.",
            'graph_modified': True
        })
    else:
        return jsonify({'type': 'system', 'content': '❌ Не удалось перестроить граф.'})


@app.route('/api/roadmap', methods=['GET'])
def get_roadmap():
    user_session = get_session()

    if not user_session.graph.nodes:
        return jsonify({'error': 'Роадмап не построен'}), 404

    available = roadmap_service.get_available_nodes(user_session.graph, user_session.completed_nodes)
    total = len(user_session.graph.nodes)
    completed = len(user_session.completed_nodes)

    return jsonify({
        'graph': user_session.graph.to_dict(),
        'current_node_id': user_session.current_node_id,
        'completed_nodes': user_session.completed_nodes,
        'available_nodes': [n.to_dict() for n in available],
        'progress': {
            'total': total,
            'completed': completed,
            'percentage': round((completed / total) * 100) if total > 0 else 0
        },
        'points': user_session.points
    })


@app.route('/api/roadmap/next', methods=['POST'])
def mark_complete_and_next():
    user_session = get_session()

    if not user_session.current_node_id:
        return jsonify({'error': 'Нет текущего узла'}), 400

    rewards = []

    if user_session.current_node_id not in user_session.completed_nodes:
        user_session.completed_nodes.append(user_session.current_node_id)
        user_session.points += POINTS['complete_node']
        rewards.append(f"+{POINTS['complete_node']} за этап")

        # Бонус за первый курс
        if len(user_session.completed_nodes) == 1:
            user_session.points += POINTS['first_course']
            rewards.append(f"+{POINTS['first_course']} за первый курс!")

        # Ежедневный квест
        quest_bonus = complete_daily_quest(user_session, 'complete_node')
        if quest_bonus > 0:
            user_session.points += quest_bonus
            rewards.append(f"+{quest_bonus} за квест")

    # Проверяем бейджи
    new_badges = check_new_badges(user_session)
    for badge in new_badges:
        rewards.append(f"🏅 Бейдж: {badge['title']}")

    available = roadmap_service.get_available_nodes(user_session.graph, user_session.completed_nodes)
    save_session(user_session)

    response = {
        'points': user_session.points,
        'rewards': rewards,
        'level': get_level(user_session.points),
        'badges': user_session.badges
    }

    if not available:
        response['message'] = '🏆 Маршрут пройден!'
        response['completed'] = True
        return jsonify(response)

    if len(available) == 1:
        user_session.current_node_id = available[0].node_id
        save_session(user_session)
        response['next_node'] = available[0].to_dict()

    return jsonify(response)


@app.route('/api/roadmap/select/<node_id>', methods=['POST'])
def select_node(node_id):
    user_session = get_session()

    available = roadmap_service.get_available_nodes(user_session.graph, user_session.completed_nodes)
    if not any(n.node_id == node_id for n in available):
        return jsonify({'error': 'Узел недоступен'}), 400

    user_session.current_node_id = node_id
    user_session.state = 'learning'
    save_session(user_session)

    return jsonify({'ok': True, 'points': user_session.points})


@app.route('/api/test', methods=['POST'])
def start_test():
    user_session = get_session()

    current = next((n for n in user_session.graph.nodes if n.node_id == user_session.current_node_id), None)
    if not current:
        return jsonify({'error': 'Нет текущего узла'}), 404

    # Ищем тест в базе
    test = test_service.get_test_for_course(current.course_id)

    # Если не нашли — ищем по теме
    if not test:
        test = test_service.find_test_by_topic(current.title)

    # Если всё равно нет — генерируем
    if not test:
        test = test_service.generate_dynamic_test(current.title)

    user_session.current_test = test
    save_session(user_session)

    return jsonify(test)


@app.route('/api/test/submit', methods=['POST'])
@rate_limit(max_requests=3, window=10)  # Максимум 3 запроса за 10 секунд
def submit_test():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Нет данных'}), 400

    user_answer = data.get('answer', '').strip()
    user_session = get_session()

    # 🔧 ЗАЩИТА: Проверяем что тест активен
    if not user_session.current_test:
        return jsonify({'error': 'Тест уже пройден или не начат', 'passed': False}), 400

    # 🔧 ЗАЩИТА: Проверяем что узел ещё не пройден
    if user_session.current_node_id in user_session.completed_nodes:
        user_session.current_test = None
        save_session(user_session)
        return jsonify({'error': 'Этот этап уже пройден', 'passed': False}), 400

    test = user_session.current_test

    # 🔧 СРАЗУ обнуляем тест чтобы нельзя было отправить повторно
    user_session.current_test = None
    save_session(user_session)

    # Проверяем ответ
    result = test_service.evaluate_answer(test['question'], test['correct_answer'], user_answer)

    rewards = []

    if result.get('passed'):
        # Начисляем очки за этап
        if user_session.current_node_id not in user_session.completed_nodes:
            user_session.completed_nodes.append(user_session.current_node_id)
            user_session.points += POINTS['complete_node']
            rewards.append(f"+{POINTS['complete_node']} за этап")

        # 🔧 Начисляем очки за тест ТОЛЬКО если он ещё не был сдан
        if user_session.current_node_id not in user_session.completed_tests:
            user_session.completed_tests.append(user_session.current_node_id)
            user_session.points += POINTS['pass_test']
            rewards.append(f"+{POINTS['pass_test']} за тест")

            # Ежедневный квест
            quest_bonus = complete_daily_quest(user_session, 'pass_test')
            if quest_bonus > 0:
                user_session.points += quest_bonus
                rewards.append(f"+{quest_bonus} за квест")

    # Проверяем бейджи
    new_badges = check_new_badges(user_session)
    for badge in new_badges:
        rewards.append(f"🏅 {badge['title']}")

    # Переход к следующему узлу
    available = roadmap_service.get_available_nodes(user_session.graph, user_session.completed_nodes)
    if result.get('passed') and available and len(available) == 1:
        user_session.current_node_id = available[0].node_id

    save_session(user_session)
    result['points'] = user_session.points
    result['rewards'] = rewards
    result['level'] = get_level(user_session.points)

    return jsonify(result)


@app.route('/api/reset', methods=['POST'])
def reset_session():
    session_id = request.headers.get('X-Session-Id')
    if session_id:
        session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(session_file):
            os.remove(session_file)
    return jsonify({'message': 'Сброшено'})


# ═══════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ПРОГРЕССОР — Backend v2.0")
    print("=" * 60)
    print(f"📁 Сессии: {SESSIONS_DIR}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)