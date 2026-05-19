import os
from datetime import datetime, timezone
from typing import Optional

import httpx


GURUFOCUS_BASE = "https://api.gurufocus.com/public/user"

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "BRK.B"]


async def _fetch_summary(
    client: httpx.AsyncClient, api_key: str, ticker: str
) -> dict:
    url = f"{GURUFOCUS_BASE}/{api_key}/stock/{ticker}/summary"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    summary = data.get("summary", {})
    return {
        "ticker": ticker,
        "gf_score": summary.get("gf_score"),
        "financial_strength": summary.get("financial_strength"),
        "profitability_rank": summary.get("profitability_rank"),
        "valuation": summary.get("valuation"),
        "momentum_rank": summary.get("momentum"),
        "pe_ratio": summary.get("pe_ratio"),
        "pb_ratio": summary.get("pb_ratio"),
        "price_to_gf_value": summary.get("price_to_gf_value"),
        "gf_value": summary.get("gf_value"),
        "market_cap": summary.get("mktcap"),
    }


async def _fetch_guru_trades(
    client: httpx.AsyncClient, api_key: str, ticker: str
) -> list[dict]:
    url = f"{GURUFOCUS_BASE}/{api_key}/stock/{ticker}/guru_trades"
    resp = await client.get(url)
    resp.raise_for_status()
    trades = resp.json().get("guru_trades", [])
    return [
        {
            "guru": t.get("GuruName"),
            "date": t.get("Date"),
            "action": t.get("action"),
            "shares": t.get("Shares"),
            "price": t.get("Price"),
        }
        for t in trades[:5]
    ]


async def fetch_gurufocus(
    tickers: Optional[list[str]] = None,
) -> dict:
    api_key = os.getenv("GURUFOCUS_API_KEY", "")
    tickers = tickers or DEFAULT_TICKERS
    fetched_at = datetime.now(timezone.utc).isoformat()

    if not api_key:
        return {
            "source": "gurufocus",
            "error": "GURUFOCUS_API_KEY not configured",
            "stocks": [],
            "fetched_at": fetched_at,
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            stocks = []
            for ticker in tickers:
                try:
                    summary = await _fetch_summary(client, api_key, ticker)
                    trades = await _fetch_guru_trades(client, api_key, ticker)
                    summary["recent_guru_trades"] = trades
                    stocks.append(summary)
                except Exception as e:
                    stocks.append({"ticker": ticker, "error": str(e)})

        return {
            "source": "gurufocus",
            "stocks": stocks,
            "fetched_at": fetched_at,
        }
    except Exception as e:
        return {
            "source": "gurufocus",
            "error": str(e),
            "stocks": [],
            "fetched_at": fetched_at,
        }
