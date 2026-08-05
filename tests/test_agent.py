import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import extract_text_tool_calls


def test_extract_text_tool_calls_single():
    sample = """<think>
Some reasoning...
</think>

<tool_call>
{"name": "sql_query", "arguments": {"query": "SELECT * FROM clients WHERE business_segment = 'CIBG';"}}
</tool_call>"""

    tools = extract_text_tool_calls(sample)
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "sql_query"
    assert "SELECT * FROM clients WHERE business_segment = 'CIBG';" in tools[0]["function"]["arguments"]


def test_extract_text_tool_calls_empty():
    assert extract_text_tool_calls("Just a regular response.") == []
