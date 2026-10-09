# NerfSQL reproducible metrics

The benchmark contains 55 labeled scenarios: 20 single-table questions, 30 join or aggregation questions, and 5 deliberately unanswerable questions. It compares connection-scoped Pinecone retrieval (`rag`) with the complete selected database schema (`full`).

## What is measured

- Semantic accuracy: required tables and expected result values are present.
- Hallucination rate: generated SQL references an unavailable table, or an unanswerable question returns data.
- Token consumption: input tokens reported by the LLM provider across generation, semantic validation, and correction calls.
- Retry count and LLM-call count.
- End-to-end p50, p95, and p99 latency.

The files under `benchmark-results/` are generated evidence and should include the model, timestamp, connection, and configuration when results are reported publicly.

## Free-tier benchmark

First deploy the current API and ensure the `sd` connection is present and its schema has been refreshed into Pinecone. Then run:

```powershell
.\venv\Scripts\python.exe tests\run_metrics.py `
  --base-url https://nerfsql-demo.onrender.com `
  --connection-name sd `
  --modes rag full `
  --delay 10 `
  --max-attempts 3
```

Use a small smoke run before the complete run:

```powershell
.\venv\Scripts\python.exe tests\run_metrics.py --connection-name sd --limit 3 --delay 2
```

The runner writes:

- `benchmark-results/metrics.json`: case-level evidence.
- `benchmark-results/REPORT.md`: résumé-friendly aggregate metrics.

Provider free-tier rate limits can interrupt a complete run. The runner backs off on HTTP 429 responses. Increase `--delay`, keep the JSON evidence, and rerun when the quota resets. Provider failures are evidence of an incomplete run, never accuracy or hallucination results.

## Free infrastructure load test

Install development dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run 100 virtual users against lightweight endpoints:

```powershell
.\venv\Scripts\locust.exe -f tests\locustfile.py `
  --headless --users 100 --spawn-rate 10 --run-time 2m `
  --host https://nerfsql-demo.onrender.com `
  --csv benchmark-results\load
```

This load test supports claims about API and schema endpoint concurrency. It does not support a claim that 100 concurrent LLM queries complete below 200 ms.

For a small LLM-query load test, set `BENCHMARK_CONNECTION_ID` and `LOCUST_QUERY_TEST=1`, then use two to five users. Watch the provider's free-tier limits.

## Claim rules

Only publish a metric produced by a completed report. State the tested model and dataset. End-to-end `/query` latency must be reported separately from `/health`, `/connections`, and `/schema` latency.
