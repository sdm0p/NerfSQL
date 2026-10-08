"""Named database connection profiles and isolated SQLAlchemy engines.

Profiles are stored in a small local metadata database by default.  Set
``CONNECTION_STORE_URI`` to the application's durable metadata database in
production.  Connection URLs are encrypted at rest and are never included in
the public profile representation.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Boolean, DateTime, String, Text, create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


ALLOWED_DIALECTS = {"sqlite", "postgresql", "mysql"}
LOCAL_DB_URI = "sqlite:///data/local.db"


class ConnectionError(ValueError):
    """Raised when a connection profile is invalid or unavailable."""


class Base(DeclarativeBase):
    pass


class ConnectionProfile(Base):
    __tablename__ = "connection_profiles"

    connection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(120))
    dialect: Mapped[str] = mapped_column(String(30))
    encrypted_uri: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def _fernet() -> Fernet:
    raw = os.environ.get("SECRETS_ENCRYPTION_KEY") or os.environ.get("CONNECTION_ENCRYPTION_KEY")
    if not raw:
        # Development fallback is intentionally process-stable only. Production
        # must provide a key or profiles cannot be recovered after restart.
        raw = Fernet.generate_key().decode()
        os.environ["SECRETS_ENCRYPTION_KEY"] = raw
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except Exception as exc:
        raise ConnectionError("SECRETS_ENCRYPTION_KEY must be a valid Fernet key") from exc


def _store_engine() -> Engine:
    uri = os.environ.get("CONNECTION_STORE_URI", "sqlite:///data/connections.db")
    if uri.startswith("sqlite:///"):
        os.makedirs(os.path.dirname(uri.removeprefix("sqlite:///")) or ".", exist_ok=True)
    engine = create_engine(uri)
    Base.metadata.create_all(engine)
    return engine


_metadata_engine: Engine | None = None
_engines: dict[str, Engine] = {}
_lock = RLock()


def metadata_engine() -> Engine:
    global _metadata_engine
    with _lock:
        if _metadata_engine is None:
            _metadata_engine = _store_engine()
        return _metadata_engine


def _validate_uri(uri: str, *, allow_private_hosts: bool = False) -> str:
    if not uri or not uri.strip():
        raise ConnectionError("Database URI is required")
    try:
        parsed = make_url(uri)
    except Exception as exc:
        raise ConnectionError("Invalid database URI") from exc
    if parsed.drivername.split("+")[0] not in ALLOWED_DIALECTS:
        raise ConnectionError("Supported database types are SQLite, PostgreSQL, and MySQL")
    if parsed.drivername == "sqlite" or parsed.drivername.startswith("sqlite+"):
        return uri
    host = parsed.host
    if not host:
        raise ConnectionError("Database URI must include a host")
    if not allow_private_hosts:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 0, type=socket.SOCK_STREAM)}
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
                    raise ConnectionError("Private or local database hosts are not allowed")
        except socket.gaierror as exc:
            raise ConnectionError("Database host could not be resolved") from exc
    return uri


def _dialect(uri: str) -> str:
    return make_url(uri).drivername.split("+")[0]


def test_connection(uri: str, *, allow_private_hosts: bool = False) -> dict[str, Any]:
    validated = _validate_uri(uri, allow_private_hosts=allow_private_hosts)
    engine = create_engine(validated, pool_pre_ping=True, pool_recycle=1800)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"status": "ok", "dialect": _dialect(validated)}
    except SQLAlchemyError as exc:
        raise ConnectionError("Unable to connect to database") from exc
    finally:
        engine.dispose()


def create_profile(*, owner_id: str, name: str, uri: str, provider_id: str | None = None,
                   allow_private_hosts: bool = False, test: bool = True) -> dict[str, Any]:
    if not owner_id:
        raise ConnectionError("owner_id is required")
    if not name or len(name) > 120:
        raise ConnectionError("Connection name must be 1-120 characters")
    validated = _validate_uri(uri, allow_private_hosts=allow_private_hosts)
    health = test_connection(validated, allow_private_hosts=allow_private_hosts) if test else {"status": "unchecked"}
    profile = ConnectionProfile(connection_id=str(uuid4()), owner_id=owner_id, name=name.strip(),
                                dialect=_dialect(validated), encrypted_uri=_fernet().encrypt(validated.encode()).decode(),
                                provider_id=provider_id, last_health_check=datetime.now(timezone.utc) if test else None)
    with Session(metadata_engine(), expire_on_commit=False) as session:
        session.add(profile)
        session.commit()
    return profile_public(profile) | {"health": health}


def profile_public(profile: ConnectionProfile) -> dict[str, Any]:
    return {"connection_id": profile.connection_id, "owner_id": profile.owner_id, "name": profile.name,
            "dialect": profile.dialect, "provider_id": profile.provider_id, "enabled": profile.enabled,
            "last_health_check": profile.last_health_check.isoformat() if profile.last_health_check else None,
            "created_at": profile.created_at.isoformat() if profile.created_at else None}


def list_profiles(owner_id: str) -> list[dict[str, Any]]:
    with Session(metadata_engine(), expire_on_commit=False) as session:
        return [profile_public(p) for p in session.scalars(select(ConnectionProfile).where(ConnectionProfile.owner_id == owner_id)).all()]


def get_profile(connection_id: str, owner_id: str | None = None) -> ConnectionProfile | None:
    with Session(metadata_engine(), expire_on_commit=False) as session:
        profile = session.get(ConnectionProfile, connection_id)
        if profile and owner_id is not None and profile.owner_id != owner_id:
            return None
        return profile


def delete_profile(connection_id: str, owner_id: str) -> bool:
    with Session(metadata_engine(), expire_on_commit=False) as session:
        profile = session.get(ConnectionProfile, connection_id)
        if not profile or profile.owner_id != owner_id:
            return False
        session.delete(profile)
        session.commit()
    with _lock:
        engine = _engines.pop(connection_id, None)
        if engine:
            engine.dispose()
    return True


def get_connection_engine(connection_id: str, *, owner_id: str | None = None) -> Engine:
    profile = get_profile(connection_id, owner_id)
    if not profile or not profile.enabled:
        raise ConnectionError("Unknown or disabled database connection")
    with _lock:
        if connection_id not in _engines:
            try:
                uri = _fernet().decrypt(profile.encrypted_uri.encode()).decode()
            except InvalidToken as exc:
                raise ConnectionError("Stored database credentials cannot be decrypted") from exc
            _engines[connection_id] = create_engine(uri, pool_pre_ping=True, pool_recycle=1800)
        return _engines[connection_id]


def execute_profile_query(connection_id: str, sql: str, *, owner_id: str | None = None) -> list[dict[str, Any]]:
    from sqlalchemy import text
    with get_connection_engine(connection_id, owner_id=owner_id).connect() as conn:
        result = conn.execute(text(sql))
        return [dict(row._mapping) for row in result]


def default_connection_uri() -> str:
    return os.environ.get("DB_URI") or (LOCAL_DB_URI if os.path.exists("data/local.db") else "")
