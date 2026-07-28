from typing import Any
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.prompts import build_system_prompt
from app.agent.tools.sql_tool import execute_sql_query
from app.services.llm_factory import get_llm
from app.core.logger import setup_logger

logger = setup_logger("alfa.agent")

def build_alfa_agent(schema_context: str) -> Any:
    """Compiles and returns the LangGraph ReAct StateMachine for Alfa AI."""
    tools = [execute_sql_query]
    llm = get_llm().bind_tools(tools)
    system_prompt = build_system_prompt(schema_context)
    
    def agent_node(state: AgentState):
        messages = list(state["messages"])
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=system_prompt)] + messages

        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        iteration = len(ai_messages) + 1

        logger.info(f"🧠 [Alfa ReAct Loop - Iteration #{iteration}] Reasoning & planning...")
        response = llm.invoke(messages)

        if response.content:
            logger.info(f"💭 [ReAct Thought #{iteration}]: {response.content.strip()}")

        if hasattr(response, "tool_calls") and response.tool_calls:
            for call in response.tool_calls:
                logger.info(f"🛠️ [ReAct Action #{iteration}]: Calling Tool '{call['name']}' with args: {call['args']}")
        else:
            logger.info(f"🏁 [ReAct Final Answer #{iteration}]: Reached conclusion.")

        return {"messages": [response]}

    def tool_node(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        tool_outputs = []
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for call in last_message.tool_calls:
                if call["name"] == "execute_sql_query":
                    sql_query = call['args'].get('query', '')
                    logger.info(f"⚙️ [Executing Tool]: 'execute_sql_query' -> {sql_query}")
                    
                    output = execute_sql_query.invoke(call["args"])
                    
                    obs_snippet = str(output)[:250] + ("..." if len(str(output)) > 250 else "")
                    logger.info(f"👁️ [ReAct Observation]: Result -> {obs_snippet}")

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
