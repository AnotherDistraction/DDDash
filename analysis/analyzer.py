import json
import os
from datetime import datetime, timezone
from typing import Any

import anthropic


MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """You are a senior market analyst producing a structured Market Intelligence Digest.
You receive raw data from Reddit, StockTwits, X/Twitter, FRED macroeconomic indicators, and GuruFocus
valuation data. Your job is to synthesize this into actionable intelligence.

Respond ONLY with valid JSON matching this exact schema — no markdown, no explanation, just JSON:

{
  "sentiment_score": <float 0.0–1.0, where 0=extreme fear, 0.5=neutral, 1.0=extreme greed>,
  "overall_sentiment": <"Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed">,
  "swing_trade_signals": [
    {
      "ticker": <string>,
      "direction": <"LONG" | "SHORT">,
      "confidence": <float 0.0–1.0>,
      "timeframe": <"1-3 days" | "1-2 weeks" | "2-4 weeks">,
      "rationale": <string, max 120 chars>
    }
  ],
  "hot_tickers": [
    {
      "ticker": <string>,
      "buzz_score": <int 0–100>,
      "mentions": <int>,
      "sentiment": <"Bullish" | "Bearish" | "Mixed">
    }
  ],
  "macro_snapshot": <string, 2-4 sentences summarizing macro environment>,
  "action_items": [<string, max 80 chars each>, ...],
  "risk_flags": [<string, max 80 chars each>, ...],
  "social_pulse": {
    "reddit": {"mood": <string>, "score": <int 0–100>},
    "stocktwits": {"mood": <string>, "score": <int 0–100>},
    "x": {"mood": <string>, "score": <int 0–100>}
  },
  "key_themes": [<string>, ...]
}

Keep swing_trade_signals to 3–6 entries, hot_tickers to 5–10, action_items to 3–6, risk_flags to 2–5."""


def _truncate_for_context(data: dict, max_chars: int = 40_000) -> str:
    raw = json.dumps(data, default=str)
    if len(raw) <= max_chars:
        return raw
    # Trim post bodies and tweet text to keep within token budget
    if "reddit" in data and "posts" in data["reddit"]:
        for p in data["reddit"]["posts"]:
            p["selftext"] = p.get("selftext", "")[:100]
    if "x" in data and "results" in data["x"]:
        for r in data["x"]["results"]:
            for t in r.get("sample_tweets", []):
                t["text"] = t.get("text", "")[:100]
    return json.dumps(data, default=str)[:max_chars]


async def run_analysis(raw_data: dict[str, Any], session: str = "manual") -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_content = f"""Session: {session}
Analysis timestamp: {created_at}

Raw market data:
{_truncate_for_context(raw_data)}

Produce the Market Intelligence Digest JSON now."""

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        text = response.content[0].text.strip()
        # Strip any accidental markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        analysis = json.loads(text.strip())
    except json.JSONDecodeError as e:
        analysis = {
            "error": f"Failed to parse Claude response: {e}",
            "raw_response": text[:500] if "text" in dir() else "",
        }
    except Exception as e:
        analysis = {"error": str(e)}

    analysis["session"] = session
    analysis["created_at"] = created_at
    analysis["sources_fetched"] = list(raw_data.keys())
    return analysis
