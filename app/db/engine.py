import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings

_engine = None
LOCAL_DB_URI = "sqlite:///data/local.db"


def _candidate_uris() -> list[str]:
    uris: list[str] = []
    if settings.db_uri:
        uris.append(settings.db_uri)
    if LOCAL_DB_URI not in uris and os.path.exists("data/local.db"):
        uris.append(LOCAL_DB_URI)
    return uris

def get_engine():
    global _engine
    if _engine is None:
        last_error: Exception | None = None
        for uri in _candidate_uris():
            try:
                candidate = create_engine(uri)
                with candidate.connect() as conn:
                    conn.execute(text("SELECT 1"))
                _engine = candidate
                break
            except SQLAlchemyError as e:
                last_error = e

        if _engine is None:
            configured = settings.db_uri or "<not set>"
            raise RuntimeError(
                "Unable to connect to configured DB_URI and no working local fallback found. "
                f"Configured DB_URI={configured}. "
                "Set a valid DB_URI or create data/local.db via scripts/create_sample_db.py"
            ) from last_error
    return _engine

def execute_query(sql: str) -> list[dict]:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql))
        return [dict(row._mapping) for row in result]
