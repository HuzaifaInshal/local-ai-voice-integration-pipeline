import unittest
from app.config import settings

class TestConfigSettings(unittest.TestCase):

    def test_settings_defaults(self):
        self.assertEqual(settings.ws_path, "/ws/parakeet")
        self.assertIn("banking.db", settings.database_url)

if __name__ == "__main__":
    unittest.main()
