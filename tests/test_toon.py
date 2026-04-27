import unittest

from app.utils.toon import extract_sql_from_toon, schema_text_to_toon


class ToonUtilsTests(unittest.TestCase):
    def test_schema_text_to_toon(self):
        schema = (
            "Table: users\n"
            "Columns: user_id, full_name, country_code\n"
            "Table: travel_entries\n"
            "Columns: travel_id, user_id, co2e_kg\n"
            "Foreign keys: ['user_id'] -> users"
        )
        toon = schema_text_to_toon(schema)
        self.assertIn("tables", toon)
        self.assertIn("name: users", toon)
        self.assertIn("columns", toon)
        self.assertIn("name: travel_entries", toon)

    def test_extract_sql_from_toon_single_line(self):
        text = "sql: 'SELECT * FROM users;'"
        self.assertEqual(extract_sql_from_toon(text), "SELECT * FROM users;")

    def test_extract_sql_from_toon_fallback(self):
        text = "SELECT user_id FROM users;"
        self.assertEqual(extract_sql_from_toon(text), text)


if __name__ == "__main__":
    unittest.main()
