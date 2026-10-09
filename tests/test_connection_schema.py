import unittest
from unittest.mock import patch

from sqlalchemy import create_engine

from app.main import _schema_for_query
from scripts.ingest_schema import extract_schema_from_engine


class ConnectionSchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            conn.exec_driver_sql(
                "CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(customer_id))"
            )

    def tearDown(self):
        self.engine.dispose()

    def test_extracts_tables_and_relationships_from_selected_engine(self):
        chunks = extract_schema_from_engine(self.engine)
        schema = "\n".join(chunks)
        self.assertIn("Table: customers", schema)
        self.assertIn("Table: orders", schema)
        self.assertIn("customer_id", schema)
        self.assertIn("-> customers", schema)

    @patch("app.main.get_connection_engine")
    def test_query_schema_uses_selected_connection(self, get_engine):
        get_engine.return_value = self.engine
        schema = _schema_for_query("list customers", "supabase-connection")
        get_engine.assert_called_once_with("supabase-connection", owner_id="default")
        self.assertIn("Table: customers", schema)
        self.assertNotIn("electricity_entries", schema)


if __name__ == "__main__":
    unittest.main()
