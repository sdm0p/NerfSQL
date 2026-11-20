# NerfSQL project structure

This layout keeps the existing `app` import path intact. That is important because
Docker, Render, Vercel, tests, and the queue worker all import `app.api` or one of
its subpackages.

```text
NerfSQL/
├── app/                         # Runtime Python package
│   ├── api.py                   # FastAPI routes and middleware
│   ├── main.py                  # Query orchestration and session integration
│   ├── core/                    # Settings and session state
│   ├── graph/                   # LangGraph state, nodes, and transitions
│   ├── db/                      # SQLAlchemy engines, profiles, execution
│   ├── llm/                     # Provider factory, profiles, prompts
│   ├── retriever/               # Pinecone/FAISS schema retrieval
│   ├── validators/              # Read-only SQL safety checks
│   ├── utils/                   # TOON parsing and shared helpers
│   └── queue.py                 # Upstash seed-job queue
├── api/                         # Vercel adapter; re-exports app.api:app
├── frontend/                    # Static browser client served by FastAPI
├── scripts/                     # Operational jobs, schema ingestion, demo data
├── tests/                       # Unit, integration, benchmark, and load tests
├── configs/                     # Model and database configuration
├── data/                        # Local demo database and request collections
│   └── seed/                    # SQL seed/schema files
├── docs/                        # Project, interview, and API documentation
│   ├── api/                     # Postman/Bruno API collections
│   └── interview/               # Interview preparation notes
├── artifacts/                   # Generated handbook deliverables
├── tmp/                         # Local render/build scratch files (ignored)
├── Dockerfile                   # Render/container entry point
├── docker-compose.yml           # Local container + persistent data volume
├── render.yaml                  # Render deployment configuration
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Test/development dependencies
├── Readme.md                    # Setup and usage guide
└── .env.example                 # Environment variable template
```

## Runtime flow

```text
frontend → app.api → app.main → app.graph → app.llm / app.db
                         │             └→ app.retriever
                         └→ app.core.session
```

The graph remains the only place that controls the generate → validate → execute
→ correct loop. Database and provider implementations stay behind their existing
interfaces, so adding structure does not change API behavior.

## Compatibility rules

- Keep `app.api:app` as the ASGI entry point.
- Keep `api/index.py` as the Vercel adapter.
- Keep `scripts.ingest_schema` importable because API routes and tests use it.
- Keep `app.graph`, `app.llm`, and `app.db` package names stable.
- Put new runtime code inside an existing domain package rather than creating
  duplicate copies of the same service.
- Put one-off maintenance code in `scripts/`, and tests in `tests/`; neither is
  imported by the production request path except for explicit jobs.
- Keep generated scratch output under `tmp/`; it is not source code and should
  not be committed.
