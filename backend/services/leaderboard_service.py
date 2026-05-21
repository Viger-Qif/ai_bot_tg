"""
Лидерборд на SQLite — реальные очки пользователей
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional


class LeaderboardService:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '', 'leaderboard.db')
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS leaderboard (
                    session_id TEXT PRIMARY KEY,
                    username TEXT DEFAULT 'Аноним',
                    points INTEGER DEFAULT 0,
                    topic TEXT DEFAULT '',
                    badges_count INTEGER DEFAULT 0,
                    streak_days INTEGER DEFAULT 0,
                    updated_at REAL
                )
            ''')
            conn.commit()

    def update_score(self, session_id: str, username: str, points: int,
                     topic: str = '', badges_count: int = 0, streak_days: int = 0):
        with self._get_conn() as conn:
            conn.execute('''
                INSERT INTO leaderboard (session_id, username, points, topic, badges_count, streak_days, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    username=excluded.username,
                    points=excluded.points,
                    topic=excluded.topic,
                    badges_count=excluded.badges_count,
                    streak_days=excluded.streak_days,
                    updated_at=excluded.updated_at
            ''', (session_id, username, points, topic, badges_count, streak_days, datetime.now().timestamp()))
            conn.commit()

    def get_top(self, limit: int = 50) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT username, points, topic, badges_count, streak_days
                FROM leaderboard
                ORDER BY points DESC
                LIMIT ?
            ''', (limit,))
            return [
                {
                    'name': row[0],
                    'points': row[1],
                    'level': row[2] or 'Ученик',
                    'badges': row[3],
                    'streak': row[4]
                }
                for row in cursor.fetchall()
            ]

    def get_user_rank(self, session_id: str) -> Optional[int]:
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) + 1 FROM leaderboard
                WHERE points > (SELECT COALESCE(points, 0) FROM leaderboard WHERE session_id = ?)
            ''', (session_id,))
            row = cursor.fetchone()
            return row[0] if row else None