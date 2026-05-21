from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


@dataclass
class UserProfile:
    target_topic: str = ""
    current_level: str = "новичок"
    goal: str = "саморазвитие"
    timeline: str = "не важно"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'UserProfile':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoadmapNode:
    node_id: str
    course_id: str
    title: str
    level: str
    is_core: bool
    skills: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    url: str = ""
    description: str = ""
    why_useful: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LearningGraph:
    graph_title: str = ""
    roadmap_motivation: str = ""
    nodes: List[RoadmapNode] = field(default_factory=list)
    core_path: List[str] = field(default_factory=list)
    branches: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "graph_title": self.graph_title,
            "roadmap_motivation": self.roadmap_motivation,
            "nodes": [n.to_dict() for n in self.nodes],
            "core_path": self.core_path,
            "branches": self.branches
        }


@dataclass
class UserSession:
    session_id: str
    state: str = "interview"
    profile: UserProfile = field(default_factory=UserProfile)
    graph: LearningGraph = field(default_factory=LearningGraph)
    chat_history: List[ChatMessage] = field(default_factory=list)
    completed_nodes: List[str] = field(default_factory=list)
    current_node_id: Optional[str] = None
    current_test: Optional[Dict] = None

    # 🔥 ПРОКОИНЫ И ГЕЙМИФИКАЦИЯ
    points: int = 0
    completed_tests: List[str] = field(default_factory=list)
    badges: List[str] = field(default_factory=list)  # ID бейджей
    streak_days: int = 0  # Текущий стрик
    last_activity_date: Optional[str] = None  # YYYY-MM-DD
    daily_quest_progress: Dict = field(default_factory=dict)

    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "profile": self.profile.to_dict(),
            "graph": self.graph.to_dict(),
            "chat_history": [m.to_dict() for m in self.chat_history],
            "completed_nodes": self.completed_nodes,
            "current_node_id": self.current_node_id,
            "current_test": self.current_test,
            "points": self.points,
            "completed_tests": self.completed_tests,
            "badges": self.badges,
            "streak_days": self.streak_days,
            "last_activity_date": self.last_activity_date,
            "daily_quest_progress": self.daily_quest_progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UserSession':
        session = cls(session_id=data["session_id"])
        session.state = data.get("state", "interview")
        session.profile = UserProfile.from_dict(data.get("profile", {}))

        graph_data = data.get("graph", {})
        session.graph = LearningGraph(
            graph_title=graph_data.get("graph_title", ""),
            roadmap_motivation=graph_data.get("roadmap_motivation", ""),
            nodes=[RoadmapNode(**n) for n in graph_data.get("nodes", [])],
            core_path=graph_data.get("core_path", []),
            branches=graph_data.get("branches", [])
        )

        session.chat_history = [ChatMessage(**m) for m in data.get("chat_history", [])]
        session.completed_nodes = data.get("completed_nodes", [])
        session.current_node_id = data.get("current_node_id")
        session.current_test = data.get("current_test")
        session.points = data.get("points", 0)
        session.completed_tests = data.get("completed_tests", [])
        session.created_at = data.get("created_at", datetime.now().timestamp())
        session.updated_at = data.get("updated_at", datetime.now().timestamp())
        return session