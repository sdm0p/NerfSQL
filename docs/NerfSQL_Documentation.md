# NerfSQL: Schema-aware, Self-correcting Text-to-SQL Pipeline

## Executive Summary

NerfSQL is an advanced Text-to-SQL system that converts natural language queries into executable SQL statements with high accuracy through schema awareness, execution-based validation, and iterative self-correction. Unlike typical LLM-based Text-to-SQL approaches that rely on single-pass generation, NerfSQL treats the LLM as an unreliable component and implements robust validation and correction mechanisms to ensure correctness.

## Core Innovation

The key innovation lies in NerfSQL's bounded autonomy approach: rather than blindly trusting LLM outputs, the system validates every generated SQL against a live database, captures execution errors, and feeds them back to the LLM for correction within a bounded retry loop. This execution-based validation significantly reduces hallucinations and improves reliability.

## Detailed Architecture

### System Overview
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

### Component Breakdown

#### 1. Schema Retriever
- **Purpose**: Retrieves only relevant schema chunks for a given query to avoid context overflow
- **Technology**:
  - Embeddings: SentenceTransformers (all-MiniLM-L6-v2) via FastEmbed
  - Vector Stores: Pinecone (primary) with FAISS fallback
  - Chunking: Database schema is pre-chunked by table (Table name, Columns, Foreign Keys)
- **Process**:
  1. Embed user query
  2. Retrieve top-K most relevant schema chunks
  3. Return concatenated schema context

#### 2. SQL Generator (with TOON)
- **Technology**: Groq-hosted Llama 3.3 70B Versatile model
- **Innovation - TOON (Token-Oriented Object Notation)**:
  - Schema context is serialized in TOON format for LLM consumption
  - LLM must respond with TOON object containing a `sql` field
  - Deterministic parser extracts SQL from TOON output
- **Benefits**:
  - Structured LLM I/O reduces parsing ambiguity
  - Enables reliable extraction of SQL from LLM responses

#### 3. Pre-Execution Validator
- **SQL Guardrails**:
  - Blocks destructive operations (`DROP`, `DELETE`, `TRUNCATE`, `ALTER`)
  - Enforces read-only query constraint
  - Basic syntax validation
- **Semantic Validation**:
  - LLM-based validation to check if generated SQL can answer the question given available schema
  - Prevents execution of semantically invalid queries

#### 4. Execution Engine
- **Database Support**: PostgreSQL, MySQL, SQLite (configurable via DB_URI)
- **Connection**: SQLAlchemy engine with connection pooling
- **Safety**: All queries executed in read-only mode when possible

#### 5. Self-Correcting Loop
- **Error Parsing**: Captures database execution errors (syntax, missing tables/columns, etc.)
- **Correction Prompt**: Feeds error + original schema + question back to LLM
- **Bounded Retry**: Configurable retry limit (default: 3 attempts) prevents infinite loops
- **State Management**: LangGraph maintains execution state across iterations

#### 6. Observability & Tracing
- **LangGraph Integration**: Full execution trace available
- **Logging**:
  - Retrieved schema per iteration
  - Generated SQL per attempt
  - Errors and corrections applied
  - Retry counts and final outcomes
- **Session Tracking**: Maintains chat history for conversational context

## Technical Implementation Details

### Data Flow
1. User submits natural language question
2. System loads environment and initializes singleton services (LLM, Retriever, Session Manager)
3. Schema relevant to query is retrieved from vector store
4. Initial state created: `{question, schema, sql="", result=None, error=None, retries=0}`
5. LangGraph executes workflow:
   - Generate SQL from schema+question using LLM (TOON-constrained)
   - Normalize and extract SQL from LLM response
   - Validate SQL safety (no destructive operations)
   - Semantic validation (can this SQL answer the question?)
   - Execute SQL against live database
   - If error and retries < max: feed error back to LLM for correction
   - If success or max retries reached: return result

### Key Files & Modules
- `app/main.py`: Entry point with `query_agent()` function
- `app/graph/nodes.py`: LangGraph node implementations (generate, validate, execute, correct)
- `app/graph/graph.py`: Workflow definition with conditional edges
- `app/retriever/schema_retriever.py`: Hybrid Pinecone/FAISS retrieval
- `app/utils/toon.py`: TOON serialization/deserialization and SQL extraction
- `app/llm/prompts.py`: Prompt templates for generation, correction, validation
- `app/validators/sql_guard.py`: SQL injection prevention and operation blocking

### Configuration
- **Environment Variables**:
  - `GROQ_API_KEY`: For LLM inference
  - `DB_URI`: Database connection string (e.g., `sqlite:///data/local.db`)
  - `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, etc.: For vector storage
- **Model Config** (`configs/model.yaml`):
  ```yaml
  model: llama-3.3-70b-versatile
  temperature: 0
  max_tokens: 1024
  ```

## Why This Approach Works

### Problems with Traditional Text-to-SQL
1. **Hallucination**: LLMs generate syntactically valid but semantically incorrect SQL
2. **Schema Ignorance**: LLMs struggle with large, complex schemas
3. **Single-Point Failure**: No mechanism to recover from generation errors
4. **Synthetic Evaluation**: Many systems test on clean, academic datasets

### NerfSQL's Solutions
1. **Execution-Based Validation**: Ground truth comes from actual database execution
2. **Schema Grounding**: Retrieval ensures LLM only sees relevant schema portions
3. **Iterative Refinement**: Errors are converted into feedback for improvement
4. **Real-World Focus**: Built and tested on actual database instances
5. **Defensive Design**: Multiple layers of validation prevent harmful operations

## Example Workflow

**Question**: "Show total travel emissions per user in April 2026"

1. **Retrieval**: System fetches schema for `travel_entries`, `users`, `emission_factors`
2. **Generation**: LLM produces initial SQL (may have errors)
3. **Execution**:
   - Attempt 1: SQL fails due to wrong column name (`date` vs `travel_date`)
   - Error captured: "no such column: date"
4. **Correction**:
   - Error + schema + question fed back to LLM
   - LLM generates corrected SQL with proper column
5. **Execution**:
   - Attempt 2: SQL executes successfully
   - Returns aggregated emissions per user for April 2026
6. **Return**: Final result sent to user

## Evaluation Methodology

### Benchmark Suite
Stored in `tests/eval_queries.json` with question→expected SQL pairs:
- "List all users and their country codes"
- "Show total travel emissions per user"
- "Which household had the highest total CO2e in April 2026?"
- "Get recommendations with estimated impact for each user"
- "How much electricity did each household consume in March 2026?"

### Metrics Tracked
1. **Execution Success Rate**: % of queries that run without database errors
2. **Query Correctness**: % of successful queries that match expected semantics
3. **Retry Count**: Average iterations needed for success
4. **Latency**: End-to-end time per query
5. **Error Types**: Categorization of failures (syntax, semantic, schema)

## Guardrails & Safety

### Hard Constraints
- **Operation Blocking**: `DROP`, `DELETE`, `TRUNCATE`, `ALTER` always blocked
- **Read-Only Enforcement**: System designed for querying only
- **Schema Validation**: Tables/columns verified against retrieved schema before execution
- **Retry Bounding**: Prevents infinite loops (default max: 3 attempts)

### Soft Constraints
- **Semantic Validation**: LLM checks if SQL can possibly answer the question
- **Timeout Protection**: Database query timeouts configured
- **Resource Limits**: Result set size limitations to prevent memory exhaustion

## Limitations & Mitigations

### Known Limitations
1. **LLM Hallucination**: Reduced but not eliminated (mitigated by validation loop)
2. **Complex Join Performance**: Accuracy may degrade with very large schemas (mitigated by targeted retrieval)
3. **Embedding Quality**: Depends on schema documentation quality (mitigated by hybrid retrieval)
4. **Model Constraints**: Groq-hosted models may struggle with deeply nested queries (mitigated by correction loop)

### Future Work
- Cost-based query optimization feedback integration
- Fine-tuned domain-specific text-to-SQL model
- Interactive UI for query tracing and debugging
- Multi-database federation capabilities
- Reinforcement learning from execution feedback
- Advanced semantic validation using database constraints

## Comparison to Alternatives

| Feature | Traditional LLM Text-to-SQL | NerfSQL |
|---------|----------------------------|---------|
| Schema Awareness | Often full schema passed | Targeted retrieval |
| Validation | Syntactic only | Execution + semantic |
| Error Handling | None | Iterative correction |
| Safety | Minimal | Multi-layer guardrails |
| Observability | Basic | Full LangGraph tracing |
| Reliability | Low-Medium | High (bounded autonomy) |
| Real-world Testing | Rare | Core to design |

## Getting Started

### Installation
```bash
git clone https://github.com/sdm0p/NerfSQL.git
cd NerfSQL
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or .\venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Configuration
1. Set environment variables:
   ```bash
   export GROQ_API_KEY="your_groq_key"
   export DB_URI="sqlite:///data/local.db"
   export PINECONE_API_KEY="your_pinecone_key"  # Optional
   export PINECONE_INDEX_NAME="sql-schema-rag"
   ```
2. Initialize database and schema:
   ```bash
   python scripts/create_sample_db.py
   python scripts/ingest_schema.py --db_uri $DB_URI --output data/schema_chunks.json
   ```

### Usage
```python
from app.main import query_agent

response = query_agent(
    question="Get top 5 customers by revenue in last 3 months"
)

print(f"Generated SQL: {response.sql}")
print(f"Query Result: {response.result}")
print(f"Retries Needed: {response.retries}")
```

## Conclusion

NerfSQL represents a pragmatic approach to building reliable Text-to-SQL systems by embracing the inherent limitations of LLMs and compensating with robust validation and correction mechanisms. Its execution-centric design ensures that only database-verified SQL is returned to users, making it suitable for production environments where correctness is paramount.

The system demonstrates how combining modern LLM capabilities with traditional software engineering principles (validation, error handling, observability) can create AI systems that are both powerful and trustworthy.
