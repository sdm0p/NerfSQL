import unittest

from tests.run_metrics import percentile, reduction, score_case


class MetricsTests(unittest.TestCase):
    def test_scores_semantically_correct_result(self):
        case = {
            "expected_tables": ["customers", "orders", "order_items"],
            "expected_values": ["Aarav Sharma", 14594],
            "max_rows": 1,
        }
        response = {
            "sql": "SELECT c.name, SUM(i.quantity*i.unit_price) total FROM customers c JOIN orders o ON true JOIN order_items i ON true",
            "result": [{"name": "Aarav Sharma", "total": 14594}],
            "error": None,
        }
        result = score_case(case, response, 200)
        self.assertTrue(result["correct"])
        self.assertFalse(result["hallucination"])

    def test_detects_unknown_table_hallucination(self):
        case = {"expected_tables": ["customers"], "expected_values": [5]}
        response = {"sql": "SELECT COUNT(*) FROM customer_accounts", "result": [{"count": 5}]}
        result = score_case(case, response, 200)
        self.assertFalse(result["correct"])
        self.assertTrue(result["hallucination"])

    def test_unanswerable_question_requires_safe_error(self):
        result = score_case({"unanswerable": True}, {"error": "Cannot answer", "result": None}, 200)
        self.assertTrue(result["correct"])

    def test_metric_math(self):
        self.assertEqual(percentile([10, 20, 30, 40, 50], 95), 50)
        self.assertEqual(reduction(40, 22), 45)


if __name__ == "__main__":
    unittest.main()
