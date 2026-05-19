import os
from datetime import datetime, timezone
from typing import Optional

import httpx


STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"

DEFAULT_SYMBOLS = [
    "SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMD", "MSFT", "AMZN", "META", "GOOGL",
]


def _auth_headers() -> dict:
    token = os.getenv("STOCKTWITS_ACCESS_TOKEN")
    return {"Authorization": f"OAuth {token}"} if token else {}


async def _fetch_trending(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{STOCKTWITS_BASE}/trending/symbols.json")
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "symbol": s.get("symbol"),
            "title": s.get("title"),
            "watchlist_count": s.get("watchlist_count"),
        }
        for s in data.get("symbols", [])
    ]


async def _fetch_symbol_stream(
    client: httpx.AsyncClient, symbol: str
) -> dict:
    resp = await client.get(
        f"{STOCKTWITS_BASE}/streams/symbol/{symbol}.json",
        params={"limit": 30},
    )
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("messages", [])
    sentiments = [
        m["entities"]["sentiment"]["basic"]
        for m in messages
        if m.get("entities", {}).get("sentiment")
    ]
    bull = sentiments.count("Bullish")
    bear = sentiments.count("Bearish")
    return {
        "symbol": symbol,
        "message_count": len(messages),
        "bullish": bull,
        "bearish": bear,
        "sentiment_ratio": round(bull / max(bull + bear, 1), 2),
        "sample_messages": [m.get("body", "")[:200] for m in messages[:5]],
    }


async def fetch_stocktwits(
    symbols: Optional[list[str]] = None,
) -> dict:
    symbols = symbols or DEFAULT_SYMBOLS
    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(
            headers=_auth_headers(), timeout=15.0
        ) as client:
            trending = await _fetch_trending(client)

            streams = []
            for symbol in symbols:
                try:
                    stream = await _fetch_symbol_stream(client, symbol)
                    streams.append(stream)
                except Exception as e:
                    streams.append({"symbol": symbol, "error": str(e)})

        return {
            "source": "stocktwits",
            "trending": trending,
            "symbol_streams": streams,
            "fetched_at": fetched_at,
        }
    except Exception as e:
        return {
            "source": "stocktwits",
            "error": str(e),
            "trending": [],
            "symbol_streams": [],
            "fetched_at": fetched_at,
        }
