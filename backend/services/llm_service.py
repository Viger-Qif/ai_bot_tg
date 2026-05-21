import requests
import time
import json
import re
from typing import Optional, List, Dict


class LLMService:
    # Твои ключи (если нужно, вставь свои)
    API_KEYS = [
        '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'
    ]

    OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

    MODELS = {
        'fast': 'poolside/laguna-xs.2:free',
        'smart': 'openrouter/owl-alpha'
    }

    TIMEOUTS = {'fast': 10, 'smart': 25}

    def __init__(self):
        self._key_state = {'current_index': 0, 'exhausted': []}

    def _get_current_key(self) -> str:
        return self.API_KEYS[self._key_state['current_index']]

    def _rotate_key(self) -> bool:
        current = self._key_state['current_index']
        self._key_state['exhausted'].append(current)
        for idx in range(len(self.API_KEYS)):
            if idx not in self._key_state['exhausted']:
                self._key_state['current_index'] = idx
                print(f"🔑 Переключение на API ключ #{idx + 1}")
                return True
        print("❌ Все API ключи исчерпаны!")
        return False

    def _extract_json(self, content: str) -> Optional[Dict]:
        """Умный парсинг JSON с исправлением частых ошибок моделей"""
        if not content:
            return None

        # 1. Убираем markdown обёртку ```json ... ```
        content = re.sub(r'```(?:json)?', '', content).strip().strip('`')

        # 2. Ищем первый { и последний }
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            content = match.group(0).strip()
        else:
            # Если JSON не найден, пробуем взять весь текст как есть (на всякий случай)
            pass

        # 3. Фиксим trailing commas: {"a": "b",} -> {"a": "b"}
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)

        # 4. Пробуем распарсить
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 5. Фиксим одинарные кавычки: {'a': 'b'} -> {"a": "b"}
            try:
                return json.loads(content.replace("'", '"'))
            except Exception:
                return None

    def call_llm(self, messages: List[Dict], mode: str = 'fast',
                 temperature: float = 0.2, expect_json: bool = True,
                 retries: int = 2) -> Optional[str]:

        model = self.MODELS.get(mode, self.MODELS['fast'])
        timeout = self.TIMEOUTS.get(mode, 15)

        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature
        }
        if expect_json and mode == 'fast':
            payload['response_format'] = {'type': 'json_object'}

        for attempt in range(retries):
            try:
                response = requests.post(
                    self.OPENROUTER_URL,
                    headers={
                        'Authorization': f'Bearer {self._get_current_key()}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'http://localhost:8000',
                        'X-Title': 'Progressor'
                    },
                    json=payload,
                    timeout=timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get('choices', [])
                    if choices:
                        return choices[0]['message'].get('content', '').strip()

                elif response.status_code == 429:
                    if self._rotate_key():
                        time.sleep(1)
                        continue
                    return None

                elif response.status_code in (500, 502, 503, 504):
                    time.sleep(2)
                    continue

            except requests.RequestException:
                time.sleep(2)
                continue

        return None

    def ask_fast(self, messages: List[Dict], temperature: float = 0.2,
                 expect_json: bool = True) -> Optional[str]:
        return self.call_llm(messages, 'fast', temperature, expect_json)

    def ask_smart(self, messages: List[Dict], temperature: float = 0.3) -> Optional[str]:
        """Умная модель для сложного анализа"""
        return self.call_llm(messages, 'smart', temperature, False)

    # ═══════════════════════════════════════════════════════════════
    # 🚫 БЕЗОПАСНОСТЬ
    # ═══════════════════════════════════════════════════════════════
    BANNED_ROOTS = []  # Заполни из исходника если нужно

    def is_input_safe(self, text: str) -> bool:
        if not self.BANNED_ROOTS:
            return True
        text_lower = text.lower()
        return not any(root in text_lower for root in self.BANNED_ROOTS)