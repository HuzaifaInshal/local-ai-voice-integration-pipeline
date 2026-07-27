import unittest
import sqlite3
import tempfile
from app.services.db_registry import DatabaseRegistry

class TestDatabaseRegistry(unittest.TestCase):

    def test_db_registry_initialization(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db_file = tmp.name
            db_url = f"sqlite:///{db_file}"
            
            conn = sqlite3.connect(db_file)
            conn.execute("CREATE TABLE test_acc (id INT PRIMARY KEY, name TEXT);")
            conn.execute("INSERT INTO test_acc VALUES (1, 'Alice');")
            conn.commit()
            conn.close()

            registry = DatabaseRegistry(db_url)
            registry.initialize()

            self.assertIn("test_acc", registry.schema_context)
            self.assertEqual(len(registry.catalog), 1)
            self.assertEqual(registry.catalog[0]["table_name"], "test_acc")

    def test_db_registry_read_only_query(self):
        registry = DatabaseRegistry("sqlite:///./data/banking.db")
        registry.initialize()
        results = registry.execute_read_only_query("SELECT * FROM accounts LIMIT 2")
        self.assertTrue(len(results) > 0)
        self.assertIn("customer_name", results[0])

if __name__ == "__main__":
    unittest.main()
