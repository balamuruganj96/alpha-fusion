import streamlit as st
import asyncio
import os
import sys
import operator
from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import AzureChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv

# --- INITIALIZATION ---
load_dotenv()
st.set_page_config(page_title="Alpha-Orchestrator", layout="wide")

# --- 1. LANGGRAPH LOGIC ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

async def create_investment_graph(mcp_client):
    tools = await mcp_client.get_tools()
    llm = AzureChatOpenAI(azure_endpoint="https://dbt-poc.openai.azure.com/",
    azure_deployment="dbtpoc",
    temperature=0.4, # Added a bit of "opinion",
    api_version="2024-12-01-preview",
    model='GPT-4.1 nano'
    ).bind_tools(tools)

    async def call_model(state):
        return {"messages": [await llm.ainvoke(state['messages'])]}

    async def manager_node(state):
        summary_prompt = """
                You are a high-conviction Hedge Fund Manager. 
                Review the reports from your Technical, Fundamental, and News analysts.

                CRITICAL INSTRUCTIONS:
                1. Do NOT default to 'HOLD' unless the signals are 50/50.
                2. If the stock is 'Cheap' (Low P/E, High Growth) and News is positive, it MUST be a BUY.
                3. If the stock is 'Overvalued' (High P/E vs Peers) and Technicals are bearish, it MUST be a SELL.
                4. Provide a 'Conviction Score' from 1-10.

                Format your response with clear sections: 
                - FINAL DECISION (BUY/SELL/HOLD)
                - CONVICTION SCORE
                - THE 'WHY' (3 Bullet points)
                """
        res = await llm.ainvoke(state['messages'] + [HumanMessage(content=summary_prompt)])
        return {"messages": [res]}

    def should_continue(state):
        messages = state["messages"]
        if messages[-1].tool_calls:
            return "tools"
        return "manager"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("manager", manager_node)
    
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "manager": "manager"})
    workflow.add_edge("tools", "agent")
    workflow.add_edge("manager", END)
    
    return workflow.compile()

# --- 2. THE ASYNC BRIDGE ---
async def run_orchestration(ticker_query):
    # Dynamically find the path to your MCP tools
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Define your 3 local MCP servers
    server_params = {
        "finance": {
            "command": sys.executable,
            "args": [os.path.join(base_path, "mcp_tools", "finance.py")],
            "transport": "stdio"
        },
        "news": {
            "command": sys.executable,
            "args": [os.path.join(base_path, "mcp_tools", "news.py")],
            "transport": "stdio"
        },
        "analysis": {
            "command": sys.executable,
            "args": [os.path.join(base_path, "mcp_tools", "analysis.py")],
            "transport": "stdio"
        }
    }
    
    # Run the client and graph in a single session
    client = MultiServerMCPClient(server_params)
    graph = await create_investment_graph(client)
    
    result = await graph.ainvoke({"messages": [HumanMessage(content=ticker_query)]})
    return result['messages'][-1].content

# --- 3. STREAMLIT UI ---
st.title("🎯 Alpha-Orchestrator")
st.caption("Standalone Multi-Agent Investment Committee (Self-Contained)")

with st.sidebar:
    st.header("Ticker")
    ticker = st.text_input("Symbol", value="AAPL")
    analyze_btn = st.button("🚀 RUN FULL ANALYSIS")

if analyze_btn:
    with st.status("🛠️ **Orchestrating Agents...**", expanded=True) as status:
        st.write("Initializing MCP subprocesses...")
        try:
            # Use asyncio.run to execute the async code in a sync Streamlit flow
            final_report = asyncio.run(run_orchestration(f"Analyze {ticker}"))
            
            status.update(label="✅ Analysis Complete!", state="complete")
            
            # Display metrics (mocking values for UI demo)
            c1, c2, c3 = st.columns(3)
            c1.metric("Status", "Resolved")
            c2.metric("Agents", "4 Engaged")
            c3.metric("Latency", "Fast")
            
            st.divider()
            st.markdown(final_report)
            
        except Exception as e:
            st.error(f"Execution Error: {e}")
            st.info("Check if your mcp_tools folder exists and paths are correct.")
