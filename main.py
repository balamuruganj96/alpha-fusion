import os
from fastapi import FastAPI
from pydantic import BaseModel
from google.cloud import firestore
from langchain.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from orchestrator import create_investment_graph

app = FastAPI()
#db = firestore.Client()

class AnalysisRequest(BaseModel):
    user_id: str
    query: str # e.g., "Analyze Reliance Industries"


@app.post("/analyze")
async def run_analysis(request: AnalysisRequest):
    # 1. Setup MCP Client Parameters
    server_params = {
         "finance":{
           "command":"python",
            "args":["final_code/mcp_tools/finance.py"],
            "transport":"stdio"}
        ,"news":{
           "command":"python",
            "args":["final_code/mcp_tools/news.py"],
            "transport":"stdio"}
        ,"analysis":{
           "command":"python",
            "args":["final_code/mcp_tools/analysis.py"],
            "transport":"stdio"
        }
        }
    
    # 2. Initialize the client (NOT using 'async with')
    client = MultiServerMCPClient(server_params)
    
    try:
        # 3. Build and Run the Graph
        # Pass the client directly; the orchestrator will call get_tools()
        graph = await create_investment_graph(client)
        
        initial_state = {
            "messages": [HumanMessage(content=request.query)],
            "ticker": "",
            "analysis_results": {}
        }
        
        # Run the LangGraph
        result = await graph.ainvoke(initial_state)
        final_answer = result['messages'][-1].content

        # 4. Persistence in Firestore
        #doc_ref = db.collection("analysis_history").document()
        #doc_ref.set({
        #     "user_id": request.user_id,
        #     "query": request.query,
        #     "result": final_answer,
        #     "timestamp": firestore.SERVER_TIMESTAMP
        # })

        return {"analysis": final_answer}#, "id": doc_ref.id}

    except Exception as e:
        # Catch errors to prevent the API from hanging
        print(f"Error during analysis: {e}")
        return {"error": str(e)}
    
    # Note: MultiServerMCPClient usually handles its own cleanup, 
    # but for a production app, you'd manage the session shutdown here.


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
