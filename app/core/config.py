import os
from dataclasses import dataclass

from dotenv import load_dotenv


# Load .env once at process startup for all app modules.
load_dotenv(dotenv_path=".env")


@dataclass(frozen=True)
class Settings:
    db_uri: str | None
    groq_api_key: str | None
    pinecone_api_key: str | None
    pinecone_index_name: str
    pinecone_namespace: str
    pinecone_region: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_uri=os.environ.get("DB_URI"),
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            pinecone_api_key=os.environ.get("PINECONE_API_KEY"),
            pinecone_index_name=os.environ.get("PINECONE_INDEX_NAME", "sql-schema-rag"),
            pinecone_namespace=os.environ.get("PINECONE_NAMESPACE", "default"),
            pinecone_region=os.environ.get("PINECONE_REGION", "us-east-1"),
        )


settings = Settings.from_env()
