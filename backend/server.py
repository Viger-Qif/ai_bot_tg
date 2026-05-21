"""
Backend сервер для Прогрессора
Загрузка и отдача баз данных курсов и тестов
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os
import json

app = Flask(__name__)
CORS(app)  # Разрешаем все origins

# ═══════════════════════════════════════════════════════════════
# 📁 ПУТИ К БАЗАМ ДАННЫХ
# ═══════════════════════════════════════════════════════════════

# Положи CSV файлы в папку backend/
COURSES_CSV = os.path.join(os.path.dirname(__file__), 'cleaned_courses.csv')
TESTS_CSV = os.path.join(os.path.dirname(__file__), 'hh_super_puper_update(1).csv')

# Кэш
_courses_cache = None
_tests_cache = None

# ═══════════════════════════════════════════════════════════════
# 📚 ЗАГРУЗКА КУРСОВ
# ═══════════════════════════════════════════════════════════════

LEVEL_MAPPING = {
    'beginner': 'новичок', 'начинающий': 'новичок',
    'intermediate': 'базовый', 'средний': 'базовый',
    'advanced': 'продвинутый', 'опытный': 'продвинутый',
    'unknown': 'любой'
}

def normalize_level(raw_level):
    if not raw_level or not isinstance(raw_level, str):
        return 'любой'
    return LEVEL_MAPPING.get(raw_level.lower().strip(), 'любой')

def load_courses():
    global _courses_cache
    if _courses_cache is not None:
        return _courses_cache

    if not os.path.exists(COURSES_CSV):
        print(f"⚠️ Файл курсов не найден: {COURSES_CSV}")
        return []

    try:
        df = pd.read_csv(COURSES_CSV)
        df.columns = df.columns.str.lower().str.strip()

        # Добавляем недостающие колонки
        required_cols = ['id', 'topic', 'title', 'url', 'level', 'description']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ''

        # Нормализация уровней
        df['level'] = df['level'].fillna('unknown').astype(str).apply(normalize_level)

        # Убираем дубликаты по URL
        df = df.drop_duplicates(subset=['url'], keep='first')
        df = df[df['url'] != ''].reset_index(drop=True)

        _courses_cache = df.to_dict('records')
        print(f"✅ База курсов загружена: {len(_courses_cache)} записей")
        return _courses_cache
    except Exception as e:
        print(f"❌ Ошибка загрузки курсов: {e}")
        return []

# ═══════════════════════════════════════════════════════════════
# 📝 ЗАГРУЗКА ТЕСТОВ
# ═══════════════════════════════════════════════════════════════

def load_tests():
    """
    Загружает базу тестов и группирует их по topic (теме).
    Реальные колонки в CSV: topic, level, question, answer
    """
    global _tests_cache
    if _tests_cache is not None:
        return _tests_cache

    if not os.path.exists(TESTS_CSV):
        print(f"⚠️ Файл тестов не найден: {TESTS_CSV}")
        return {}

    try:
        # Читаем с обработкой ошибок парсинга
        df = pd.read_csv(TESTS_CSV, on_bad_lines='skip')
        df.columns = df.columns.str.lower().str.strip()

        print(f"📋 Колонки в файле тестов: {list(df.columns)}")

        # Маппинг возможных названий колонок
        column_map = {
            'topic': ['topic', 'course_id', 'theme', 'subject'],
            'question': ['question', 'q', 'query'],
            'answer': ['answer', 'correct_answer', 'a', 'solution']
        }

        # Находим реальные названия колонок
        topic_col = None
        question_col = None
        answer_col = None

        for standard_name, possible_names in column_map.items():
            for name in possible_names:
                if name in df.columns:
                    if standard_name == 'topic':
                        topic_col = name
                    elif standard_name == 'question':
                        question_col = name
                    elif standard_name == 'answer':
                        answer_col = name
                    break

        if not all([topic_col, question_col, answer_col]):
            print(f"⚠️ Не найдены нужные колонки. Нужно: topic, question, answer")
            return {}

        print(f"✅ Используем колонки: topic='{topic_col}', question='{question_col}', answer='{answer_col}'")

        tests_dict = {}
        for _, row in df.iterrows():
            # Используем topic как ключ группировки
            topic = str(row.get(topic_col, '')).strip()
            if not topic:
                continue

            if topic not in tests_dict:
                tests_dict[topic] = []

            tests_dict[topic].append({
                'question': str(row.get(question_col, '')).strip(),
                'correct_answer': str(row.get(answer_col, '')).strip(),
                'level': str(row.get('level', 'любой')).strip()
            })

        _tests_cache = tests_dict
        total_tests = sum(len(v) for v in tests_dict.values())
        print(f"✅ База тестов загружена: {total_tests} вопросов для {len(tests_dict)} тем")
        return _tests_cache
    except Exception as e:
        print(f"❌ Ошибка загрузки тестов: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════
# 🌐 API ЭНДПОИНТЫ
# ═══════════════════════════════════════════════════════════════

@app.route('/api/courses', methods=['GET'])
def get_courses():
    """Получить список всех курсов"""
    courses = load_courses()

    # Опциональная фильтрация
    topic = request.args.get('topic', '')
    level = request.args.get('level', '')

    if topic:
        courses = [c for c in courses if topic.lower() in str(c.get('title', '')).lower()]
    if level:
        courses = [c for c in courses if c.get('level', '').lower() == level.lower()]

    return jsonify(courses)

@app.route('/api/tests', methods=['GET'])
def get_all_tests():
    """Получить все тесты"""
    tests = load_tests()
    return jsonify(tests)

@app.route('/api/tests/<course_id>', methods=['GET'])
def get_tests_for_course(course_id):
    """Получить тесты для конкретного курса"""
    tests = load_tests()
    course_tests = tests.get(str(course_id), [])
    return jsonify(course_tests)

@app.route('/api/health', methods=['GET'])
def health():
    """Проверка работоспособности"""
    courses = load_courses()
    tests = load_tests()
    return jsonify({
        'status': 'ok',
        'courses_count': len(courses),
        'tests_count': sum(len(v) for v in tests.values()),
        'tests_courses_count': len(tests)
    })

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# ═══════════════════════════════════════════════════════════════
# 🚀 ЗАПУСК
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ПРОГРЕССОР — Backend сервер")
    print("=" * 60)

    # Загружаем базы при старте
    load_courses()
    load_tests()

    print("=" * 60)
    print("📡 Сервер запущен на http://localhost:5000")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)