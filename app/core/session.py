"""
In-memory session manager for storing conversation history.
Each conversation is identified by a unique chat_id (UUID).
Maintains a sliding window of the last 4 queries and 4 responses,
plus an immutable first query.
"""

from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from threading import Lock
from typing import Dict, Optional
from uuid import uuid4


@dataclass
class QueryRecord:
    """Represents a natural language query from the user."""
    timestamp: datetime
    question: str
    error: Optional[str] = None


@dataclass
class ResponseRecord:
    """Represents a response from the query agent."""
    timestamp: datetime
    sql: str
    sql_raw: str
    result: Optional[list]
    error: Optional[str]
    retries: int


@dataclass
class ChatSession:
    """Represents a single conversation session."""
    chat_id: str
    created_at: datetime
    first_query: QueryRecord
    queries: deque = field(default_factory=lambda: deque(maxlen=4))  # Last 4 queries
    responses: deque = field(default_factory=lambda: deque(maxlen=4))  # Last 4 responses


class SessionManager:
    """
    Manages in-memory chat sessions.
    Thread-safe. Data persists only for the lifetime of the application.
    """

    def __init__(self):
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = Lock()

    def create_session(self, first_question: str) -> str:
        """
        Create a new session and record the first query.
        Returns the chat_id.
        """
        chat_id = str(uuid4())
        now = datetime.now()
        first_query = QueryRecord(timestamp=now, question=first_question)

        session = ChatSession(
            chat_id=chat_id,
            created_at=now,
            first_query=first_query,
        )

        with self._lock:
            self._sessions[chat_id] = session

        return chat_id

    def get_session(self, chat_id: str) -> Optional[ChatSession]:
        """Retrieve a session by chat_id. Returns None if not found."""
        with self._lock:
            return self._sessions.get(chat_id)

    def add_query(self, chat_id: str, question: str, error: Optional[str] = None) -> bool:
        """
        Add a query to an existing session.
        Returns True if successful, False if chat_id not found.
        """
        session = self.get_session(chat_id)
        if not session:
            return False

        query_record = QueryRecord(timestamp=datetime.now(), question=question, error=error)
        with self._lock:
            session.queries.append(query_record)
        return True

    def add_response(self, chat_id: str, sql: str, sql_raw: str, result: Optional[list],
                    error: Optional[str], retries: int) -> bool:
        """
        Add a response to an existing session.
        Returns True if successful, False if chat_id not found.
        """
        session = self.get_session(chat_id)
        if not session:
            return False

        response_record = ResponseRecord(
            timestamp=datetime.now(),
            sql=sql,
            sql_raw=sql_raw,
            result=result,
            error=error,
            retries=retries,
        )
        with self._lock:
            session.responses.append(response_record)
        return True

    def list_sessions(self) -> list:
        """
        Return metadata for all active sessions.
        Returns list of dicts with chat_id, created_at, query_count, response_count.
        """
        with self._lock:
            return [
                {
                    "chat_id": session.chat_id,
                    "created_at": session.created_at.isoformat(),
                    "query_count": len(session.queries),
                    "response_count": len(session.responses),
                }
                for session in self._sessions.values()
            ]

    def get_chat_history(self, chat_id: str) -> Optional[Dict]:
        """
        Get the full conversation history for a chat_id.
        Returns dict with first_query, queries, responses.
        Returns None if chat_id not found.
        """
        session = self.get_session(chat_id)
        if not session:
            return None

        with self._lock:
            return {
                "chat_id": session.chat_id,
                "created_at": session.created_at.isoformat(),
                "first_query": {
                    "timestamp": session.first_query.timestamp.isoformat(),
                    "question": session.first_query.question,
                    "error": session.first_query.error,
                },
                "queries": [
                    {
                        "timestamp": q.timestamp.isoformat(),
                        "question": q.question,
                        "error": q.error,
                    }
                    for q in session.queries
                ],
                "responses": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "sql": r.sql,
                        "sql_raw": r.sql_raw,
                        "result": r.result,
                        "error": r.error,
                        "retries": r.retries,
                    }
                    for r in session.responses
                ],
            }
