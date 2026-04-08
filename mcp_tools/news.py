from mcp.server.fastmcp import FastMCP
import yfinance as yf
from dotenv import load_dotenv
import finnhub

load_dotenv()
import os

mcp=FastMCP("news")

@mcp.tool()
async def get_news(ticker:str)->list[dict]:
    finnhub_client = finnhub.Client(api_key= os.getenv("FINNHUB_KEY"))

    return finnhub_client.company_news(ticker, _from="2026-03-01", to="2026-03-10")

    
if __name__=="__main__":
    mcp.run(transport='stdio')
