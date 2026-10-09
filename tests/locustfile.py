"""Free load test: infrastructure endpoints only by default."""
import os

from locust import HttpUser, between, task


class NerfSQLUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(5)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(2)
    def connections(self):
        self.client.get("/connections", name="GET /connections")

    @task(2)
    def schema(self):
        connection_id = os.getenv("BENCHMARK_CONNECTION_ID")
        path = f"/schema?connection_id={connection_id}" if connection_id else "/schema"
        self.client.get(path, name="GET /schema")

    @task(1)
    def providers(self):
        self.client.get("/providers", name="GET /providers")


class LLMQueryUser(HttpUser):
    """Enable explicitly with LOCUST_QUERY_TEST=1 and use only a few users."""
    wait_time = between(5, 10)
    weight = 0 if os.getenv("LOCUST_QUERY_TEST") != "1" else 1

    @task
    def query(self):
        connection_id = os.getenv("BENCHMARK_CONNECTION_ID")
        if not connection_id:
            return
        self.client.post(
            "/query",
            name="POST /query",
            json={
                "question": "Which customer spent the most, excluding cancelled orders?",
                "connection_id": connection_id,
                "schema_strategy": "rag",
            },
        )
