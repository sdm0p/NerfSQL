"""Free-tier friendly RAG vs full-schema benchmark for the deployed API."""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ALLOWED_TABLES = {"customers", "products", "orders", "order_items"}


def request_json(base_url: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode())
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, {"error": str(exc)}
    except URLError as exc:
        return 0, {"error": str(exc)}


def run_query_with_backoff(base_url: str, payload: dict, max_attempts: int) -> tuple[int, dict, float]:
    total_started = time.perf_counter()
    status, response = 0, {}
    for attempt in range(1, max_attempts + 1):
        status, response = request_json(base_url, "/query", payload)
        if status != 429:
            break
        if attempt < max_attempts:
            wait_seconds = 60 * attempt
            print(f"  provider rate limit; waiting {wait_seconds}s before retry {attempt + 1}/{max_attempts}")
            time.sleep(wait_seconds)
    return status, response, round((time.perf_counter() - total_started) * 1000, 2)


def normalized_blob(rows: list) -> str:
    return json.dumps(rows, sort_keys=True, default=str).lower().replace(".0", "")


def tables_in_sql(sql: str) -> set[str]:
    return {name.lower() for name in re.findall(r"(?:from|join)\s+([a-zA-Z_][\w.]*)", sql, re.I)}


def score_case(case: dict, response: dict, status: int) -> dict:
    sql = response.get("sql", "") or ""
    error = response.get("error") or response.get("detail")
    rows = response.get("result") or []
    used_tables = {name.split(".")[-1] for name in tables_in_sql(sql)}
    hallucinated_tables = sorted(used_tables - ALLOWED_TABLES)
    if case.get("unanswerable"):
        correct = bool(error) and not rows
        hallucination = bool(rows) or bool(hallucinated_tables)
    else:
        expected_tables = set(case.get("expected_tables", []))
        tables_ok = expected_tables.issubset(used_tables)
        blob = normalized_blob(rows)
        values_ok = all(str(value).lower().replace(".0", "") in blob for value in case.get("expected_values", []))
        row_limit_ok = "max_rows" not in case or len(rows) <= case["max_rows"]
        correct = status == 200 and not error and tables_ok and values_ok and row_limit_ok
        hallucination = bool(hallucinated_tables)
    return {
        "correct": correct,
        "hallucination": hallucination,
        "hallucinated_tables": hallucinated_tables,
        "used_tables": sorted(used_tables),
        "error": error,
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((pct / 100) * len(ordered)) - 1)
    return round(ordered[index], 2)


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    latencies = [row["wall_latency_ms"] for row in rows]
    return {
        "cases": total,
        "correct": sum(row["correct"] for row in rows),
        "accuracy_pct": round(100 * sum(row["correct"] for row in rows) / total, 2) if total else 0,
        "hallucinations": sum(row["hallucination"] for row in rows),
        "hallucination_rate_pct": round(100 * sum(row["hallucination"] for row in rows) / total, 2) if total else 0,
        "avg_input_tokens": round(statistics.mean(row["metrics"].get("input_tokens", 0) for row in rows), 2) if total else 0,
        "total_input_tokens": sum(row["metrics"].get("input_tokens", 0) for row in rows),
        "avg_retries": round(statistics.mean(row.get("retries", 0) for row in rows), 2) if total else 0,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "p99_latency_ms": percentile(latencies, 99),
    }


def markdown_report(report: dict) -> str:
    summaries = report["summary"]
    lines = ["# NerfSQL benchmark report", "", f"Generated: {report['generated_at']}", "", "| Mode | Cases | Accuracy | Hallucination rate | Input tokens | p95 latency |", "|---|---:|---:|---:|---:|---:|"]
    for mode in ("rag", "full"):
        row = summaries.get(mode, {})
        lines.append(f"| {mode.upper()} | {row.get('cases', 0)} | {row.get('accuracy_pct', 0)}% | {row.get('hallucination_rate_pct', 0)}% | {row.get('total_input_tokens', 0)} | {row.get('p95_latency_ms', 0)} ms |")
    comparison = report.get("comparison", {})
    lines.extend(["", "## Comparison", "", f"- Hallucination reduction: **{comparison.get('hallucination_reduction_pct', 0)}%**", f"- Input-token reduction: **{comparison.get('input_token_reduction_pct', 0)}%**", "", "> Metrics are evidence only for the recorded model, dataset, configuration, and timestamp."])
    return "\n".join(lines) + "\n"


def reduction(before: float, after: float) -> float:
    return round(100 * (before - after) / before, 2) if before else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://nerfsql-demo.onrender.com")
    parser.add_argument("--connection-id")
    parser.add_argument("--connection-name", default="sd")
    parser.add_argument("--provider-id")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between LLM calls for free-tier rate limits")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--modes", nargs="+", choices=["rag", "full"], default=["rag", "full"])
    parser.add_argument("--output-dir", default="benchmark-results")
    args = parser.parse_args()

    with open(ROOT / "benchmark_cases.json", encoding="utf-8") as handle:
        cases = json.load(handle)
    if args.limit:
        cases = cases[: args.limit]

    connection_id = args.connection_id
    if not connection_id:
        status, payload = request_json(args.base_url, "/connections")
        if status != 200:
            raise SystemExit(f"Could not list connections: {status} {payload}")
        match = next((item for item in payload.get("connections", []) if item.get("name") == args.connection_name), None)
        if not match:
            raise SystemExit(f"Connection named {args.connection_name!r} was not found")
        connection_id = match["connection_id"]

    results: dict[str, list[dict]] = {}
    for mode in args.modes:
        mode_rows = []
        for number, case in enumerate(cases, 1):
            payload = {"question": case["question"], "connection_id": connection_id, "provider_id": args.provider_id, "schema_strategy": mode}
            status, response, wall_latency_ms = run_query_with_backoff(
                args.base_url, payload, args.max_attempts
            )
            scored = score_case(case, response, status)
            row = {"id": case["id"], "question": case["question"], "mode": mode, "status": status, "sql": response.get("sql"), "result": response.get("result"), "retries": response.get("retries", 0), "metrics": response.get("metrics", {}), "wall_latency_ms": wall_latency_ms, **scored}
            mode_rows.append(row)
            print(f"[{mode}] {number}/{len(cases)} {case['id']}: {'PASS' if row['correct'] else 'FAIL'} ({wall_latency_ms} ms)")
            if args.delay:
                time.sleep(args.delay)
        results[mode] = mode_rows

    summary = {mode: summarize(rows) for mode, rows in results.items()}
    comparison = {}
    if "rag" in summary and "full" in summary:
        comparison = {
            "hallucination_reduction_pct": reduction(summary["full"]["hallucination_rate_pct"], summary["rag"]["hallucination_rate_pct"]),
            "input_token_reduction_pct": reduction(summary["full"]["total_input_tokens"], summary["rag"]["total_input_tokens"]),
        }
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "base_url": args.base_url, "connection_id": connection_id, "case_count": len(cases), "summary": summary, "comparison": comparison, "results": results}
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (output_dir / "REPORT.md").write_text(markdown_report(report), encoding="utf-8")
    print(f"Wrote {output_dir / 'metrics.json'} and {output_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
