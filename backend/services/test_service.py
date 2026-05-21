"""
Сервис работы с тестами
"""

from typing import Dict, List, Optional
import random
from .llm_service import LLMService

class TestService:
    def __init__(self, llm: LLMService, tests_db: Dict[str, List[Dict]]):
        self.llm = llm
        self.tests_db = tests_db or {}

    def get_test_for_course(self, course_id: str) -> Optional[Dict]:
        """Ищет тест для курса в базе данных"""
        # Ищем по course_id
        tests = self.tests_db.get(str(course_id), [])
        if tests:
            return random.choice(tests)

        # Ищем по topic (если tests_db сгруппирован по темам)
        for topic, topic_tests in self.tests_db.items():
            if topic.lower() in str(course_id).lower():
                if topic_tests:
                    return random.choice(topic_tests)

        return None

    def find_test_by_topic(self, topic: str) -> Optional[Dict]:
        """Ищет тест по названию темы"""
        topic_lower = topic.lower()

        for db_topic, tests in self.tests_db.items():
            if topic_lower in db_topic.lower() or db_topic.lower() in topic_lower:
                if tests:
                    return random.choice(tests)

        return None

    def generate_dynamic_test(self, course_title: str) -> Dict:
        """Генерирует простой тест, если его нет в базе"""
        system_prompt = """Ты — добрый экзаменатор. Придумай ОДИН очень простой базовый вопрос на РУССКОМ ЯЗЫКЕ по теме курса.
Вопрос должен быть теоретическим или на логику. НЕ ИСПОЛЬЗУЙ АНГЛИЙСКИЙ.
Верни ТОЛЬКО JSON:
{
   "question": "текст вопроса",
   "correct_answer": "короткий эталонный ответ"
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Курс: {course_title}"}
        ]

        try:
            raw_response = self.llm.ask_fast(messages, temperature=0.3)
            result = self.llm._extract_json(raw_response)

            if result and "question" in result:
                return result
        except Exception as e:
            print(f"⚠️ Ошибка генерации теста: {e}")

        # Fallback
        return {
            "question": f"Какое главное правило при изучении темы '{course_title}'?",
            "correct_answer": "Практика и внимательность к деталям."
        }

    def evaluate_answer(self, question: str, correct_answer: str, user_answer: str) -> Dict:
        """Добрая проверка ответа"""
        system_prompt = """Ты — ОЧЕНЬ ДОБРЫЙ ИИ-учитель.
Тебе дадут ВОПРОС, ЭТАЛОН и ОТВЕТ ПОЛЬЗОВАТЕЛЯ.
Твоя задача: понять, правильно ли ответил пользователь.
ПРАВИЛО: Не придирайся к словам! Если суть верна, логична или человек просто угадал смысл — ставь passed: true и хвали его.
Верни ТОЛЬКО JSON:
{
   "passed": true/false,
   "feedback": "Короткий дружелюбный комментарий на русском"
}"""

        prompt = f"ВОПРОС: {question}\nЭТАЛОН: {correct_answer}\nОТВЕТ УЧЕНИКА: {user_answer}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_response = self.llm.call_llm(messages, mode='smart', temperature=0.1, expect_json=True)
            result = self.llm._extract_json(raw_response)

            if result and "passed" in result:
                return result
        except Exception as e:
            print(f"⚠️ Ошибка проверки ответа: {e}")

        return {
            "passed": False,
            "feedback": "Я не совсем понял твой ответ. Попробуй объяснить иначе!"
        }