# NerfSQL — Interview Documentation

---

## 1. What is NerfSQL? (30-second pitch)

NerfSQL is a backend system that takes a plain English question like *"Show total travel emissions per user in April 2026"* and converts it into a valid SQL query, runs it against a real database, and returns the result.

What makes it different from a simple LLM call is that it **validates and self-corrects**. If the generated SQL fails, the system automatically feeds the error back to the LLM and retries — up to 3 times — before giving up. It also uses RAG (Retrieval-Augmented Generation) so the LLM only sees the relevant parts of the schema, not the entire database.

---

## 2. Architecture — How It Works End to End

```
User Question (natural language)
        │
        ▼
Schema Retriever          ← Embeds question, finds relevant tables via FAISS / Pinecone
        │
        ▼
SQL Generator (LLM)       ← Groq LLM generates SQL using only retrieved schema
        │
        ▼
Semantic Validator (LLM)  ← Checks if SQL actually answers the question
        │
        ▼
Safety Guard              ← Blocks DROP, DELETE, TRUNCATE, ALTER, INSERT, UPDATE
        │
        ▼
SQL Executor (SQLAlchemy) ← Runs query on real DB
        │
   ┌────┴────┐
Success    Error
   │          │
Return     Error Parser → Correction LLM → Retry (max 3)
Result
```

---

## 3. Component-by-Component Breakdown

### 3.1 Schema Retriever (`app/retriever/schema_retriever.py`)

- Loads `data/schema_chunks.json` — a list of table descriptions (table name, columns, foreign keys)
- Uses **FastEmbed** with `sentence-transformers/all-MiniLM-L6-v2` to embed all chunks at startup
- Builds a **FAISS** in-memory vector index over those embeddings
- On each query, embeds the user question and does a nearest-neighbor search (top 5 chunks)
- **Primary**: tries Pinecone first if API key is configured
- **Fallback**: uses local FAISS if Pinecone is unavailable or fails
- Returns only the relevant table descriptions as a string — not the full schema

**Why RAG here?** If you have 50 tables and pass all of them to the LLM, you waste tokens and confuse the model. RAG gives it only what it needs.

---

### 3.2 LangGraph Orchestration (`app/graph/`)

The pipeline is a **stateful graph** built with LangGraph. Each node is a pure function that takes state and returns updated state.

**State object (`AgentState`):**
```
question  → original user question
schema    → retrieved schema chunks
sql       → current generated SQL
result    → query result rows
error     → last error message
retries   → retry count
```

**Nodes:**
| Node | What it does |
|------|-------------|
| `generate_sql` | Calls Groq LLM with schema + question, extracts SQL from TOON response |
| `validate_sql_semantic` | Asks LLM if the SQL actually answers the question — returns VALID/INVALID |
| `validate_and_execute` | Runs safety guard, then executes SQL on DB via SQLAlchemy |
| `correct_sql` | Feeds SQL + error back to LLM, asks it to fix the query |

**Edges:**
- `generate → validate → execute`
- `execute → correct` (if error and retries < 3)
- `execute → END` (if success or retries exhausted)
- `correct → validate` (loops back, not directly to execute)

---

### 3.3 LLM Client (`app/llm/client.py`)

- Uses **Groq** via `langchain-groq` — Groq provides very fast inference (low latency)
- Model config (name, temperature, max_tokens) loaded from `configs/model.yaml`
- Temperature is kept low for deterministic SQL output

---

### 3.4 Prompts (`app/llm/prompts.py`)

Three prompts:

**GENERATE_PROMPT** — Given schema in TOON format + question, generate SQL. Returns `sql: SELECT ...`

**CORRECT_PROMPT** — Given broken SQL + error message + schema, fix the SQL. Same output format.

**VALIDATE_PROMPT** — Given question + SQL + available tables, respond with exactly `VALID` or `INVALID`.

---

### 3.5 TOON Parsing (`app/utils/toon.py`)

- TOON (Token-Oriented Object Notation) is a lightweight key-value format the LLM responds in
- Example response: `sql: SELECT * FROM users WHERE user_id = 1;`
- `extract_sql_from_toon()` parses this deterministically — with multiple fallback regex patterns for when the LLM doesn't follow format perfectly
- `schema_text_to_toon()` converts the retrieved schema chunks into TOON format before sending to LLM

---

### 3.6 Safety Guard (`app/validators/sql_guard.py`)

- Single regex check: blocks `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `INSERT`, `UPDATE`
- Enforces read-only access — the system can never modify or destroy data
- Runs before every SQL execution

---

### 3.7 Database Engine (`app/db/engine.py`)

- Uses **SQLAlchemy** with a lazy singleton engine
- Tries `DB_URI` from `.env` first, falls back to `data/local.db` if it exists
- `execute_query()` returns results as a list of dicts

---

### 3.8 Session Manager (`app/core/session.py`)

- In-memory, thread-safe session store using Python's `threading.Lock`
- Each chat session has a UUID `chat_id`
- Stores: first query (immutable) + sliding window of last 4 queries + last 4 responses
- Sessions live only for the lifetime of the server process (no DB persistence)

---

### 3.9 FastAPI Layer (`app/api.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/ingest` | POST | Extract schema from DB, save to JSON, optionally upsert to Pinecone |
| `/schema` | GET | View currently ingested schema chunks |
| `/query` | POST | Run a natural language query |
| `/history` | GET | List all active chat sessions |
| `/history/{chat_id}` | GET | Get full conversation history for a session |

Middleware stack: GZip → TrustedHost → CORS → SecurityHeaders (X-Frame-Options, CSP, etc.)

---

## 4. Tech Stack — Why Each Tool Was Chosen

| Tool | Why |
|------|-----|
| **LangGraph** | Stateful graph with conditional edges — perfect for retry loops. Better than plain LangChain chains for branching logic |
| **Groq** | Fastest LLM inference available. Low latency matters when you might retry 3 times |
| **FastEmbed** | Lightweight, no GPU needed, runs locally. Good for embedding schema chunks |
| **FAISS** | In-memory vector search, zero infrastructure. Fast for small schema sizes |
| **Pinecone** | Cloud vector DB for production — persists embeddings across restarts |
| **SQLAlchemy** | DB-agnostic — works with SQLite, PostgreSQL, MySQL without code changes |
| **FastAPI** | Async, auto-docs, Pydantic validation out of the box |

---

## 5. Database Schema (Personal Carbon Footprint)

12 tables:

- **users** — user accounts
- **households** — household groups
- **household_members** — many-to-many users ↔ households
- **emission_factors** — CO2e per unit for each activity type (car/km, beef/kg, etc.)
- **travel_entries** — travel activity logs
- **electricity_entries** — electricity billing records
- **food_entries** — food consumption logs
- **waste_entries** — waste disposal logs
- **purchase_entries** — purchase activity logs
- **goals** — user-defined emission reduction goals
- **calculation_runs** — periodic total CO2e calculations
- **recommendations** — system-generated suggestions

---

## 6. Interview Q&A

---

### Q: Why not just send the full schema to the LLM every time?

**A:** Two reasons. First, large schemas exceed context windows or get expensive fast. Second, irrelevant tables confuse the LLM — it might join tables that have nothing to do with the question. RAG retrieval gives the model only what it needs, which improves accuracy and reduces token cost.

---

### Q: What happens if the LLM generates wrong SQL?

**A:** The SQL gets executed against the real database. If it throws an error, the error message is captured and passed back to the LLM via the `CORRECT_PROMPT` along with the broken SQL and the schema. The LLM fixes it and we retry. This loop runs up to 3 times (MAX_RETRIES). If it still fails after 3 attempts, we return the last error to the user.

---

### Q: How does the semantic validator work?

**A:** After SQL is generated, before execution, we ask the LLM a second question: "Does this SQL actually answer what the user asked?" We give it the question, the SQL, and the list of available tables. It responds with exactly `VALID` or `INVALID`. If invalid, we skip execution entirely and return an error — this prevents wasted DB calls for completely wrong queries like asking about bank transactions when the DB only has carbon footprint data.

---

### Q: Why LangGraph instead of just writing a loop?

**A:** LangGraph gives you a proper state machine with named nodes and conditional edges. The graph is inspectable, the state is typed, and the flow is explicit. A plain loop would work but you lose observability — you can't easily trace which node failed or add new nodes without restructuring the code. LangGraph also makes it easy to add parallelism or checkpointing later.

---

### Q: What's TOON and why use it?

**A:** TOON (Token-Oriented Object Notation) is a simple key-value format — like `sql: SELECT ...`. We use it because asking the LLM to return JSON often fails (it wraps things in markdown, adds extra text, etc.). TOON is simpler for the LLM to follow and easier to parse deterministically. We have multiple fallback regex patterns in `extract_sql_from_toon()` to handle cases where the LLM still doesn't follow the format exactly.

---

### Q: How do you prevent the LLM from dropping tables or deleting data?

**A:** Two layers. First, the `is_safe()` function in `sql_guard.py` runs a regex against every SQL string before execution — it blocks `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `INSERT`, `UPDATE`. Second, the generate prompt explicitly says "write a single read-only SQL query." The guard is the hard enforcement; the prompt is the soft guidance.

---

### Q: What's the difference between FAISS and Pinecone here?

**A:** FAISS is an in-memory vector index — it's fast, requires no external service, but data is lost when the server restarts. Pinecone is a managed cloud vector database — embeddings persist, it scales, and it supports namespaces. The system tries Pinecone first if an API key is configured, and falls back to FAISS if Pinecone is unavailable. For local development, FAISS is sufficient.

---

### Q: How does the session/chat history work?

**A:** Each conversation gets a UUID `chat_id`. The `SessionManager` stores sessions in a Python dict with a threading lock for thread safety. It keeps the first query immutable (for context) and a sliding window of the last 4 queries and 4 responses using `collections.deque(maxlen=4)`. Sessions are in-memory only — they don't survive a server restart. To continue a conversation, the client passes `?chat_id=<uuid>` in the query request.

---

### Q: Why SQLAlchemy instead of raw sqlite3?

**A:** SQLAlchemy is DB-agnostic. The same code works with SQLite for local dev, PostgreSQL for production, and MySQL if needed — just change the `DB_URI` environment variable. With raw sqlite3 you'd have to rewrite the connection layer for each database.

---

### Q: What are the limitations of this system?

**A:** Honest answer:
1. LLM hallucination is reduced but not eliminated — the model can still generate plausible-looking but wrong SQL
2. Complex multi-table joins with ambiguous column names can confuse the model
3. Sessions are in-memory — a server restart loses all chat history
4. The retry loop adds latency — 3 retries means 3 LLM calls which can take several seconds
5. Schema retrieval is based on semantic similarity — if the question uses very different vocabulary from the schema, relevant tables might not be retrieved

---

### Q: How would you scale this to production?

**A:** Several changes:
1. Replace in-memory sessions with Redis or a DB-backed store
2. Use Pinecone (already supported) instead of FAISS for persistent embeddings
3. Add async LLM calls — currently the endpoint blocks a thread per request
4. Add a caching layer for repeated identical questions
5. Add rate limiting on the `/query` endpoint
6. Move to a fine-tuned text-to-SQL model for better accuracy on complex queries

---

### Q: Walk me through what happens when I call POST /query

**A:**
1. FastAPI receives the request, validates the `QueryRequest` body (Pydantic)
2. `query_agent()` is called — creates a new session or appends to existing one
3. `SchemaRetriever.retrieve()` embeds the question and finds top-5 relevant schema chunks
4. LangGraph graph is invoked with initial state (question + schema)
5. `generate_sql` node: LLM generates SQL from schema + question
6. `validate_sql_semantic` node: LLM checks if SQL is semantically correct
7. `validate_and_execute` node: safety guard runs, then SQLAlchemy executes the query
8. If success → state flows to END, result returned
9. If error → `should_retry` routes to `correct_sql` node, LLM fixes SQL, loops back to validate
10. After max 3 retries or success, response is recorded in session and returned to client

---

## 7. Things to Say Confidently

- "I used LangGraph because it gives me a proper state machine — I can add nodes, change routing logic, and trace execution without rewriting the loop"
- "The RAG layer is what makes this practical — without it, you'd be sending 50 table definitions to the LLM every single time"
- "The self-correction loop is bounded — MAX_RETRIES = 3 — because an unbounded loop would be a reliability risk"
- "FAISS and Pinecone serve different purposes — FAISS for local/dev, Pinecone for production persistence"
- "The safety guard is deterministic — it doesn't rely on the LLM to be safe, it enforces it with a regex"

---

## 8. Things to Avoid Saying

- Don't say "it always works" — LLMs are probabilistic, be honest about limitations
- Don't say "I built this from scratch in a day" — be honest that you studied the architecture and understand it deeply
- Don't overclaim on the RAG — it retrieves top-5 chunks by similarity, it's not perfect

---
