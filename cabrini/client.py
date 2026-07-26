"""Core Cabrini client with automatic x402 payment."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx
from eth_account import Account
from eth_account.messages import encode_typed_data

BASE_URL = "https://cabrini.ai"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CHAIN_ID = 8453


class Cabrini:
    """Client that automatically pays x402 invoices and returns data.

    Usage:
        from cabrini import Cabrini

        c = Cabrini(private_key="0x...")
        bars = c.query("AAPL", "2024-01-15")
    """

    def __init__(
        self,
        private_key: str,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ):
        self._account = Account.from_key(private_key)
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout)

    @property
    def address(self) -> str:
        return self._account.address

    def query(self, ticker: str, date: str, interval: int = 3, adjusted: bool = False) -> Dict[str, Any]:
        """Intraday bars for one ticker/date. $0.025

        Each bar carries pct_open/pct_high/pct_low/pct_close — fractional change
        from that day's open — plus volume and transactions. For absolute prices,
        get the open from daily() and compute price = day_open * (1 + pct).
        """
        return self._paid_request("POST", "/v1/query", json={
            "ticker": ticker, "date": date, "interval": interval, "adjusted": adjusted,
        })

    def daily(self, ticker: str, start: str, end: str, adjusted: bool = False) -> Dict[str, Any]:
        """Daily OHLCV bars plus VWAP for a date range. $0.001 per year.

        This is the endpoint that carries absolute price levels.
        """
        return self._paid_request("POST", "/v1/daily", json={
            "ticker": ticker, "start": start, "end": end, "adjusted": adjusted,
        })

    def batch(self, tickers: list, date: str, interval: int = 3) -> Dict[str, Any]:
        """Intraday bars for several tickers on one date. $0.02 per ticker, no limit.

        Each ticker is referenced to its own daily open.
        """
        return self._paid_request("POST", "/v1/batch", json={
            "tickers": tickers, "date": date, "interval": interval,
        })

    def range(self, ticker: str, start: str, end: str, interval: int = 60) -> Dict[str, Any]:
        """Multi-day intraday bars. $0.01 per trading day, no limit.

        Percentages reset to each day's own open — they are not cumulative.
        """
        return self._paid_request("POST", "/v1/range", json={
            "ticker": ticker, "start": start, "end": end, "interval": interval,
        })

    def bars(self, ticker: str, date: str, interval: int = 60) -> Dict[str, Any]:
        """Resampled intraday bars at a custom interval. $0.015 per day."""
        return self._paid_request("POST", "/v1/bars", json={
            "ticker": ticker, "date": date, "interval": interval,
        })

    def scan(self, date: str, **criteria: Any) -> Dict[str, Any]:
        """Screen every US stock on a date. $0.10

        At least one criterion is required or the API returns 400. Accepts
        gap_up_pct, gap_down_pct, change_pct_min, change_pct_max, volume_min,
        volume_ratio_min, transactions_min, limit — all in percent (5 = 5%).

        Returns pct_change, pct_gap, volume and volume_ratio per match
        (fractional: 0.05 = 5%).
        """
        if not criteria:
            raise ValueError(
                "scan() needs at least one criterion, e.g. "
                "scan(date, volume_min=1_000_000) or scan(date, gap_up_pct=5)"
            )
        return self._paid_request("POST", "/v1/scan", json={"date": date, **criteria})

    def tickers(self, date: str) -> Dict[str, Any]:
        """List all tickers traded on a date. $0.005"""
        return self._paid_request("GET", "/v1/tickers", params={"date": date})

    def company(self, ticker: str) -> Dict[str, Any]:
        """Company profile from SEC EDGAR. $0.005"""
        return self._paid_request("GET", "/v1/company", params={"ticker": ticker})

    def fundamentals(self, ticker: str) -> Dict[str, Any]:
        """SEC quarterly fundamentals. $0.02"""
        return self._paid_request("POST", "/v1/fundamentals", json={"ticker": ticker})

    def filings(self, ticker: str, form_type: Optional[str] = None) -> Dict[str, Any]:
        """SEC filing index. $0.01, or $0.05 with extracted section text."""
        body = {"ticker": ticker}
        if form_type:
            body["form_type"] = form_type
        return self._paid_request("POST", "/v1/filings", json=body)

    def insiders(self, ticker: str) -> Dict[str, Any]:
        """Insider transactions. $0.02"""
        return self._paid_request("POST", "/v1/insiders", json={"ticker": ticker})

    def brief(self, ticker: str) -> Dict[str, Any]:
        """Joined research brief: price + fundamentals + insiders + splits. $0.25"""
        return self._paid_request("POST", "/v1/brief", json={"ticker": ticker})

    def _paid_request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make a request; if 402, sign payment and retry."""
        url = self._base_url + path
        resp = self._http.request(method, url, **kwargs)

        if resp.status_code == 402:
            payment_header = resp.headers.get("payment-required")
            if not payment_header:
                raise PaymentError("Got 402 but no PAYMENT-REQUIRED header")

            import base64
            payment_req = json.loads(base64.b64decode(payment_header))
            signature = self._sign_payment(payment_req)

            kwargs.setdefault("headers", {})
            kwargs["headers"]["X-PAYMENT"] = signature
            resp = self._http.request(method, url, **kwargs)

        if resp.status_code != 200:
            raise CabriniError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        return resp.json()

    def _sign_payment(self, payment_req: dict) -> str:
        """Sign the x402 EIP-712 payment authorization."""
        accepts = payment_req["accepts"][0]

        domain = {
            "name": accepts["extra"]["name"],
            "version": accepts["extra"]["version"],
            "chainId": CHAIN_ID,
            "verifyingContract": accepts["asset"],
        }

        message = {
            "from": self._account.address,
            "to": accepts["payTo"],
            "value": int(accepts["amount"]),
            "validAfter": 0,
            "validBefore": 2**48 - 1,
            "nonce": self._payment_nonce(),
        }

        types = {
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ]
        }

        full_message = {
            "types": types,
            "primaryType": "TransferWithAuthorization",
            "domain": domain,
            "message": message,
        }

        signable = encode_typed_data(full_message=full_message)
        signed = self._account.sign_message(signable)

        import base64
        payload = json.dumps({
            "x402Version": 2,
            "scheme": "exact",
            "network": "eip155:8453",
            "payload": {
                "signature": signed.signature.hex(),
                "authorization": {
                    "from": message["from"],
                    "to": message["to"],
                    "value": str(message["value"]),
                    "validAfter": str(message["validAfter"]),
                    "validBefore": str(message["validBefore"]),
                    "nonce": message["nonce"].hex() if isinstance(message["nonce"], bytes) else message["nonce"],
                },
            },
        })
        return base64.b64encode(payload.encode()).decode()

    def _payment_nonce(self) -> bytes:
        """Generate a random nonce for the payment."""
        import os
        return os.urandom(32)


class CabriniError(Exception):
    pass


class PaymentError(CabriniError):
    pass
