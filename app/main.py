from dataclasses import dataclass
from typing import Optional
from app.core.config import settings  # ensures env is loaded once
from app.core.session import SessionManager
from app.graph.graph import build_graph
from app.retriever.schema_retriever import SchemaRetriever
from app.db.connections import get_connection_engine
from scripts.ingest_schema import extract_schema_from_engine

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

def _schema_for_query(question: str, connection_id: Optional[str]) -> str:
    if connection_id:
        # Connection profiles must always use their own live schema. Reusing the
        # deployment-wide vector namespace can inject tables from another DB.
        engine = get_connection_engine(connection_id, owner_id="default")
        return "\n".join(extract_schema_from_engine(engine))
    return _get_retriever().retrieve(question)

@dataclass
class QueryResponse:
    sql: str
    result: Optional[list]
    error: Optional[str]
    retries: int
    chat_id: str = ""
    connection_id: Optional[str] = None
    provider_id: Optional[str] = None
    model: Optional[str] = None

def query_agent(question: str, chat_id: Optional[str] = None, connection_id: Optional[str] = None,
                provider_id: Optional[str] = None, model: Optional[str] = None) -> QueryResponse:
    # Create new session if chat_id not provided, otherwise use existing
    if chat_id is None:
        chat_id = _session_manager.create_session(question, connection_id, provider_id, model)
    else:
        existing = _session_manager.get_session(chat_id)
        if existing:
            connection_id = connection_id or existing.connection_id
            provider_id = provider_id or existing.provider_id
            model = model or existing.model
        _session_manager.add_query(chat_id, question, connection_id=connection_id,
                                   provider_id=provider_id, model=model)

    schema = _schema_for_query(question, connection_id)
    state = {"question": question, "schema": schema, "sql": "", "result": None,
             "error": None, "retries": 0, "connection_id": connection_id,
             "provider_id": provider_id, "model": model}
    final = _get_graph().invoke(state)

    # Record response to session
    _session_manager.add_response(
        chat_id=chat_id,
        sql=final["sql"],
        sql_raw=final["sql"],
        result=final["result"],
        error=final["error"],
        retries=final["retries"],
        connection_id=final.get("connection_id"), provider_id=final.get("provider_id"),
        model=final.get("model"),
    )

    return QueryResponse(
        sql=final["sql"],
        result=final["result"],
        error=final["error"],
        retries=final["retries"],
        chat_id=chat_id,
        connection_id=final.get("connection_id"), provider_id=final.get("provider_id"),
        model=final.get("model"),
    )
