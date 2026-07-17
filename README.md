# cabrini

US stock market data for AI agents. 23 years of minute-level OHLCV bars, SEC fundamentals, filings, and insider data — every US equity from 2003 to present.

Pay per query with USDC on Base (x402). No API keys, no subscriptions, no signup.

## Install

```bash
pip install cabrini
```

## Quick start

```python
from cabrini import Cabrini

c = Cabrini(private_key="0x...")  # any Base wallet with USDC

# Intraday bars — $0.025
bars = c.query("AAPL", "2024-01-15")

# Daily bars — $0.01/day
daily = c.daily("TSLA", "2024-01-01", "2024-03-31")

# SEC fundamentals — $0.02
fins = c.fundamentals("NVDA")

# Full research brief — $0.04
brief = c.brief("MSFT")
```

## LangChain

```python
from cabrini import get_langchain_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

tools = get_langchain_tools(private_key="0x...")
agent = create_react_agent(ChatOpenAI(model="gpt-4o"), tools)

result = agent.invoke({"messages": [
    {"role": "user", "content": "What was NVDA's trading volume on the day of their last earnings?"}
]})
```

## CrewAI

```python
from cabrini import get_crewai_tools
from crewai import Agent, Task, Crew

tools = get_crewai_tools(private_key="0x...")

analyst = Agent(
    role="Financial Analyst",
    goal="Analyze stock performance using real market data",
    tools=tools,
)

task = Task(
    description="Compare AAPL and MSFT intraday volatility on 2024-06-15",
    agent=analyst,
)

Crew(agents=[analyst], tasks=[task]).kickoff()
```

## MCP (Claude, Cursor, etc.)

Point any MCP client at `https://cabrini.ai/mcp`:

```json
{
  "mcpServers": {
    "cabrini": {
      "url": "https://cabrini.ai/mcp"
    }
  }
}
```

## All endpoints

| Method | Price | Description |
|--------|-------|-------------|
| `query(ticker, date)` | $0.025 | Full trading day of intraday bars |
| `daily(ticker, start, end)` | $0.01/day | Daily OHLCV |
| `batch(tickers, date)` | $0.10 | Up to 10 tickers at once |
| `range(ticker, start, end)` | $0.015 | Multi-day intraday |
| `bars(ticker, date)` | $0.02 | Flexible bar query |
| `scan(date)` | $0.25 | All tickers on a date |
| `tickers(date)` | $0.005 | List traded tickers |
| `company(ticker)` | $0.001 | Company metadata |
| `fundamentals(ticker)` | $0.02 | SEC quarterly data |
| `filings(ticker)` | $0.02 | SEC filings + text |
| `insiders(ticker)` | $0.02 | Insider transactions |
| `brief(ticker)` | $0.04 | Full research brief |

## How payment works

Every paid request uses [x402](https://www.x402.org/) — an open protocol for HTTP micropayments:

1. Client sends request → server returns `402` with a `PAYMENT-REQUIRED` header
2. Client signs a USDC transfer authorization (EIP-3009)
3. Client replays request with `X-PAYMENT` header containing the signed authorization
4. Cloudflare edge worker verifies signature, submits to Base, forwards to origin
5. Origin returns data

The `Cabrini` client handles all of this automatically. You just need a wallet with USDC on Base.

## Get USDC on Base

1. Bridge from Ethereum: [bridge.base.org](https://bridge.base.org)
2. Buy directly: Coinbase → send USDC to your wallet on Base network
3. Faucet (testnet): not needed, mainnet USDC is cheap ($0.025/query)

## Links

- Homepage: https://cabrini.ai
- API docs: https://cabrini.ai/docs
- Agent guide: https://cabrini.ai/agents
- MCP endpoint: https://cabrini.ai/mcp

<!-- mcp-name: ai.cabrini/market-data -->
