# NerfSQL

**Schema-aware, self-correcting Text-to-SQL pipeline using LangGraph + Groq**

---

## Overview

NerfSQL is a schema-aware text-to-SQL system that converts natural language queries into executable SQL, validates them against a live database, and iteratively corrects errors until a valid result is produced.

The system uses:

- Retrieval-Augmented Generation (RAG) over database schema
- A constrained LLM loop for SQL generation and correction
- Execution-based validation against a real database
- Stateful orchestration via LangGraph
- Fast inference using Groq models

---

## Key Features

### TOON-Based LLM I/O

- LLM-facing schema context is serialized in **TOON** (Token-Oriented Object Notation)
- SQL generation and correction prompts require TOON responses with a `sql` field
- Internal parser extracts SQL deterministically from TOON output

### 1. Schema-Aware Retrieval

- Embeds database schema (tables, columns, relationships)
- Retrieves only relevant schema chunks per query
- Avoids context overflow and irrelevant joins

---

### 2. Controlled SQL Generation

- Generates SQL using filtered schema context
- Supports multiple dialects (PostgreSQL, MySQL, etc.)
- Enforces read-only constraints (no `DROP`, `DELETE`, etc.)

---

### 3. Execution-Based Validation

- Runs generated SQL on a live database
- Captures:
  - syntax errors
  - missing columns/tables
  - invalid joins

---

### 4. Self-Correcting Loop (Bounded)

- Parses DB errors and feeds them back to the LLM
- Iteratively refines queries
- Stops after a configurable retry limit

---

### 5. Deterministic Guardrails

- Query sanitizer blocks destructive operations
- Schema validator checks table/column existence pre-execution
- Retry budget prevents infinite loops

---

### 6. Observability

- Full execution trace via LangGraph state
- Logs:
  - retrieved schema
  - generated SQL per iteration
  - errors and corrections

---

## Architecture

```
User Query
   │
   ▼
Schema Retriever (Vector DB)
   │
   ▼
SQL Generator (LLM)
   │
   ▼
Pre-Execution Validator
   │
   ▼
SQL Execution (DB)
   │
   ├── Success ───────────────► Return Result
   │
   ▼
Error Parser
   │
   ▼
Correction Loop (LLM)
   │
   └── Retry (bounded)
```

---

## Tech Stack

- **Orchestration:** LangGraph
- **LLM Inference:** Groq
- **Embeddings:** SentenceTransformers / OpenAI-compatible
- **Vector Store:** Pinecone (primary) + FAISS fallback
- **Database:** PostgreSQL / MySQL / SQLite
- **Backend:** Python (FastAPI optional)

---

## Project Structure

```
NerfSQL/
│
├── app/
│   ├── graph/              # LangGraph nodes and edges
│   ├── retriever/          # Schema embedding + retrieval
│   ├── llm/                # Groq client + prompts
│   ├── db/                 # DB connection + execution
│   ├── validators/         # SQL + schema validation
│   ├── utils/              # logging, parsing, helpers
│
├── configs/
│   ├── model.yaml
│   ├── db.yaml
│
├── data/
│   ├── schema_chunks.json
│
├── tests/
│   ├── eval_queries.json   # input + expected outputs
│
├── scripts/
│   ├── ingest_schema.py
│
├── README.md
└── requirements.txt
```

---

## Installation

```bash
git clone https://github.com/sdm0p/NerfSQL.git
cd NerfSQL

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## Configuration

### Environment Variables

```bash
GROQ_API_KEY=your_key
DB_URI=sqlite:///data/local.db
PINECONE_API_KEY=your_key
PINECONE_INDEX_NAME=sql-schema-rag
PINECONE_NAMESPACE=default
PINECONE_REGION=us-east-1
```

---

### Schema Ingestion

Create and seed the local SQLite database from the provided sustainability schema:

```bash
python scripts/create_sample_db.py
```

```bash
python scripts/ingest_schema.py \
  --db_uri $DB_URI \
  --output data/schema_chunks.json
```

Optional flags:

```bash
python scripts/ingest_schema.py \
   --db_uri $DB_URI \
   --output data/schema_chunks.json \
   --pinecone_index $PINECONE_INDEX_NAME \
   --pinecone_namespace $PINECONE_NAMESPACE \
   --pinecone_region $PINECONE_REGION
```

This will:

- Extract tables, columns, relationships
- Chunk schema
- Generate embeddings

---

## Usage

### Run Query

```python
from app.main import query_agent

response = query_agent(
    question="Get top 5 customers by revenue in last 3 months"
)

print(response.sql)
print(response.result)
```

---

### Example Flow

**Input:**

```
"Show total travel emissions per user in April 2026"
```

**System:**

1. Retrieves relevant tables (`travel_entries`, `users`, `emission_factors`)
2. Generates SQL
3. Executes → error (wrong column)
4. Corrects query
5. Executes successfully

---

## Evaluation

Run benchmark queries:

```bash
python -m tests.run_eval
```

For reproducible RAG-versus-full-schema metrics across 55 labeled cases, token
usage, hallucination rate, latency percentiles, and free load testing, see
[`BENCHMARK.md`](BENCHMARK.md).

Metrics:

- Execution success rate
- Query correctness
- Retry count
- Latency per query

---

## Guardrails

- Blocks:
  - `DROP`, `DELETE`, `TRUNCATE`, `ALTER`

- Enforces:
  - read-only queries
  - schema-constrained SQL

- Retry limit:
  - default: 3 attempts

---

## Limitations

- LLM hallucination still possible (reduced, not eliminated)
- Complex joins across large schemas may degrade accuracy
- Performance depends on schema quality and indexing
- Groq-hosted models may struggle with deeply nested queries

---

## Future Work

- Cost-based query optimization feedback
- Fine-tuned text-to-SQL model
- UI for query tracing and debugging
- Support for multi-database federation
- Reinforcement learning from execution feedback

---

## Why This Project Exists

Most text-to-SQL demos fail because they:

- ignore schema scale
- lack validation
- rely on single-pass generation

This project focuses on:

- **correctness over novelty**
- **bounded autonomy over blind generation**
- **real execution over synthetic examples**

---

## License

MIT License

---

## Final Note

This is not a “one-shot LLM demo.”
It is a constrained system that treats LLMs as unreliable components and compensates accordingly.
