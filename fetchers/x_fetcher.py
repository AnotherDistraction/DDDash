import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx


X_BASE = "https://api.twitter.com/2"

DEFAULT_QUERIES = [
    "stock market lang:en -is:retweet",
    "investing bull bear lang:en -is:retweet",
    "Fed interest rates lang:en -is:retweet",
    "earnings season lang:en -is:retweet",
    "$SPY $QQQ lang:en -is:retweet",
]


def _bearer_headers() -> dict:
    token = os.getenv("X_BEARER_TOKEN", "")
    return {"Authorization": f"Bearer {token}"}


async def _search_recent(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
    start_time: str,
) -> dict:
    resp = await client.get(
        f"{X_BASE}/tweets/search/recent",
        params={
            "query": query,
            "max_results": min(max_results, 100),
            "start_time": start_time,
            "tweet.fields": "public_metrics,created_at,context_annotations",
            "expansions": "author_id",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    tweets = data.get("data", [])

    total_likes = sum(t.get("public_metrics", {}).get("like_count", 0) for t in tweets)
    total_retweets = sum(
        t.get("public_metrics", {}).get("retweet_count", 0) for t in tweets
    )

    return {
        "query": query,
        "count": len(tweets),
        "total_likes": total_likes,
        "total_retweets": total_retweets,
        "sample_tweets": [
            {
                "text": t.get("text", "")[:280],
                "likes": t.get("public_metrics", {}).get("like_count", 0),
                "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
            }
            for t in sorted(
                tweets,
                key=lambda x: x.get("public_metrics", {}).get("like_count", 0),
                reverse=True,
            )[:5]
        ],
    }


async def fetch_x_sentiment(
    queries: Optional[list[str]] = None,
    max_results: int = 50,
    lookback_hours: int = 12,
) -> dict:
    queries = queries or DEFAULT_QUERIES
    fetched_at = datetime.now(timezone.utc)
    start_time = (fetched_at - timedelta(hours=lookback_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    bearer_token = os.getenv("X_BEARER_TOKEN", "")
    if not bearer_token:
        return {
            "source": "x",
            "error": "X_BEARER_TOKEN not configured",
            "results": [],
            "fetched_at": fetched_at.isoformat(),
        }

    try:
        async with httpx.AsyncClient(
            headers=_bearer_headers(), timeout=15.0
        ) as client:
            results = []
            for query in queries:
                try:
                    result = await _search_recent(client, query, max_results, start_time)
                    results.append(result)
                except Exception as e:
                    results.append({"query": query, "error": str(e)})

        return {
            "source": "x",
            "lookback_hours": lookback_hours,
            "results": results,
            "fetched_at": fetched_at.isoformat(),
        }
    except Exception as e:
        return {
            "source": "x",
            "error": str(e),
            "results": [],
            "fetched_at": fetched_at.isoformat(),
        }
