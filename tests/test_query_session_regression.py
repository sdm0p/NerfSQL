import unittest
from unittest.mock import patch

from app.main import query_agent, _session_manager


class QuerySessionRegressionTest(unittest.TestCase):
    def test_missing_local_schema_cache_uses_database_schema(self):
        from app.main import _schema_for_query
        with patch("app.main._get_retriever") as retriever, \
             patch("app.main.get_engine", return_value=object()), \
             patch("app.main.extract_schema_from_engine", return_value=["Table: users"]):
            retriever.return_value.retrieve.return_value = ""
            self.assertEqual(_schema_for_query("users", None), "Table: users")

    def test_successful_query_records_and_returns_metrics(self):
        class Graph:
            def invoke(self, state):
                return {**state, "sql": "SELECT 1", "result": [[1]],
                        "input_tokens": 12, "output_tokens": 3, "llm_calls": 1}

        with patch("app.main._schema_for_query", return_value="Table: demo"), \
             patch("app.main._get_graph", return_value=Graph()):
            response = query_agent("test", schema_strategy="full")

        self.assertEqual(response.result, [[1]])
        self.assertEqual(response.input_tokens, 12)
        self.assertEqual(response.schema_strategy, "full")
        history = _session_manager.get_chat_history(response.chat_id)
        self.assertEqual(history["responses"][-1]["llm_calls"], 1)
        self.assertEqual(history["responses"][-1]["schema_strategy"], "full")


if __name__ == "__main__":
    unittest.main()
