import unittest
from app.agent.prompts import build_system_prompt
from app.utils.formatting import extract_json_payload

class TestAgentUtilities(unittest.TestCase):

    def test_system_prompt_builder(self):
        prompt = build_system_prompt("sample_schema_context_here")
        self.assertIn("Parakeet", prompt)
        self.assertIn("sample_schema_context_here", prompt)
        self.assertIn("display_type", prompt)

    def test_extract_json_payload(self):
        sample_text = """Here is the breakdown of top accounts:
```json
{
  "display_type": "table",
  "title": "Top Accounts",
  "table_headers": ["Name", "Balance"],
  "rows": [["Acme Corp", "$4,500,000"]]
}
```
Let me know if you need more details."""

        clean_text, payload = extract_json_payload(sample_text)
        self.assertEqual(payload["display_type"], "table")
        self.assertEqual(payload["title"], "Top Accounts")
        self.assertIn("Here is the breakdown", clean_text)
        self.assertNotIn("```json", clean_text)

if __name__ == "__main__":
    unittest.main()
