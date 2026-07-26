from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Typed state for the Parakeet ReAct agent pipeline."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
