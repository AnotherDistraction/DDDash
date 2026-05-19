import os
import asyncio
from datetime import datetime, timezone
from typing import Optional

import praw


FINANCIAL_SUBREDDITS = [
    "wallstreetbets",
    "investing",
    "stocks",
    "options",
    "SecurityAnalysis",
    "StockMarket",
    "ValueInvesting",
]


def _build_reddit() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "MarketDigest/1.0 by MarketBot"),
    )


def _fetch_posts_sync(subreddits: list[str], limit: int) -> list[dict]:
    reddit = _build_reddit()
    posts = []
    for sub in subreddits:
        try:
            subreddit = reddit.subreddit(sub)
            for post in subreddit.hot(limit=limit):
                posts.append({
                    "subreddit": sub,
                    "title": post.title,
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "created_utc": datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    ).isoformat(),
                    "selftext": (post.selftext or "")[:600],
                    "flair": post.link_flair_text,
                })
        except Exception as e:
            posts.append({"subreddit": sub, "error": str(e)})
    return posts


async def fetch_reddit_sentiment(
    subreddits: Optional[list[str]] = None,
    limit: int = 25,
) -> dict:
    subreddits = subreddits or FINANCIAL_SUBREDDITS
    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(
            None, _fetch_posts_sync, subreddits, limit
        )
        return {
            "source": "reddit",
            "subreddits": subreddits,
            "post_count": len([p for p in posts if "error" not in p]),
            "posts": posts,
            "fetched_at": fetched_at,
        }
    except Exception as e:
        return {
            "source": "reddit",
            "error": str(e),
            "posts": [],
            "fetched_at": fetched_at,
        }
