import argparse
import json
import os
import time
from typing import Any

import numpy as np
from pinecone import Pinecone, ServerlessSpec
from fastembed import TextEmbedding
from sqlalchemy import create_engine, inspect

try:
    from app.core.config import settings
except ModuleNotFoundError:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=".env")

    class _ScriptSettings:
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        pinecone_index_name = os.environ.get("PINECONE_INDEX_NAME", "sql-schema-rag")
        pinecone_namespace = os.environ.get("PINECONE_NAMESPACE", "default")
        pinecone_region = os.environ.get("PINECONE_REGION", "us-east-1")

    settings = _ScriptSettings()


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def extract_schema(db_uri: str) -> list[str]:
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    chunks = []
    for table in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns(table)]
        fks = [f"{fk['constrained_columns']} -> {fk['referred_table']}" for fk in inspector.get_foreign_keys(table)]
        chunk = f"Table: {table}\nColumns: {', '.join(cols)}"
        if fks:
            chunk += f"\nForeign keys: {'; '.join(fks)}"
        chunks.append(chunk)
    return chunks


def _list_index_names(pc: Pinecone) -> set[str]:
    indexes: Any = pc.list_indexes()
    if hasattr(indexes, "names"):
        return set(indexes.names())
    names: set[str] = set()
    for idx in indexes:
        if isinstance(idx, dict) and "name" in idx:
            names.add(idx["name"])
        elif hasattr(idx, "name"):
            names.add(idx.name)
    return names


def upsert_schema_chunks_to_pinecone(
    chunks: list[str],
    index_name: str,
    namespace: str,
    region: str,
    api_key: str,
) -> int:
    if not chunks:
        return 0

    model = TextEmbedding(EMBEDDING_MODEL)
    embeddings = np.array(list(model.embed(chunks)), dtype=np.float32)
    dimension = int(embeddings.shape[1])

    pc = Pinecone(api_key=api_key)
    if index_name not in _list_index_names(pc):
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=region),
        )

    for _ in range(30):
        status = pc.describe_index(index_name).status
        ready = status.get("ready") if isinstance(status, dict) else getattr(status, "ready", False)
        if ready:
            break
        time.sleep(1)
    else:
        raise RuntimeError(f"Pinecone index '{index_name}' is not ready")

    index = pc.Index(index_name)
    vectors = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=False)):
        vectors.append(
            {
                "id": f"schema-{i}",
                "values": emb.tolist(),
                "metadata": {"chunk": chunk},
            }
        )

    batch_size = 100
    for start in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[start : start + batch_size], namespace=namespace)

    return len(vectors)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db_uri", required=True)
    parser.add_argument("--output", default="data/schema_chunks.json")
    parser.add_argument("--pinecone_index", default=settings.pinecone_index_name)
    parser.add_argument("--pinecone_namespace", default=settings.pinecone_namespace)
    parser.add_argument("--pinecone_region", default=settings.pinecone_region)
    parser.add_argument("--skip_pinecone", action="store_true")
    args = parser.parse_args()

    chunks = extract_schema(args.db_uri)
    with open(args.output, "w") as f:
        json.dump(chunks, f, indent=2)
    print(f"Wrote {len(chunks)} schema chunks to {args.output}")

    if args.skip_pinecone:
        print("Skipped Pinecone upsert")
    else:
        api_key = settings.pinecone_api_key
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY is required unless --skip_pinecone is used")
        upserted = upsert_schema_chunks_to_pinecone(
            chunks=chunks,
            index_name=args.pinecone_index,
            namespace=args.pinecone_namespace,
            region=args.pinecone_region,
            api_key=api_key,
        )
        print(
            f"Upserted {upserted} schema vectors to Pinecone index '{args.pinecone_index}' namespace '{args.pinecone_namespace}'"
        )
