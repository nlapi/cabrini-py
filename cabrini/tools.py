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

    class ScanInput(BaseModel):
        date: str = Field(description="Trading date in YYYY-MM-DD format")
        volume_min: Optional[int] = Field(default=None, description="Minimum total volume for the day")
        gap_up_pct: Optional[float] = Field(default=None, description="Minimum gap up from prior close, in percent (5 = 5%)")
        gap_down_pct: Optional[float] = Field(default=None, description="Minimum gap down from prior close, in percent")
        change_pct_min: Optional[float] = Field(default=None, description="Minimum open-to-close change, in percent")
        change_pct_max: Optional[float] = Field(default=None, description="Maximum open-to-close change, in percent")
        volume_ratio_min: Optional[float] = Field(default=None, description="Minimum volume vs prior day, e.g. 2.0 for 2x")
        limit: Optional[int] = Field(default=50, description="Maximum matches to return")

    class CompanyInput(BaseModel):
        ticker: str = Field(description="US stock ticker symbol")

    tools = [
        StructuredTool.from_function(
            func=lambda ticker, date, interval=3: c.query(ticker, date, interval),
            name="cabrini_query",
            description="Get intraday bars for a US stock on a date. Each bar gives pct_open/pct_high/pct_low/pct_close (fractional change from that day's open) plus volume and transactions. ~130 bars/day at 3-min intervals, 23 years of history. For absolute prices call cabrini_daily and compute price = day_open * (1 + pct). Costs $0.025 USDC.",
            args_schema=QueryInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker, start, end: c.daily(ticker, start, end),
            name="cabrini_daily",
            description="Get daily OHLCV bars plus VWAP for a US stock over a date range. This is the tool that returns absolute price levels. Costs $0.001 per year of data.",
            args_schema=DailyInput,
        ),
        StructuredTool.from_function(
            func=lambda date: c.tickers(date),
            name="cabrini_tickers",
            description="List all US stock tickers that traded on a given date. Costs $0.005 USDC.",
            args_schema=DateInput,
        ),
        StructuredTool.from_function(
            func=lambda date, **kw: c.scan(date, **{k: v for k, v in kw.items() if v is not None}),
            name="cabrini_scan",
            description="Screen every US stock on a date against criteria such as volume_min, gap_up_pct or change_pct_min. At least one criterion is required. Returns pct_change, pct_gap, volume and volume_ratio per match (fractional: 0.05 = 5%). Costs $0.10 USDC.",
            args_schema=ScanInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.fundamentals(ticker),
            name="cabrini_fundamentals",
            description="Get SEC quarterly fundamentals (revenue, income, EPS, etc.) for a US stock. Costs $0.02 USDC.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.filings(ticker),
            name="cabrini_filings",
            description="Get the SEC filing index (10-K, 10-Q, 8-K) for a US stock. Costs $0.01 USDC, or $0.05 with extracted section text.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.insiders(ticker),
            name="cabrini_insiders",
            description="Get insider buy/sell transactions (SEC Form 4) for a US stock. Costs $0.02 USDC.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.brief(ticker),
            name="cabrini_brief",
            description="Get a joined research brief: price action + fundamentals + insiders + splits in one call. Replaces ~20 individual queries. Costs $0.25 USDC.",
            args_schema=CompanyInput,
        ),
        StructuredTool.from_function(
            func=lambda ticker: c.company(ticker),
            name="cabrini_company",
            description="Get a company profile from SEC EDGAR (name, CIK, industry, exchange). Costs $0.005 USDC.",
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
        """Intraday bars as fractional change from the daily open, plus volume. Pair with get_daily_bars for absolute prices. $0.025 per query."""
        import json
        return json.dumps(c.query(ticker, date, interval))

    @crewai_tool("Get Daily Bars")
    def get_daily_bars(ticker: str, start: str, end: str) -> str:
        """Daily OHLCV bars plus VWAP — the absolute price levels. $0.001 per year."""
        import json
        return json.dumps(c.daily(ticker, start, end))

    @crewai_tool("List Tickers")
    def list_tickers(date: str) -> str:
        """List all US stocks traded on a date. $0.005 USDC."""
        import json
        return json.dumps(c.tickers(date))

    @crewai_tool("Get Fundamentals")
    def get_fundamentals(ticker: str) -> str:
        """Get SEC quarterly fundamentals for a stock. $0.02 USDC."""
        import json
        return json.dumps(c.fundamentals(ticker))

    @crewai_tool("Get SEC Filings")
    def get_sec_filings(ticker: str) -> str:
        """SEC filing index. $0.01 USDC, or $0.05 with extracted section text."""
        import json
        return json.dumps(c.filings(ticker))

    @crewai_tool("Get Insider Trades")
    def get_insider_trades(ticker: str) -> str:
        """Get insider buy/sell transactions (Form 4). $0.02 USDC."""
        import json
        return json.dumps(c.insiders(ticker))

    @crewai_tool("Company Brief")
    def company_brief(ticker: str) -> str:
        """Joined research brief: price + fundamentals + insiders + splits. $0.25 USDC."""
        import json
        return json.dumps(c.brief(ticker))

    @crewai_tool("Market Scan")
    def market_scan(date: str, volume_min: Optional[int] = None, gap_up_pct: Optional[float] = None,
                    change_pct_min: Optional[float] = None, volume_ratio_min: Optional[float] = None,
                    limit: int = 50) -> str:
        """Screen every US stock on a date. At least one criterion is required.

        Criteria are in percent (5 = 5%); results are fractional (0.05 = 5%). $0.10 USDC.
        """
        import json
        criteria = {k: v for k, v in {
            "volume_min": volume_min, "gap_up_pct": gap_up_pct,
            "change_pct_min": change_pct_min, "volume_ratio_min": volume_ratio_min,
            "limit": limit,
        }.items() if v is not None}
        return json.dumps(c.scan(date, **criteria))

    return [query_stock_bars, get_daily_bars, list_tickers, get_fundamentals,
            get_sec_filings, get_insider_trades, company_brief, market_scan]
