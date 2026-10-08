"""Provider-neutral LLM construction and encrypted provider secrets."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse
import yaml
from cryptography.fernet import Fernet, InvalidToken
from langchain_groq import ChatGroq
from app.core.config import settings
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

@dataclass(frozen=True)
class ProviderProfile:
    provider_id: str
    owner_id: str
    name: str
    provider_type: str
    api_key: str
    model: str
    base_url: str | None = None
    enabled: bool = True

def _fernet() -> Fernet:
    key = os.getenv("SECRETS_ENCRYPTION_KEY") or os.getenv("CONNECTION_ENCRYPTION_KEY")
    if not key: raise ProviderError("secrets_not_configured", "SECRETS_ENCRYPTION_KEY is not configured")
    try: return Fernet(key.encode())
    except Exception as exc: raise ProviderError("invalid_secrets_key", "Configured secrets key is invalid") from exc

def encrypt_secret(value: str) -> str:
    if not value: raise ValueError("secret cannot be empty")
    return _fernet().encrypt(value.encode()).decode()

def decrypt_secret(value: str) -> str:
    try: return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc: raise ProviderError("invalid_secret", "Stored provider secret cannot be decrypted") from exc

def validate_base_url(base_url: str | None) -> str | None:
    if not base_url: return None
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc: raise ProviderError("invalid_base_url", "Custom provider URL must be an HTTPS URL")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"} or host.endswith(".local"): raise ProviderError("unsafe_base_url", "Custom provider URL targets a private host")
    return base_url.rstrip("/")

def _profile_from_mapping(profile: Mapping[str, Any]) -> ProviderProfile:
    kind = str(profile.get("provider_type", profile.get("type", ""))).lower()
    if kind not in {"groq", "openai", "anthropic", "gemini", "openai_compatible"}: raise ProviderError("unsupported_provider", f"Unsupported provider: {kind}")
    api_key = decrypt_secret(str(profile["encrypted_api_key"])) if profile.get("encrypted_api_key") else profile.get("api_key")
    api_key = str(api_key).strip() if api_key else ""
    if not api_key: raise ProviderError("missing_api_key", "Provider API key is required")
    base_url = decrypt_secret(str(profile["encrypted_base_url"])) if profile.get("encrypted_base_url") else profile.get("base_url")
    if kind == "openai_compatible" and not validate_base_url(base_url): raise ProviderError("missing_base_url", "OpenAI-compatible providers require base_url")
    return ProviderProfile(str(profile.get("provider_id", "default")), str(profile.get("owner_id", "default")), str(profile.get("name", kind)), kind, str(api_key), str(profile.get("model") or ""), base_url, bool(profile.get("enabled", True)))

def get_llm(provider_id: str | None = None, model: str | None = None, profile: ProviderProfile | Mapping[str, Any] | None = None):
    with open("configs/model.yaml") as f: cfg = yaml.safe_load(f) or {}
    if profile is None:
        if provider_id not in (None, "default"):
            try:
                from app.llm.profiles import get_profile
                profile = get_profile(provider_id)
            except Exception:
                profile = None
            if profile is None:
                raise ProviderError("provider_not_found", f"Provider {provider_id} was not resolved")
        if profile is not None:
            p = profile if isinstance(profile, ProviderProfile) else _profile_from_mapping(profile)
        else:
            if not settings.groq_api_key: raise ProviderError("missing_api_key", "GROQ_API_KEY is not configured")
            p = ProviderProfile("default", "default", "Default Groq", "groq", settings.groq_api_key, model or cfg.get("model", "openai/gpt-oss-20b"))
    else:
        p = profile if isinstance(profile, ProviderProfile) else _profile_from_mapping(profile)
        if not p.enabled: raise ProviderError("provider_disabled", "Provider is disabled")
    kwargs = {"model": model or p.model, "temperature": cfg.get("temperature", 0), "max_tokens": cfg.get("max_tokens"), "api_key": p.api_key}
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    if p.provider_type == "groq": return ChatGroq(**kwargs)
    if p.provider_type in {"openai", "openai_compatible"}:
        if ChatOpenAI is None: raise ProviderError("provider_dependency_missing", "langchain-openai is required")
        if p.base_url: kwargs["base_url"] = p.base_url
        return ChatOpenAI(**kwargs)
    if p.provider_type == "gemini":
        if ChatGoogleGenerativeAI is None: raise ProviderError("provider_dependency_missing", "langchain-google-genai is required")
        kwargs["google_api_key"] = kwargs.pop("api_key"); return ChatGoogleGenerativeAI(**kwargs)
    if p.provider_type == "anthropic":
        try: from langchain_anthropic import ChatAnthropic
        except ImportError as exc: raise ProviderError("provider_dependency_missing", "langchain-anthropic is required") from exc
        kwargs["anthropic_api_key"] = kwargs.pop("api_key"); return ChatAnthropic(**kwargs)
    raise ProviderError("unsupported_provider", p.provider_type)

def provider_metadata(profile: ProviderProfile | Mapping[str, Any]) -> dict[str, Any]:
    p = profile if isinstance(profile, ProviderProfile) else _profile_from_mapping(profile)
    return {"provider_id": p.provider_id, "owner_id": p.owner_id, "name": p.name, "provider_type": p.provider_type, "model": p.model, "enabled": p.enabled, "base_url": p.base_url}
