import operator
import os
from typing import Annotated, List, TypedDict, Union

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode  # <--- Crucial for tool execution
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# 1. Define the State
class AgentState(TypedDict):
    # Important: operator.add ensures tool responses are appended to history
    messages: Annotated[List[BaseMessage], operator.add]

async def create_investment_graph(mcp_client):
    # Load your 4 MCP tools
    tools = await mcp_client.get_tools()
    
    # Initialize LLM and bind tools
    llm = AzureChatOpenAI().bind_tools(tools)

    # --- NODE FUNCTIONS ---
    
    async def call_model(state: AgentState):
        """Node that decides which tools to call."""
        response = await llm.ainvoke(state['messages'])
        return {"messages": [response]}

    async def manager_node(state: AgentState):
        """The final node that summarizes everything once tools are done."""
        summary_prompt = (
            "You are the Chief Investment Officer. Review the technical, "
            "fundamental, and news reports provided above. Resolve any conflicts "
            "and provide a final 'BUY/HOLD/SELL' recommendation with reasoning."
        )
        # Combine history with the final CIO instruction
        messages = state['messages'] + [HumanMessage(content=summary_prompt)]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    # --- ROUTING LOGIC ---

    def should_continue(state: AgentState):
        """Determines if we need to execute tools or go to the manager."""
        last_message = state["messages"][-1]
        # If the LLM made tool calls, we must go to the 'tools' node
        if last_message.tool_calls:
            return "tools"
        # Otherwise, the analysts are done and the manager can summarize
        return "manager"

    # --- GRAPH CONSTRUCTION ---
    workflow = StateGraph(AgentState)

    # Define Nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools)) # This executes the MCP tools
    workflow.add_node("manager", manager_node)

    # Define Edges
    workflow.set_entry_point("agent")

    # Conditional logic: Agent -> Tools OR Agent -> Manager
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "manager": "manager"
        }
    )

    # After tools run, they MUST go back to the agent so it can read the results
    workflow.add_edge("tools", "agent")
    
    # After the manager speaks, we are finished
    workflow.add_edge("manager", END)

    return workflow.compile()
