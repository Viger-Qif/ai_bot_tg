"""
Простая аналитика — пишем события в JSONL файл
"""
import json
import os
from datetime import datetime

class AnalyticsService:
    def __init__(self, log_file: str = None):
        if log_file is None:
            log_file = os.path.join(os.path.dirname(__file__), '..', 'analytics.jsonl')
        self.log_file = os.path.abspath(log_file)

    def log(self, session_id: str, event: str, data: dict = None):
        record = {
            'ts': datetime.now().isoformat(),
            'sid': session_id[:16],
            'ev': event,
            'data': data or {}
        }
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"⚠️ Analytics error: {e}")

analytics = AnalyticsService()