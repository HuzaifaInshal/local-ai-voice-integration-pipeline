import json
import re
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

        # TOOL CALL INTERCEPTOR: Guarantee any generated SQL query or JSON tool call is executed
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            content_text = response.content or ""
            sql_query = None

            # 1. Check for JSON tool call
            json_match = re.search(r"```json\s*(\{[\s\S]*?\"execute_sql_query\"[\s\S]*?\})\s*```", content_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r"(\{[\s\S]*?\"execute_sql_query\"[\s\S]*?\})", content_text, re.DOTALL)

            if json_match:
                try:
                    payload = json.loads(json_match.group(1))
                    if "args" in payload and isinstance(payload["args"], dict):
                        sql_query = payload["args"].get("query")
                    elif "query" in payload:
                        sql_query = payload.get("query")
                except Exception:
                    pass

            # 2. Check for ```sql ... ``` or standalone SELECT query
            if not sql_query:
                sql_codeblock = re.search(r"```sql\s*(SELECT[\s\S]+?)\s*```", content_text, re.IGNORECASE)
                if sql_codeblock:
                    sql_query = sql_codeblock.group(1).strip()
                else:
                    sql_match = re.search(r"\b(SELECT\s+[\s\S]+?)(?:;|\n\n|```|$)", content_text, re.IGNORECASE)
                    if sql_match and len(sql_match.group(1).strip()) > 10:
                        sql_query = sql_match.group(1).strip()

            if sql_query:
                if not sql_query.endswith(";"):
                    sql_query += ";"
                logger.info(f"🎯 [Interceptor]: Found SQL query in response text: '{sql_query}' -> Converting to tool_call execution")
                response = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "execute_sql_query",
                        "args": {"query": sql_query},
                        "id": f"call_sql_{iteration:03d}"
                    }]
                )

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
