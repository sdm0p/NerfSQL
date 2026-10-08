import json
import os
import re
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from pydantic import BaseModel
from app.core.config import settings
from app.main import QueryResponse, query_agent, _session_manager
from scripts.ingest_schema import extract_schema, upsert_schema_chunks_to_pinecone
from app.db import connections
from app.llm import profiles as provider_profiles
from app.llm.client import get_llm, ProviderError
from app.queue import enqueue_seed, drain_seed_queue

app = FastAPI(title="SQL-RAG Agent", description="Natural language to SQL agent powered by RAG", version="1.0.0")
app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")

@app.on_event("startup")
def drain_startup_seed_queue():
    """Replay durable seed jobs after a container restart."""
    try:
        drain_seed_queue()
    except Exception:
        # The API remains available if Upstash is temporarily unreachable.
        pass

@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/frontend/")

app.add_middleware(GZipMiddleware, minimum_size=1000)
_allowed_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
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
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; connect-src 'self'"
        return response

app.add_middleware(SecurityHeadersMiddleware)

class QueryRequest(BaseModel):
    question: str
    connection_id: str | None = None
    provider_id: str | None = None
    model: str | None = None

class ProviderRequest(BaseModel):
    name: str
    provider_type: str
    api_key: str
    model: str
    base_url: str | None = None

class ConnectionRequest(BaseModel):
    name: str
    db_uri: str
    provider_id: str | None = None

class IngestRequest(BaseModel):
    db_uri: str | None = None  # defaults to DB_URI from .env if omitted

    model_config = {"json_schema_extra": {"examples": [{"db_uri": "postgresql://user:pass@localhost/mydb"}]}}


def _compact_sql(sql: str) -> str:
    # Deterministic API-side formatting for JSON clients.
    return re.sub(r"\s+", " ", (sql or "")).strip()

@app.get("/health", summary="Health check", tags=["Utility"])
def health():
    """Lightweight liveness probe used by Render and external monitors."""
    return {"status": "ok", "service": "nerfsql"}

@app.get("/ready", tags=["Utility"])
def ready():
    return {"status": "ready"}

@app.post("/jobs/seed", tags=["Jobs"])
def seed_job():
    """Queue a rebuildable demo dataset; the job is safe to retry."""
    return enqueue_seed()

@app.post("/providers", tags=["Providers"])
def create_provider(req: ProviderRequest):
    try:
        profile = provider_profiles.create_profile(owner_id="default", **req.model_dump())
        # Construction validates provider type and local configuration without making a paid call.
        get_llm(profile=provider_profiles.get_profile(profile["provider_id"]))
        return profile
    except (ValueError, ProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/providers", tags=["Providers"])
def list_providers():
    return {"providers": provider_profiles.list_profiles()}

@app.get("/providers/{provider_id}", tags=["Providers"])
def get_provider(provider_id: str):
    profile = next((p for p in provider_profiles.list_profiles() if p["provider_id"] == provider_id), None)
    if not profile: raise HTTPException(status_code=404, detail="Provider not found")
    return profile

@app.delete("/providers/{provider_id}", tags=["Providers"])
def delete_provider(provider_id: str):
    if not provider_profiles.delete_profile(provider_id): raise HTTPException(status_code=404, detail="Provider not found")
    return {"deleted": True, "provider_id": provider_id}

@app.post("/connections", tags=["Connections"])
def create_connection(req: ConnectionRequest):
    try:
        return connections.create_profile(owner_id="default", name=req.name, uri=req.db_uri, provider_id=req.provider_id)
    except connections.ConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/connections", tags=["Connections"])
def list_connections():
    return {"connections": connections.list_profiles("default")}

@app.get("/connections/{connection_id}", tags=["Connections"])
def get_connection(connection_id: str):
    profile = connections.get_profile(connection_id, "default")
    if not profile: raise HTTPException(status_code=404, detail="Connection not found")
    return connections.profile_public(profile)

@app.delete("/connections/{connection_id}", tags=["Connections"])
def delete_connection(connection_id: str):
    if not connections.delete_profile(connection_id, "default"): raise HTTPException(status_code=404, detail="Connection not found")
    return {"deleted": True, "connection_id": connection_id}

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
        schema_path = os.path.join(os.path.dirname(os.getenv("MOCK_DB_PATH", "data/local.db")), "schema_chunks.json")
        if not os.path.exists(schema_path):
            db_path = os.getenv("MOCK_DB_PATH", "data/local.db")
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
                    chunks = []
                    for (table,) in tables:
                        cols = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
                        chunks.append(f"Table: {table}\nColumns: {', '.join(cols)}")
                with open(schema_path, "w", encoding="utf-8") as out:
                    json.dump(chunks, out)
        with open(schema_path) as f:
            chunks = json.load(f)
        return {"count": len(chunks), "chunks": chunks}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Schema not ingested yet. Call POST /ingest first.")

@app.post("/query", summary="Run a natural language query", tags=["Query"])
def query(req: QueryRequest, chat_id: str | None = Query(None)):
    resp: QueryResponse = query_agent(req.question, chat_id=chat_id, connection_id=req.connection_id,
                                      provider_id=req.provider_id, model=req.model)

    # Build response conditionally
    response_data = {
        "chat_id": resp.chat_id,
        "error": resp.error,
        "retries": resp.retries,
        "connection_id": resp.connection_id,
        "provider_id": resp.provider_id,
        "model": resp.model,
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
