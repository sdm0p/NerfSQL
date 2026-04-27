import json
import os
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from pydantic import BaseModel
from app.core.config import settings
from app.main import QueryResponse, query_agent, _session_manager
from scripts.ingest_schema import extract_schema, upsert_schema_chunks_to_pinecone

app = FastAPI(title="SQL-RAG Agent", description="Natural language to SQL agent powered by RAG", version="1.0.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response

app.add_middleware(SecurityHeadersMiddleware)

class QueryRequest(BaseModel):
    question: str

class IngestRequest(BaseModel):
    db_uri: str | None = None  # defaults to DB_URI from .env if omitted

    model_config = {"json_schema_extra": {"examples": [{"db_uri": "postgresql://user:pass@localhost/mydb"}]}}


def _compact_sql(sql: str) -> str:
    # Deterministic API-side formatting for JSON clients.
    return re.sub(r"\s+", " ", (sql or "")).strip()

@app.get("/health", summary="Health check", tags=["Utility"])
def health():
    return {"status": "ok"}

@app.post("/ingest", summary="Ingest database schema", tags=["Schema"])
def ingest(req: IngestRequest = IngestRequest()):
    db_uri = req.db_uri or settings.db_uri
    local_fallback = "sqlite:///data/local.db"
    if not db_uri:
        if os.path.exists("data/local.db"):
            db_uri = local_fallback
        else:
            raise HTTPException(status_code=400, detail="db_uri required")
    try:
        chunks = extract_schema(db_uri)
    except Exception as e:
        # For local development, fall back if configured DB credentials are invalid.
        if req.db_uri is None and db_uri != local_fallback and os.path.exists("data/local.db"):
            try:
                chunks = extract_schema(local_fallback)
                db_uri = local_fallback
            except Exception:
                raise HTTPException(status_code=500, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))
    try:
        with open("data/schema_chunks.json", "w") as f:
            json.dump(chunks, f, indent=2)
        # reset retriever so it reloads fresh chunks
        import app.main as _main

        _main._retriever = None

        pinecone_status = "skipped"
        api_key = settings.pinecone_api_key
        if api_key:
            upserted = upsert_schema_chunks_to_pinecone(
                chunks=chunks,
                index_name=settings.pinecone_index_name,
                namespace=settings.pinecone_namespace,
                region=settings.pinecone_region,
                api_key=api_key,
            )
            pinecone_status = f"upserted:{upserted}"

        return {
            "ingested": len(chunks),
            "tables": [c.split("\n")[0].replace("Table: ", "") for c in chunks],
            "pinecone": pinecone_status,
            "source_db_uri": db_uri,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema", summary="Retrieve ingested schema chunks", tags=["Schema"])
def schema():
    try:
        with open("data/schema_chunks.json") as f:
            chunks = json.load(f)
        return {"count": len(chunks), "chunks": chunks}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Schema not ingested yet. Call POST /ingest first.")

@app.post("/query", summary="Run a natural language query", tags=["Query"])
def query(req: QueryRequest, chat_id: str | None = Query(None)):
    resp: QueryResponse = query_agent(req.question, chat_id=chat_id)

    # Build response conditionally
    response_data = {
        "chat_id": resp.chat_id,
        "error": resp.error,
        "retries": resp.retries,
    }

    # Only include SQL fields if SQL was successfully generated
    if resp.sql.strip():
        response_data["sql"] = _compact_sql(resp.sql)
        response_data["sql_raw"] = resp.sql

    # Include result if available
    if resp.result is not None:
        response_data["result"] = resp.result

    return response_data

@app.get("/history", summary="List all active chat sessions", tags=["History"])
def history():
    """Returns metadata for all active chat sessions."""
    sessions = _session_manager.list_sessions()
    return {"chats": sessions}

@app.get("/history/{chat_id}", summary="Get conversation history for a chat", tags=["History"])
def history_detail(chat_id: str):
    """Returns the full conversation history (first query + last 4 queries + last 4 responses)."""
    history = _session_manager.get_chat_history(chat_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found")
    return history
