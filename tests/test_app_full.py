import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import app
from app.main import QueryResponse


class FullAppApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import scripts.create_sample_db as sample_db

        sample_db.main()
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_ingest_and_schema(self):
        ingest = self.client.post("/ingest", json={"db_uri": "sqlite:///data/local.db"})
        self.assertEqual(ingest.status_code, 200)
        body = ingest.json()
        self.assertGreater(body.get("ingested", 0), 0)
        self.assertEqual(body.get("source_db_uri"), "sqlite:///data/local.db")

        schema = self.client.get("/schema")
        self.assertEqual(schema.status_code, 200)
        schema_body = schema.json()
        self.assertGreater(schema_body.get("count", 0), 0)
        self.assertIsInstance(schema_body.get("chunks"), list)

    @patch("app.api.query_agent")
    def test_query_endpoint(self, mock_query_agent):
        mock_query_agent.return_value = QueryResponse(
            sql="SELECT user_id, full_name FROM users;",
            result=[{"user_id": 1, "full_name": "Alice Green"}],
            error=None,
            retries=0,
        )

        response = self.client.post("/query", json={"question": "List users"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("error"), None)
        self.assertEqual(body.get("retries"), 0)
        self.assertIn("SELECT", body.get("sql", ""))
        self.assertEqual(len(body.get("result") or []), 1)


if __name__ == "__main__":
    unittest.main()
