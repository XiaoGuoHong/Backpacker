from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.models import Itinerary, TripRequest


@dataclass
class Session:
    session_id: str
    confirmed: dict = field(default_factory=dict)
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: Optional[str], default_id: str) -> Session:
        sid = session_id or default_id
        sess = self._sessions.get(sid)
        if sess is None:
            sess = Session(session_id=sid)
            self._sessions[sid] = sess
        return sess

    def merge(self, session_id: str, params: dict) -> Session:
        sess = self._sessions.get(session_id)
        if sess is None:
            sess = Session(session_id=session_id)
            self._sessions[session_id] = sess
        for k, v in params.items():
            if v is not None:
                sess.confirmed[k] = v
        return sess

    def save_plan(self, session_id: str, task_id: str, request: TripRequest, itinerary: Itinerary) -> None:
        sess = self.get_or_create(session_id, session_id)
        sess.plans[task_id] = {
            "request": request.model_dump(mode="json"),
            "itinerary": itinerary.model_dump(mode="json"),
        }

    def get_plan(self, session_id: str, task_id: str) -> dict[str, Any] | None:
        sess = self._sessions.get(session_id)
        if sess is None:
            return None
        return sess.plans.get(task_id)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
