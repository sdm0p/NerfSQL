from dataclasses import dataclass
from typing import Optional
from app.core.config import settings  # ensures env is loaded once
from app.core.session import SessionManager
from app.graph.graph import build_graph
from app.retriever.schema_retriever import SchemaRetriever

_ = settings

_graph = None
_retriever = None
_session_manager = SessionManager()

def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = SchemaRetriever()
    return _retriever

@dataclass
class QueryResponse:
    sql: str
    result: Optional[list]
    error: Optional[str]
    retries: int
    chat_id: str

def query_agent(question: str, chat_id: Optional[str] = None) -> QueryResponse:
    # Create new session if chat_id not provided, otherwise use existing
    if chat_id is None:
        chat_id = _session_manager.create_session(question)
    else:
        _session_manager.add_query(chat_id, question)

    schema = _get_retriever().retrieve(question)
    state = {"question": question, "schema": schema, "sql": "", "result": None, "error": None, "retries": 0}
    final = _get_graph().invoke(state)

    # Record response to session
    _session_manager.add_response(
        chat_id=chat_id,
        sql=final["sql"],
        sql_raw=final["sql"],
        result=final["result"],
        error=final["error"],
        retries=final["retries"],
    )

    return QueryResponse(
        sql=final["sql"],
        result=final["result"],
        error=final["error"],
        retries=final["retries"],
        chat_id=chat_id,
    )
