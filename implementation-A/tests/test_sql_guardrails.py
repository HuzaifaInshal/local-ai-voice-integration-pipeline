import unittest
from app.agent.tools.sanitize import validate_read_only_sql

class TestSQLGuardrails(unittest.TestCase):

    def test_valid_select_queries(self):
        valid_queries = [
            "SELECT * FROM accounts;",
            "SELECT customer_name, balance FROM accounts WHERE balance > 10000 ORDER BY balance DESC",
            "SELECT count(*) FROM transactions GROUP BY category"
        ]
        for q in valid_queries:
            try:
                validate_read_only_sql(q)
            except Exception as e:
                self.fail(f"Valid query '{q}' raised exception: {e}")

    def test_forbidden_sql_statements(self):
        forbidden_queries = [
            "UPDATE accounts SET balance = 0 WHERE account_id = 1",
            "DELETE FROM transactions WHERE transaction_id = 5",
            "DROP TABLE loans;",
            "INSERT INTO accounts (customer_name) VALUES ('Hacker')",
            "ALTER TABLE accounts ADD COLUMN hacked TEXT",
            "TRUNCATE TABLE transactions"
        ]
        for q in forbidden_queries:
            with self.assertRaises(PermissionError):
                validate_read_only_sql(q)

if __name__ == "__main__":
    unittest.main()
