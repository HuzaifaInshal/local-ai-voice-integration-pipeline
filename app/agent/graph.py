from typing import Any
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.prompts import build_system_prompt
from app.agent.tools.sql_tool import execute_sql_query
from app.services.llm_factory import get_llm

def build_parakeet_agent(schema_context: str) -> Any:
    """Compiles and returns the LangGraph ReAct StateMachine for Parakeet."""
    tools = [execute_sql_query]
    llm = get_llm().bind_tools(tools)
    system_prompt = build_system_prompt(schema_context)
    
    def agent_node(state: AgentState):
        messages = list(state["messages"])
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=system_prompt)] + messages
        response = llm.invoke(messages)
        return {"messages": [response]}

    def tool_node(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        tool_outputs = []
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for call in last_message.tool_calls:
                if call["name"] == "execute_sql_query":
                    output = execute_sql_query.invoke(call["args"])
                    tool_outputs.append(
                        ToolMessage(content=str(output), tool_call_id=call["id"])
                    )
        return {"messages": tool_outputs}

    def should_continue(state: AgentState):
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
