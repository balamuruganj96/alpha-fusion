import sys
import logging
from mcp.server.fastmcp import FastMCP
import yfinance as yf
from ta.momentum import RSIIndicator

# Configure logging to stderr so it doesn't corrupt the stdio MCP channel
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("analysis")

@mcp.tool()
async def get_technical_analysis(ticker: str):
    """
    Performs technical analysis including RSI, Moving Averages, and Trend detection.
    Returns signals to indicate if a stock is overbought or oversold.
    """
    try:
        stock = yf.Ticker(ticker)
        # Fetching 7 months to ensure we have enough data for a 200-day MA
        df = stock.history(period="8mo")

        if df.empty:
            return {"error": f"No technical data found for {ticker}"}

        # 1. RSI Calculation
        rsi_indicator = RSIIndicator(close=df["Close"], window=14)
        df["RSI"] = rsi_indicator.rsi()
        latest_rsi = float(df["RSI"].iloc[-1])

        # 2. Moving Averages
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["MA200"] = df["Close"].rolling(window=200).mean()
        
        current_price = float(df["Close"].iloc[-1])
        ma50 = float(df["MA50"].iloc[-1])
        ma200 = float(df["MA200"].iloc[-1])

        # 3. Support & Resistance (60-day window)
        support = float(df["Low"].tail(60).min())
        resistance = float(df["High"].tail(60).max())

        # 4. Logic-Based Grounding (The "Anti-Hold" Logic)
        rsi_signal = "NEUTRAL"
        if latest_rsi > 70: rsi_signal = "OVERBOUGHT (Sell Signal)"
        elif latest_rsi < 30: rsi_signal = "OVERSOLD (Buy Signal)"

        trend = "NEUTRAL"
        if current_price > ma50 > ma200: trend = "STRONG BULLISH"
        elif current_price < ma50 < ma200: trend = "STRONG BEARISH"

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 2),
            "rsi": round(latest_rsi, 2),
            "rsi_interpretation": rsi_signal,
            "market_trend": trend,
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "distance_from_resistance": f"{round(((resistance - current_price)/resistance)*100, 2)}%"
        }
    except Exception as e:
        logger.error(f"Technical analysis error for {ticker}: {str(e)}")
        return {"error": str(e)}

@mcp.tool()
async def get_fundamental_analysis(ticker: str):
    """
    Performs fundamental analysis including P/E ratios, EPS, and profit margins.
    Identifies if a stock is undervalued or expensive based on historical averages.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        pe_ratio = info.get("trailingPE")
        profit_margin = info.get("profitMargins")
        
        # 1. Valuation Grounding
        # Standard benchmark: PE > 35 is generally considered "Expensive" for large caps
        valuation_status = "FAIR VALUE"
        if pe_ratio:
            if pe_ratio > 40: valuation_status = "OVERVALUED / EXPENSIVE"
            elif pe_ratio < 15: valuation_status = "UNDERVALUED / CHEAP"

        # 2. Financial Health Grounding
        margin_status = "STABLE"
        if profit_margin:
            if profit_margin > 0.20: margin_status = "HIGHLY PROFITABLE"
            elif profit_margin < 0.05: margin_status = "THIN MARGINS / RISKY"

        return {
            "ticker": ticker.upper(),
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "pe_ratio": round(pe_ratio, 2) if pe_ratio else "N/A",
            "valuation_interpretation": valuation_status,
            "eps": info.get("trailingEps"),
            "profit_margin_pct": f"{round(profit_margin * 100, 2)}%" if profit_margin else "N/A",
            "margin_interpretation": margin_status,
            "dividend_yield": info.get("dividendYield", 0),
            "market_cap_billions": round(info.get("marketCap", 0) / 1e9, 2)
        }
    except Exception as e:
        logger.error(f"Fundamental analysis error for {ticker}: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # Explicitly run with stdio transport for the LangGraph client
    mcp.run(transport='stdio')
