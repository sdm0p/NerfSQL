import yaml
from langchain_groq import ChatGroq
from app.core.config import settings

def get_llm() -> ChatGroq:
    with open("configs/model.yaml") as f:
        cfg = yaml.safe_load(f)
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    return ChatGroq(
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        api_key=settings.groq_api_key,
    )
