import json

from fastapi.testclient import TestClient

from app.api import app


def main() -> None:
    client = TestClient(app)

    with open("tests/eval_queries.json", "r", encoding="utf-8") as f:
        tests = json.load(f)

    ingest = client.post("/ingest", json={"db_uri": "sqlite:///data/local.db"})
    if ingest.status_code != 200:
        raise RuntimeError(f"Ingest failed: {ingest.status_code} {ingest.text}")

    passed = 0
    for i, test in enumerate(tests, start=1):
        question = test["question"]
        response = client.post("/query", json={"question": question})
        body = response.json()
        ok = response.status_code == 200 and body.get("error") in (None, "")
        print(f"{i}. {question}")
        print(
            f"   status: {response.status_code} retries: {body.get('retries')} error: {body.get('error')}"
        )
        print(f"   sql: {body.get('sql')}")
        print(f"   rows: {len(body.get('result') or [])}")
        if ok:
            passed += 1

    print(f"passed {passed}/{len(tests)}")
    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
