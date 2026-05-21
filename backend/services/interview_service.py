"""
Интервьюер с ПРИНУДИТЕЛЬНЫМ построением профиля после 3 сообщений.
"""

import re
from typing import Dict, List, Optional
from models import ChatMessage
from .llm_service import LLMService

class InterviewService:
    # Расширенный словарь тем
    TOPIC_KEYWORDS = {
        'Python': ['питон', 'python', 'пайтон', 'django', 'flask', 'джанго'],
        'JavaScript': ['javascript', 'js', 'джаваскрипт', 'фронтенд', 'frontend', 'react', 'vue'],
        'Веб-разработка': ['веб', 'сайт', 'сайты', 'web', 'fullstack', 'фулстек', 'html', 'css'],
        'Data Science': ['данные', 'data', 'ml', 'machine learning', 'pandas', 'датасаенс', 'нейросет', 'ии', 'ai'],
        'Дизайн': ['дизайн', 'design', 'figma', 'ui', 'ux'],
        'QA/Тестирование': ['тестирование', 'qa', 'автотесты', 'selenium'],
        'Java': ['java', 'джава', 'spring'],
        'C#': ['c#', 'csharp', 'шарп', '.net'],
        'DevOps': ['devops', 'девопс', 'docker', 'kubernetes', 'linux'],
        'Мобильная разработка': ['мобильн', 'android', 'ios', 'flutter', 'swift', 'kotlin'],
        'Кулинария': ['повар', 'готовить', 'кулинар', 'рецепт', 'кухн', 'гроссмейстер', 'кгандмастер'],
        'Маркетинг': ['маркетинг', 'smm', 'продвижение'],
        'Шахматы': ['шахмат', 'гроссмейстер', 'кгандмастер', 'гандмастер'],
    }

    LEVEL_KEYWORDS = {
        'новичок': ['новичок', 'нулев', 'с нуля', 'нет опыта', '0 опыта', 'не умею', 'полный 0', 'начинающ', 'ниразу', 'ни раз'],
        'базовый': ['базов', 'средн', 'немного', 'чуть-чуть', 'знаю основы', 'middle'],
        'продвинутый': ['продвинут', 'опыт', 'сеньор', 'senior', 'хорошо знаю', 'профи'],
    }

    def __init__(self, llm: LLMService):
        self.llm = llm
        self.MAX_TURNS = 3  # После 3 ответов — ВСЕГДА строим граф

    def _extract_topic(self, text: str) -> Optional[str]:
        """Извлекает тему из текста"""
        text_lower = text.lower()
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return None

    def _extract_level(self, text: str) -> str:
        """Извлекает уровень из текста"""
        text_lower = text.lower()
        for level, keywords in self.LEVEL_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return level
        return 'новичок'

    def _extract_topic_from_all_messages(self, chat_history: List[ChatMessage], user_message: str) -> str:
        """
        Извлекает тему из ВСЕХ сообщений пользователя.
        Если не находит по ключевым словам — берёт первую значимую фразу.
        """
        all_messages = [m.content for m in chat_history if m.role == 'user'] + [user_message]
        all_text = ' '.join(all_messages).lower()

        # 1. Пробуем найти по ключевым словам
        topic = self._extract_topic(all_text)
        if topic:
            return topic

        # 2. Ищем в последнем сообщении пользователя
        last_msg = user_message.strip()
        if last_msg and len(last_msg) >= 2:
            # Берём первое слово или фразу как тему
            words = last_msg.split()
            if len(words) <= 3:
                return last_msg.capitalize()
            else:
                return words[0].capitalize()

        # 3. Ищем в любом сообщении
        for msg in reversed(all_messages):
            msg = msg.strip()
            if msg and len(msg) >= 2:
                words = msg.split()
                if len(words) <= 3:
                    return msg.capitalize()
                return words[0].capitalize()

        return 'Общие знания'

    def process_message(self, user_message: str, chat_history: List[ChatMessage]) -> Dict:
        # 1. Проверка безопасности
        if not self.llm.is_input_safe(user_message):
            return {'status': 'blocked', 'message': 'Эта тема нарушает правила безопасности.'}

        # 2. Считаем ходы пользователя
        user_turns = sum(1 for m in chat_history if m.role == 'user')

        # 3. После MAX_TURNS ходов — ВСЕГДА строим профиль принудительно
        if user_turns >= self.MAX_TURNS:
            topic = self._extract_topic_from_all_messages(chat_history, user_message)
            level = self._extract_level(' '.join([m.content for m in chat_history if m.role == 'user']) + ' ' + user_message)

            print(f"🎯 ПРИНУДИТЕЛЬНО: тема='{topic}', уровень='{level}' (после {user_turns} ходов)")

            return {
                'status': 'ready',
                'message': f'Понял! Тема: {topic}, уровень: {level}. Сейчас соберу план 🚀',
                'profile': {
                    'target_topic': topic,
                    'current_level': level,
                    'goal': 'саморазвитие',
                    'timeline': 'не важно'
                }
            }

        # 4. На первых ходах — пытаемся найти тему
        all_text = ' '.join([m.content for m in chat_history if m.role == 'user']) + ' ' + user_message
        topic = self._extract_topic(all_text)
        level = self._extract_level(all_text)

        # Если нашли и тему и уровень — можно сразу строить
        if topic and level and user_turns >= 1:
            print(f"🎯 Раннее построение: тема='{topic}', уровень='{level}'")
            return {
                'status': 'ready',
                'message': f'Отлично! {topic} ({level}). Сейчас соберу план 🚀',
                'profile': {
                    'target_topic': topic,
                    'current_level': level,
                    'goal': 'саморазвитие',
                    'timeline': 'не важно'
                }
            }

        # 5. Иначе — задаём уточняющий вопрос через LLM
        return self._ask_clarification(user_message, chat_history)

    def _ask_clarification(self, user_message: str, chat_history: List[ChatMessage]) -> Dict:
        """Задаёт уточняющий вопрос"""
        system_prompt = """Ты — интервьюер. Задай ОДИН короткий вопрос на русском (про уровень или цель).
Отвечай обычным текстом, НЕ JSON. Максимум 2 предложения. Не повторяй предыдущие вопросы."""

        messages = [{'role': 'system', 'content': system_prompt}]
        for msg in chat_history[-4:]:
            messages.append({'role': msg.role, 'content': msg.content})
        messages.append({'role': 'user', 'content': user_message})

        response = self.llm.ask_fast(messages, temperature=0.5, expect_json=False)

        return {
            'status': 'need_more',
            'message': response or 'Интересно! Расскажи подробнее о своём уровне.',
            'collected': {}
        }