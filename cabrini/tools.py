"""LangChain and CrewAI tool wrappers for Cabrini."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_langchain_tools(private_key: str, **client_kwargs) -> List[Any]:
    """Return Cabrini tools as LangChain Tool objects.

    Usage:
        from cabrini import get_langchain_tools

        tools = get_langchain_tools(private_key="0x...")
        agent = create_react_agent(llm, tools)
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from cabrini.client import Cabrini

    c = Cabrini(private_key=private_key, **client_kwargs)

    class QueryInput(BaseModel):
        ticker: str = Field(description="US stock ticker symbol, e.g. AAPL")
        date: str = Field(description="Trading date in YYYY-MM-DD format (2003-09 to present)")
        interval: int = Field(default=3, description="Bar interval in minutes: 3, 6, 9, 12, 15, 30, 60, or 240")

    class DailyInput(BaseModel):
        ticker: str = Field(description="US stock ticker symbol")
        start: str = Field(description="Start date YYYY-MM-DD")
        end: str = Field(description="End date YYYY-MM-DD")

    class TickerInput(BaseModel):
        ticker: str = Field(description="US stock ticker symbol")

    class DateInput(BaseModel):
        date: str = Field(description="Date in YYYY-MM-DD format")

    class CompanyInput(BaseModel):
        ticker: str = Field(description="US stock ticker symbol")

    tools = [
        StructuredTool.from_function(
            func=lambda ticker, date, interval=3: c.query(ticker, date, interval),
            name="cabrini_query",
            description="Get intraday OHLCV bars for a US stock on a specific date. Returns ~130 bars per day at 3-min intervals. 23 years of history. Costs $0.025 USDC.",
            args_schema=QueryInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker, start, end: c.daily(ticker, start, end),
            name="cabrini_daily",
            description="Get daily OHLCV bars for a US stock over a date range. Costs $0.01 per day in the range.",
            args_schema=DailyInput,
        ),
        StructuredTool.from_function(
            func=lambda date: c.tickers(date),
            name="cabrini_tickers",
            description="List all US stock tickers that traded on a given date. Costs $0.005.",
            args_schema=DateInput,
        ),
        StructuredTool.from_function(
            func=lambda date: c.scan(date),
            name="cabrini_scan",
            description="Get daily OHLCV for ALL tickers on a date (full market snapshot). Costs $0.25.",
            args_schema=DateInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.fundamentals(ticker),
            name="cabrini_fundamentals",
            description="Get SEC quarterly fundamentals (revenue, income, EPS, etc.) for a US stock. Costs $0.02.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.filings(ticker),
            name="cabrini_filings",
            description="Get SEC filings (10-K, 10-Q, 8-K) with extracted text for a US stock. Costs $0.02.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.insiders(ticker),
            name="cabrini_insiders",
            description="Get insider buy/sell transactions for a US stock. Costs $0.02.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.brief(ticker),
            name="cabrini_brief",
            description="Get a full company research brief: fundamentals + recent filings + insider activity. Costs $0.04.",
            args_schema=CompanyInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.company(ticker),
            name="cabrini_company",
            description="Get company metadata (name, sector, market cap, exchange). Costs $0.001.",
            args_schema=CompanyInput,
        ),
    ]
    return tools


def get_crewai_tools(private_key: str, **client_kwargs) -> List[Any]:
    """Return Cabrini tools as CrewAI Tool objects.

    Usage:
        from cabrini import get_crewai_tools

        tools = get_crewai_tools(private_key="0x...")
        agent = Agent(role="analyst", tools=tools)
    """
    from crewai import tool as crewai_tool

    from cabrini.client import Cabrini

    c = Cabrini(private_key=private_key, **client_kwargs)

    @crewai_tool("Query Stock Bars")
    def query_stock_bars(ticker: str, date: str, interval: int = 3) -> str:
        """Get intraday OHLCV bars for a US stock. 23 years of minute-level data. $0.025 per query."""
        import json
        return json.dumps(c.query(ticker, date, interval))

    @crewai_tool("Get Daily Bars")
    def get_daily_bars(ticker: str, start: str, end: str) -> str:
        """Get daily OHLCV bars for a date range. $0.01/day."""
        import json
        return json.dumps(c.daily(ticker, start, end))

    @crewai_tool("List Tickers")
    def list_tickers(date: str) -> str:
        """List all US stocks traded on a date. $0.005."""
        import json
        return json.dumps(c.tickers(date))

    @crewai_tool("Get Fundamentals")
    def get_fundamentals(ticker: str) -> str:
        """Get SEC quarterly fundamentals for a stock. $0.02."""
        import json
        return json.dumps(c.fundamentals(ticker))

    @crewai_tool("Get SEC Filings")
    def get_sec_filings(ticker: str) -> str:
        """Get SEC filings with extracted text. $0.02."""
        import json
        return json.dumps(c.filings(ticker))

    @crewai_tool("Get Insider Trades")
    def get_insider_trades(ticker: str) -> str:
        """Get insider buy/sell transactions. $0.02."""
        import json
        return json.dumps(c.insiders(ticker))

    @crewai_tool("Company Brief")
    def company_brief(ticker: str) -> str:
        """Full research brief: fundamentals + filings + insiders. $0.04."""
        import json
        return json.dumps(c.brief(ticker))

    @crewai_tool("Market Scan")
    def market_scan(date: str) -> str:
        """Full market snapshot — all tickers on a date. $0.25."""
        import json
        return json.dumps(c.scan(date))

    return [query_stock_bars, get_daily_bars, list_tickers, get_fundamentals,
            get_sec_filings, get_insider_trades, company_brief, market_scan]
