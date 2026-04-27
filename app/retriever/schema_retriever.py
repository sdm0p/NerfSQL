import json

import faiss
import numpy as np
from pinecone import Pinecone
from fastembed import TextEmbedding
from app.core.config import settings

class SchemaRetriever:
    def __init__(self, chunks_path: str = "data/schema_chunks.json", top_k: int = 5):
        self.top_k = top_k
        self.model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        self.pinecone_api_key = settings.pinecone_api_key
        self.pinecone_index_name = settings.pinecone_index_name
        self.pinecone_namespace = settings.pinecone_namespace
        self.pinecone_index = None

        if self.pinecone_api_key:
            try:
                pc = Pinecone(api_key=self.pinecone_api_key)
                self.pinecone_index = pc.Index(self.pinecone_index_name)
            except Exception:
                self.pinecone_index = None

        with open(chunks_path) as f:
            self.chunks: list[str] = json.load(f)
        if self.chunks:
            embeddings = np.array(list(self.model.embed(self.chunks)))
            self.index = faiss.IndexFlatL2(embeddings.shape[1])
            self.index.add(embeddings.astype(np.float32))
        else:
            self.index = None

    def retrieve(self, query: str) -> str:
        vec = np.array(list(self.model.embed([query])), dtype=np.float32)[0]

        if self.pinecone_index is not None:
            try:
                response = self.pinecone_index.query(
                    vector=vec.tolist(),
                    top_k=self.top_k,
                    namespace=self.pinecone_namespace,
                    include_metadata=True,
                )
                matches = response.get("matches") if isinstance(response, dict) else response.matches
                pinecone_chunks = []
                for match in matches:
                    metadata = match.get("metadata", {}) if isinstance(match, dict) else getattr(match, "metadata", {})
                    chunk = metadata.get("chunk")
                    if chunk:
                        pinecone_chunks.append(chunk)
                if pinecone_chunks:
                    return "\n".join(pinecone_chunks)
            except Exception:
                pass

        if not self.index:
            return ""
        _, ids = self.index.search(vec.reshape(1, -1), self.top_k)
        return "\n".join(self.chunks[i] for i in ids[0] if i < len(self.chunks))
