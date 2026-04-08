from mcp.server.fastmcp import FastMCP
import yfinance as yf

mcp=FastMCP("finance")
@mcp.tool()
async def fetch_stock_data(ticker: str):
    """Fetches real-time price, change, and volume using Yahoo Finance for the particular ticker."""
    try:
        stock = yf.Ticker(ticker)
        # fast_info is optimized for speed
        info = stock.fast_info 
        
        # Calculate % change manually from previous close
        prev_close = stock.history(period="1d")["Close"].iloc[-1]
        current_price = info['last_price']
        change_pct = ((current_price - prev_close) / prev_close) * 100

        return {
            "ticker": ticker.upper(),
            "price": round(current_price, 2),
            "change": f"{round(change_pct, 2)}%",
            "volume": f"{int(info['last_volume'] / 1e6)}M",
            "source": "Yahoo Finance"
        }
    except Exception as e:
        return {"error": f"Could not fetch data for {ticker}: {str(e)}"}
#currently unstable
# @mcp.tool()
# async def search_ticker(query: str) -> list:
#     """
#     Dynamically searches for stock tickers based on a company name or keyword.
#     Use this when the user doesn't provide a specific ticker symbol.
#     """
#     try:
#         # yf.Search is the official way to perform lookups
#         search = yf.Search(query, max_results=5)
        
#         # Extract the relevant info: symbol, company name, and exchange
#         results = []
#         for quote in search.quotes:
#             results.append({
#                 "ticker": quote.get("symbol"),
#                 "name": quote.get("shortname"),
#                 "exchange": quote.get("exchange")
#             })
            
#         return results if results else [{"error": "No tickers found for this query."}]
#     except Exception as e:
#         return [{"error": f"Search failed: {str(e)}"}]
    
if __name__=="__main__":
    mcp.run(transport='stdio')
