"""
Roadmap Service — полный pipeline:
1. Фильтрация базы по теме и уровню
2. Если мало курсов — поиск через DuckDuckGo
3. LLM-анализатор отбирает лучшие курсы
4. Построение графа с реальными URL
"""

import json
import urllib.parse
import re
from typing import Dict, List, Optional
import pandas as pd
from models import UserProfile, LearningGraph, RoadmapNode
from .llm_service import LLMService


class RoadmapService:

    # ═══════════════════════════════════════════════════════════════
    # КЛАСТЕРЫ ТЕМ
    # ═══════════════════════════════════════════════════════════════

    TOPIC_CLUSTERS = {
        'python': ['python', 'питон', 'пайтон', 'django', 'flask'],
        'javascript': ['javascript', 'js', 'джаваскрипт', 'фронтенд', 'frontend', 'react', 'vue'],
        'java': ['java', 'джава', 'spring'],
        'c#': ['c#', 'csharp', 'шарп', '.net'],
        'data science': ['data science', 'data', 'данные', 'pandas', 'machine learning', 'ml'],
        'design': ['design', 'дизайн', 'figma', 'ui', 'ux'],
        'qa': ['qa', 'testing', 'тестирование', 'автотесты', 'selenium'],
        'web': ['веб', 'сайт', 'сайты', 'web', 'fullstack', 'фулстек', 'html', 'css'],
        'devops': ['devops', 'девопс', 'docker', 'kubernetes', 'linux'],
        'mobile': ['мобильн', 'android', 'ios', 'flutter', 'swift', 'kotlin'],
        'кулинария': ['кулинария', 'повар', 'готовка', 'рецепт', 'кухн', 'блюд'],
        'английский': ['английский', 'english', 'англ', 'язык'],
        'фотография': ['фото', 'фотография', 'photography', 'камера'],
        'музыка': ['музыка', 'гитара', 'пианино', 'вокал'],
    }

    # Чёрный список агрегаторов и платных курсов
    AGGREGATOR_BLACKLIST = [
        'coursera.org', 'udemy.com', 'skillbox.ru', 'netology.ru', 'geekbrains.ru',
        'hexlet.io', 'praktikum.yandex.ru', 'stepik.org/catalog',
        'habr.com', 'proglib.io', 'tproger.ru', 'vc.ru'
    ]

    # Доверенные домены для поиска
    TRUSTED_DOMAINS = [
        'stepik.org', 'youtube.com', 'youtu.be', 'github.com',
        'developer.mozilla.org', 'learn.javascript.ru', 'metanit.com',
        'python.org', 'docs.python.org', 'w3schools.com'
    ]

    # ═══════════════════════════════════════════════════════════════
    # ПРОМПТЫ
    # ═══════════════════════════════════════════════════════════════

    ANALYZER_SYSTEM = """Ты — ИИ-методист. Твоя задача: из предоставленного списка курсов отобрать ЛУЧШИЕ для пользователя.
⛔ ЖЁСТКИЕ ПРАВИЛА ОТБОРА:
1. ТОЛЬКО курсы на РУССКОМ ЯЗЫКЕ! Отбрасывай всё на английском, французском и других языках.
2. Отбрасывай нерелевантные темы (Starbucks, налоги, магазины, новости).
3. Отбрасывай дубликаты и очень похожие курсы.
4. Курс должен быть ОБУЧАЮЩИМ материалом, а не просто статьёй или новостью.

ВЫБЕРИ ОТ 8 ДО 12 КУРСОВ для качественного образовательного трека:
- 5-7 курсов для ОСНОВНОГО пути (от новичка до продвинутого)
- 3-5 курсов для ДОПОЛНИТЕЛЬНЫХ веток (углубление)

КРИТЕРИИ:
1. Курсы должны выстраиваться ЛОГИЧНО: от базовых концепций к продвинутым
2. ИЗБЕГАЙ дубликатов
3. Выбирай курсы с понятными навыками
4. Для основного пути: "новичок" → "базовый" → "продвинутый"
5. Для веток — любые релевантные темы

Верни JSON:
{
  "selected": [
    {
      "id": "id_курса",
      "why_useful": "Почему нужен (1 предложение)",
      "skills": ["навык1", "навык2"],
      "is_core": true/false,
      "difficulty_order": 1-10
    }
  ]
}

ВАЖНО: id ДОЛЖЕН точно совпадать с id из списка"""

    GRAPH_ARCHITECT_SYSTEM = """Ты — архитектор образовательных графов. Создай ИДЕАЛЬНЫЙ РОАДМАП.

ПРАВИЛА:
1. ТОЛЬКО ОДНА стартовая точка (узел "1", dependencies: [])
2. Основной путь (core_path) — 4-6 этапов ПОСЛЕДОВАТЕЛЬНО
3. Ветки (branches) — 2-3 дополнительных курса
4. dependencies отражают реальные зависимости
5. НЕ ПРИДУМЫВАЙ новые курсы — используй ТОЛЬКО те, что в списке!
6. Напиши roadmap_motivation: 2-3 предложения почему такой порядок

ФОРМАТ JSON:
{
   "graph_title": "Название трека",
   "roadmap_motivation": "Объяснение логики...",
   "nodes": [
    {
       "node_id": "1",
       "course_id": "ID_из_списка",
       "title": "Название",
       "level": "новичок",
       "is_core": true,
       "skills": ["навык1"],
       "dependencies": [],
       "why_useful": "Почему важен"
    }
  ],
   "core_path": ["1", "2", "3"],
   "branches": ["4", "5"]
}"""

    MODIFY_PROMPT = """Ты — архитектор образовательных графов. ИЗМЕНИ существующий граф по запросу.

ЗАПРОС: {user_request}
ТЕКУЩИЙ ГРАФ: {current_graph}

ПРАВИЛА:
1. Если просят ДОБАВИТЬ — добавь новые узлы
2. Если просят УДАЛИТЬ — удали указанные
3. Верни ПОЛНЫЙ обновлённый граф"""

    def __init__(self, llm: LLMService, courses_df: pd.DataFrame = None):
        self.llm = llm
        self.courses_df = courses_df if courses_df is not None else pd.DataFrame()

    # ═══════════════════════════════════════════════════════════════
    # ПОИСК СИНОНИМОВ
    # ═══════════════════════════════════════════════════════════════

    def _get_topic_synonyms(self, topic: str) -> List[str]:
        topic_lower = topic.lower().strip()
        for key, synonyms in self.TOPIC_CLUSTERS.items():
            if topic_lower in synonyms or topic_lower == key:
                return synonyms + [key]
            if topic_lower in key or key in topic_lower:
                return synonyms + [key]
        return [topic_lower]

    def validate_graph(self, graph_data: Dict) -> bool:
        """Проверяет валидность графа перед использованием"""
        if not graph_data or not isinstance(graph_data, dict):
            print("⚠️ Граф не словарь")
            return False

        nodes = graph_data.get('nodes', [])
        if not nodes or not isinstance(nodes, list) or len(nodes) == 0:
            print("⚠️ В графе нет узлов")
            return False

        # Проверяем что есть стартовый узел
        has_start = any(
            not node.get('dependencies')
            for node in nodes
            if isinstance(node, dict)
        )
        if not has_start:
            print("⚠️ В графе нет стартового узла (без dependencies)")
            return False

        # Проверяем что все зависимости существуют
        node_ids = {str(n.get('node_id')) for n in nodes if isinstance(n, dict)}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get('node_id')
            deps = node.get('dependencies', [])
            for dep in deps:
                if str(dep) not in node_ids:
                    print(f"⚠️ Узел {node_id} ссылается на несуществующий {dep}")
                    return False

        return True


    # ═══════════════════════════════════════════════════════════════
    # ФИЛЬТРАЦИЯ БАЗЫ
    # ═══════════════════════════════════════════════════════════════

    def filter_courses_by_profile(self, profile: UserProfile, max_results: int = 40) -> List[Dict]:
        """Фильтрует курсы с проверкой русского языка"""
        if self.courses_df.empty:
            return []

        topic = (profile.target_topic or '').lower().strip()
        user_level = profile.current_level or 'новичок'
        topic_synonyms = self._get_topic_synonyms(topic)

        df = self.courses_df.copy()
        mask = pd.Series([False] * len(df), index=df.index)

        for synonym in topic_synonyms:
            mask = mask | df['title'].str.lower().str.contains(synonym, na=False, regex=False)

        filtered = df[mask].copy()

        if filtered.empty:
            return []

        # 🔧 ФИЛЬТР ПО РУССКОМУ ЯЗЫКУ
        def is_russian_text(text):
            """Проверяет что текст преимущественно на русском"""
            if not text or pd.isna(text):
                return False
            text = str(text)
            # Считаем кириллические символы
            cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
            latin = sum(1 for c in text if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))
            # Должно быть минимум 30% кириллицы или нет латиницы
            total_alpha = cyrillic + latin
            if total_alpha == 0:
                return True
            return cyrillic / total_alpha >= 0.3

        filtered = filtered[filtered['title'].apply(is_russian_text)]

        # Фильтрация от запрещёнки
        filtered = filtered[filtered['title'].apply(lambda x: self.llm.is_input_safe(str(x)))]

        # Отсев платных и нерелевантных URL
        if 'url' in filtered.columns:
            filtered = filtered[~filtered['url'].str.lower().str.contains('/promo', na=False)]

            # 🔧 Отсев нерусских сайтов
            def is_valid_russian_url(row):
                url = str(row.get('url', '')).lower()
                title = str(row.get('title', '')).lower()
                combined = url + ' ' + title

                # Чёрный список доменов
                foreign_domains = [
                    'impots.gouv', 'starbucksreserve', 'starbucks.com',
                    'amazon.com', 'ebay.com', 'walmart.com',
                    'gov.uk', 'gov.us', 'franceconnect',
                    'nytimes.com', 'bbc.com', 'cnn.com'
                ]
                if any(domain in combined for domain in foreign_domains):
                    return False

                # Проверка на поисковые страницы
                if '/results?' in url or '/search?' in url:
                    if 'youtube.com' not in url and 'yandex.ru' not in url:
                        return False

                return True

            filtered = filtered[filtered.apply(is_valid_russian_url, axis=1)]

        # Фильтр по уровню
        level_map = {
            'новичок': ['новичок', 'любой'],
            'базовый': ['новичок', 'базовый', 'любой'],
            'продвинутый': ['новичок', 'базовый', 'продвинутый', 'любой']
        }
        allowed_levels = level_map.get(user_level, ['новичок', 'базовый', 'продвинутый', 'любой'])

        if 'level' in filtered.columns:
            filtered = filtered[filtered['level'].isin(allowed_levels)]

        # Сортировка
        filtered['_score'] = filtered['title'].apply(
            lambda x: 100 if topic in str(x).lower() else (
                50 if any(s in str(x).lower() for s in topic_synonyms) else 25)
        )
        filtered = filtered.sort_values(by=['_score'], ascending=[False])
        filtered = filtered.drop(columns=['_score'])

        return filtered.head(max_results).to_dict('records')

    # ═══════════════════════════════════════════════════════════════
    # 🌐 DUCKDUCKGO ПОИСК
    # ═══════════════════════════════════════════════════════════════

    def search_web_courses(self, topic: str, max_results: int = 15) -> List[Dict]:
        """Ищет курсы через DuckDuckGo с таймаутом 10 сек"""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

        def _search_sync() -> List[Dict]:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                print("⚠️ duckduckgo_search не установлен")
                return []

            queries = [
                f'бесплатный курс {topic} обучение русский язык',
                f'{topic} для начинающих бесплатно на русском',
                f'site:stepik.org {topic} бесплатный',
                f'site:youtube.com {topic} обучение плейлист русский',
            ]

            results = []
            seen_urls = set()
            topic_keywords = self._get_topic_synonyms(topic)

            try:
                with DDGS() as ddgs:
                    for query in queries:
                        if len(results) >= max_results:
                            break
                        try:
                            search_results = list(ddgs.text(
                                query, region='ru-ru', max_results=8, safesearch='moderate'
                            ))
                            for item in search_results:
                                url = item.get('href', '')
                                title = item.get('title', '')
                                body = item.get('body', '')

                                if not url or url in seen_urls:
                                    continue

                                # Проверка на русский язык
                                combined = (title + ' ' + body).lower()
                                cyrillic = sum(1 for c in combined if '\u0400' <= c <= '\u04FF')
                                latin = sum(1 for c in combined if c.isalpha() and not ('\u0400' <= c <= '\u04FF'))
                                if latin > 0 and cyrillic / (cyrillic + latin) < 0.4:
                                    continue

                                # Проверка релевантности
                                if not any(kw in combined for kw in topic_keywords):
                                    continue

                                # Чёрные списки
                                if any(agg in url.lower() for agg in self.AGGREGATOR_BLACKLIST):
                                    continue

                                # YouTube: только видео/плейлисты
                                if 'youtube.com' in url or 'youtu.be' in url:
                                    if 'watch?v=' not in url and 'playlist?list=' not in url:
                                        continue

                                # Не поисковые страницы
                                if '/results?' in url or '/search?' in url:
                                    if 'youtube.com' not in url:
                                        continue

                                seen_urls.add(url)
                                results.append({
                                    'id': f'web_{len(results) + 1}',
                                    'title': title,
                                    'url': url,
                                    'level': 'новичок',
                                    'description': body[:200],
                                    'topic': topic,
                                    'why_useful': '',
                                    'skills': [],
                                    'is_core': True,
                                    'difficulty_order': 5
                                })

                                if len(results) >= max_results:
                                    break
                        except Exception as e:
                            print(f"⚠️ Ошибка поиска по запросу '{query}': {e}")
                            continue
            except Exception as e:
                print(f"⚠️ DuckDuckGo недоступен: {e}")

            print(f"   🌐 Найдено в интернете: {len(results)} курсов")
            return results

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_search_sync)
                return future.result(timeout=10)
        except FuturesTimeoutError:
            print(f"⚠️ Веб-поиск превысил таймаут для темы: {topic}")
            return []
        except Exception as e:
            print(f"⚠️ Ошибка веб-поиска: {e}")
            return []
    # ═══════════════════════════════════════════════════════════════
    # LLM-АНАЛИЗАТОР
    # ═══════════════════════════════════════════════════════════════

    def analyze_courses(self, courses: List[Dict], profile: UserProfile, max_analyze: int = 25) -> List[Dict]:
        if not courses:
            return []

        prompt_data = []
        for c in courses[:max_analyze]:
            prompt_data.append({
                'id': str(c.get('id', '')),
                'title': str(c.get('title', ''))[:100],
                'level': c.get('level', 'любой'),
                'desc': str(c.get('description', ''))[:150] if c.get('description') else ''
            })

        user_prompt = f"""Профиль: Тема '{profile.target_topic}', Уровень: '{profile.current_level}'.

Список курсов (выбери лучшие):
{json.dumps(prompt_data, ensure_ascii=False, indent=2)}

Отбери 8-12 лучших курсов, выстрой от простого к сложному."""

        raw_response = self.llm.ask_smart(
            [{'role': 'system', 'content': self.ANALYZER_SYSTEM},
             {'role': 'user', 'content': user_prompt}],
            temperature=0.2
        )

        result = self.llm._extract_json(raw_response)

        final_selected = []
        if result and 'selected' in result:
            for item in result['selected']:
                course_id = str(item.get('id', ''))
                course_full = next((c for c in courses if str(c.get('id', '')) == course_id), None)

                if course_full:
                    final_selected.append({
                        'id': course_full.get('id'),
                        'title': course_full.get('title', ''),
                        'url': course_full.get('url', ''),
                        'level': course_full.get('level', 'новичок'),
                        'description': course_full.get('description', ''),
                        'topic': course_full.get('topic', ''),
                        'why_useful': item.get('why_useful', 'Важный этап обучения'),
                        'skills': item.get('skills', []),
                        'is_core': item.get('is_core', True),
                        'difficulty_order': item.get('difficulty_order', 5)
                    })
        else:
            # Fallback
            for c in courses[:10]:
                final_selected.append({
                    'id': c.get('id'),
                    'title': c.get('title', ''),
                    'url': c.get('url', ''),
                    'level': c.get('level', 'новичок'),
                    'description': c.get('description', ''),
                    'topic': c.get('topic', ''),
                    'why_useful': 'Важный этап обучения',
                    'skills': [],
                    'is_core': True,
                    'difficulty_order': 5
                })

        final_selected.sort(key=lambda x: x.get('difficulty_order', 5))
        return final_selected

    # ═══════════════════════════════════════════════════════════════
    # ПОСТРОЕНИЕ ГРАФА
    # ═══════════════════════════════════════════════════════════════

    def build_learning_graph(self, courses: List[Dict], profile: UserProfile) -> Optional[LearningGraph]:
        if not courses:
            return None

        courses_for_llm = [
            {
                'id': str(c.get('id', '')),
                'title': c.get('title', '')[:80],
                'level': c.get('level', 'новичок'),
                'is_core': c.get('is_core', True),
                'difficulty': c.get('difficulty_order', 5)
            }
            for c in courses
        ]

        prompt = f"""Профиль: Тема '{profile.target_topic}', Уровень '{profile.current_level}', Цель '{profile.goal}'.

Отобранные курсы (по возрастанию сложности):
{json.dumps(courses_for_llm, ensure_ascii=False, indent=2)}

Построй граф зависимостей."""

        raw_response = self.llm.ask_smart(
            [{'role': 'system', 'content': self.GRAPH_ARCHITECT_SYSTEM},
             {'role': 'user', 'content': prompt}],
            temperature=0.2
        )

        graph_data = self.llm._extract_json(raw_response)

        if not graph_data or 'nodes' not in graph_data:
            return self._build_linear_graph(courses, profile)

        # 🔧 Валидация
        if not self.validate_graph(graph_data):
            print("⚠️ LLM вернул битый граф, использую fallback")
            return self._build_linear_graph(courses, profile)

        nodes = []
        for node_data in graph_data.get('nodes', []):
            course_id = str(node_data.get('course_id', ''))
            course = next((c for c in courses if str(c.get('id', '')) == course_id), None)

            if course:
                node = RoadmapNode(
                    node_id=str(node_data.get('node_id', '')),
                    course_id=course_id,
                    title=node_data.get('title', course.get('title', '')),
                    level=node_data.get('level', course.get('level', 'новичок')),
                    is_core=node_data.get('is_core', course.get('is_core', True)),
                    skills=node_data.get('skills', course.get('skills', [])),
                    dependencies=[str(d) for d in node_data.get('dependencies', [])],
                    url=course.get('url', ''),
                    description=course.get('description', ''),
                    why_useful=node_data.get('why_useful', course.get('why_useful', 'Важный этап'))
                )
            else:
                title = node_data.get('title', 'Этап обучения')
                query = urllib.parse.quote(f"{title} {profile.target_topic} обучение")
                node = RoadmapNode(
                    node_id=str(node_data.get('node_id', '')),
                    course_id='custom',
                    title=title,
                    level=node_data.get('level', 'новичок'),
                    is_core=node_data.get('is_core', False),
                    skills=node_data.get('skills', []),
                    dependencies=[str(d) for d in node_data.get('dependencies', [])],
                    url=f'https://www.youtube.com/results?search_query={query}',
                    description='🤖 Сгенерированный этап.',
                    why_useful=node_data.get('why_useful', 'Полезный навык')
                )

            nodes.append(node)

        return LearningGraph(
            graph_title=graph_data.get('graph_title', f"Путь: {profile.target_topic}"),
            roadmap_motivation=graph_data.get('roadmap_motivation', ''),
            nodes=nodes,
            core_path=[str(n) for n in graph_data.get('core_path', [])],
            branches=[str(n) for n in graph_data.get('branches', [])]
        )

    def _build_linear_graph(self, courses: List[Dict], profile: UserProfile) -> LearningGraph:
        """Fallback: линейный граф"""
        nodes = []
        core_path = []

        for i, course in enumerate(courses):
            node_id = str(i + 1)
            dependencies = [str(i)] if i > 0 else []

            node = RoadmapNode(
                node_id=node_id,
                course_id=str(course.get('id', '')),
                title=course.get('title', ''),
                level=course.get('level', 'новичок'),
                is_core=course.get('is_core', True),
                skills=course.get('skills', []),
                dependencies=dependencies,
                url=course.get('url', ''),
                description=course.get('description', ''),
                why_useful=course.get('why_useful', 'Важный этап')
            )
            nodes.append(node)
            core_path.append(node_id)

        return LearningGraph(
            graph_title=f"Путь: {profile.target_topic}",
            roadmap_motivation=f"План из {len(courses)} этапов для изучения {profile.target_topic}.",
            nodes=nodes,
            core_path=core_path,
            branches=[]
        )

    # ═══════════════════════════════════════════════════════════════
    # ГЛАВНЫЙ PIPELINE
    # ═══════════════════════════════════════════════════════════════

    def build_graph(self, profile: UserProfile) -> Optional[LearningGraph]:
        print(f"\n🔍 Ищу курсы по теме: {profile.target_topic}")

        # 1. Фильтрация базы
        filtered = self.filter_courses_by_profile(profile, max_results=40)
        print(f"   📚 Найдено в базе: {len(filtered)} курсов")

        # 2. Если мало — ищем в интернете
        if len(filtered) < 10:
            web_courses = self.search_web_courses(profile.target_topic, max_results=15)
            filtered.extend(web_courses)
            print(f"   ✨ После веб-поиска: {len(filtered)} курсов")

        if not filtered:
            print("   ⚠️ Курсов не найдено, генерирую из LLM")
            return self._generate_fully_custom_graph(profile)

        # 3. LLM отбирает лучшие
        selected = self.analyze_courses(filtered, profile, max_analyze=25)
        print(f"   🎯 LLM отобрал: {len(selected)} курсов")

        # 4. Построение графа
        graph = self.build_learning_graph(selected, profile)

        if graph:
            print(f"   ✅ Граф построен: {len(graph.nodes)} узлов")

        return graph

    def _generate_fully_custom_graph(self, profile: UserProfile) -> LearningGraph:
        """Генерация полностью из LLM когда ничего не найдено"""

        # Сначала пробуем найти через DuckDuckGo
        web_courses = self.search_web_courses(profile.target_topic, max_results=10)

        if web_courses:
            selected = self.analyze_courses(web_courses, profile, max_analyze=10)
            graph = self.build_learning_graph(selected, profile)
            if graph and graph.nodes:
                return graph

        # Fallback на LLM генерацию
        prompt = f"""Создай образовательный граф для темы '{profile.target_topic}' с уровня '{profile.current_level}'.
Построй 6-8 этапов от основ к продвинутому уровню.
Для каждого этапа придумай название и навыки.
Используй course_id: "custom" для всех узлов."""

        raw_response = self.llm.ask_smart(
            [{'role': 'system', 'content': self.GRAPH_ARCHITECT_SYSTEM},
             {'role': 'user', 'content': prompt}],
            temperature=0.3
        )

        graph_data = self.llm._extract_json(raw_response)

        if not graph_data or 'nodes' not in graph_data:
            return self._build_minimal_graph(profile)

        nodes = []
        for node_data in graph_data.get('nodes', []):
            title = node_data.get('title', 'Этап обучения')
            query = urllib.parse.quote(f"{title} обучение {profile.target_topic}")

            node = RoadmapNode(
                node_id=str(node_data.get('node_id', '')),
                course_id='custom',
                title=title,
                level=node_data.get('level', 'новичок'),
                is_core=node_data.get('is_core', True),
                skills=node_data.get('skills', []),
                dependencies=[str(d) for d in node_data.get('dependencies', [])],
                url=f'https://www.youtube.com/results?search_query={query}',
                description='🤖 Сгенерированный этап.',
                why_useful=node_data.get('why_useful', 'Важный навык')
            )
            nodes.append(node)

        return LearningGraph(
            graph_title=graph_data.get('graph_title', f"Путь: {profile.target_topic}"),
            roadmap_motivation=graph_data.get('roadmap_motivation', f"План обучения {profile.target_topic}."),
            nodes=nodes,
            core_path=[str(n) for n in graph_data.get('core_path', [])],
            branches=[str(n) for n in graph_data.get('branches', [])]
        )

    def _build_minimal_graph(self, profile: UserProfile) -> LearningGraph:
        topic = profile.target_topic
        stages = [
            (f"Основы {topic}", "новичок", ["базовые концепции"]),
            (f"Практика {topic}", "базовый", ["применение знаний"]),
            (f"Продвинутый {topic}", "продвинутый", ["сложные темы"])
        ]

        nodes = []
        for i, (title, level, skills) in enumerate(stages):
            query = urllib.parse.quote(f"{title} обучение")
            nodes.append(RoadmapNode(
                node_id=str(i + 1),
                course_id='custom',
                title=title,
                level=level,
                is_core=True,
                skills=skills,
                dependencies=[str(i)] if i > 0 else [],
                url=f'https://www.youtube.com/results?search_query={query}',
                description='🤖 Сгенерированный этап.',
                why_useful='Важный этап обучения'
            ))

        return LearningGraph(
            graph_title=f"Путь: {topic}",
            roadmap_motivation=f"Базовый план из 3 этапов для изучения {topic}.",
            nodes=nodes,
            core_path=['1', '2', '3'],
            branches=[]
        )

    def modify_graph(self, current_graph: LearningGraph, user_request: str, profile: UserProfile) -> Optional[LearningGraph]:
        prompt = self.MODIFY_PROMPT.format(
            user_request=user_request,
            current_graph=json.dumps(current_graph.to_dict(), ensure_ascii=False, indent=2)
        )

        raw_response = self.llm.ask_smart(
            [{'role': 'system', 'content': 'Ты — архитектор образовательных графов.'},
             {'role': 'user', 'content': prompt}],
            temperature=0.2
        )

        graph_data = self.llm._extract_json(raw_response)

        if not graph_data or 'nodes' not in graph_data:
            return None

        nodes = []
        for node_data in graph_data.get('nodes', []):
            node_id = str(node_data.get('node_id', ''))
            existing = next((n for n in current_graph.nodes if n.node_id == node_id), None)

            if existing:
                node = RoadmapNode(
                    node_id=node_id,
                    course_id=existing.course_id,
                    title=node_data.get('title', existing.title),
                    level=node_data.get('level', existing.level),
                    is_core=node_data.get('is_core', existing.is_core),
                    skills=node_data.get('skills', existing.skills),
                    dependencies=[str(d) for d in node_data.get('dependencies', [])],
                    url=existing.url,
                    description=existing.description,
                    why_useful=node_data.get('why_useful', existing.why_useful)
                )
            else:
                title = node_data.get('title', 'Новый этап')
                query = urllib.parse.quote(f"{title} обучение")
                node = RoadmapNode(
                    node_id=node_id,
                    course_id='custom',
                    title=title,
                    level=node_data.get('level', 'новичок'),
                    is_core=node_data.get('is_core', False),
                    skills=node_data.get('skills', []),
                    dependencies=[str(d) for d in node_data.get('dependencies', [])],
                    url=f'https://www.youtube.com/results?search_query={query}',
                    description='🤖 Новый этап.',
                    why_useful=node_data.get('why_useful', 'Дополнительный навык')
                )

            nodes.append(node)

        return LearningGraph(
            graph_title=graph_data.get('graph_title', current_graph.graph_title),
            roadmap_motivation=graph_data.get('roadmap_motivation', ''),
            nodes=nodes,
            core_path=[str(n) for n in graph_data.get('core_path', [])],
            branches=[str(n) for n in graph_data.get('branches', [])]
        )

    def get_start_node_id(self, graph: LearningGraph) -> Optional[str]:
        if not graph.nodes:
            return None

        if graph.core_path:
            first_core = graph.core_path[0]
            if any(n.node_id == first_core for n in graph.nodes):
                return first_core

        for node in graph.nodes:
            if not node.dependencies:
                return node.node_id

        return graph.nodes[0].node_id

    def get_available_nodes(self, graph: LearningGraph, completed: List[str]) -> List[RoadmapNode]:
        completed_set = set(str(c) for c in completed)
        available = []

        for node in graph.nodes:
            if str(node.node_id) in completed_set:
                continue
            deps = [str(d) for d in node.dependencies]
            if all(d in completed_set for d in deps):
                available.append(node)

        available.sort(key=lambda n: (0 if n.is_core else 1, int(n.node_id) if n.node_id.isdigit() else 999))
        return available