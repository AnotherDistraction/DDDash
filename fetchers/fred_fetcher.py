import os
from datetime import datetime, timezone

import httpx


FRED_BASE = "https://api.stlouisfed.org/fred"

# Series ID -> human-readable label
INDICATORS = {
    "GDP": "Real GDP (Quarterly)",
    "CPIAUCSL": "CPI (All Urban Consumers)",
    "UNRATE": "Unemployment Rate",
    "FEDFUNDS": "Federal Funds Rate",
    "DGS10": "10-Year Treasury Yield",
    "M2SL": "M2 Money Supply",
    "UMCSENT": "Consumer Sentiment (Univ. of Michigan)",
    "INDPRO": "Industrial Production Index",
    "HOUST": "Housing Starts",
    "DCOILWTICO": "WTI Crude Oil Price",
}


async def _fetch_series(
    client: httpx.AsyncClient, series_id: str, api_key: str, limit: int = 1
) -> dict:
    resp = await client.get(
        f"{FRED_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        },
    )
    resp.raise_for_status()
    observations = resp.json().get("observations", [])
    if not observations:
        return {"series_id": series_id, "value": None, "date": None}

    latest = observations[0]
    prior = observations[1] if len(observations) > 1 else None

    result = {
        "series_id": series_id,
        "label": INDICATORS.get(series_id, series_id),
        "value": latest.get("value"),
        "date": latest.get("date"),
    }
    if prior:
        try:
            delta = float(latest["value"]) - float(prior["value"])
            result["change"] = round(delta, 4)
            result["prior_value"] = prior["value"]
            result["prior_date"] = prior["date"]
        except (ValueError, TypeError):
            pass

    return result


async def fetch_fred_indicators(
    series_ids: list[str] | None = None,
) -> dict:
    api_key = os.getenv("FRED_API_KEY", "")
    series_ids = series_ids or list(INDICATORS.keys())
    fetched_at = datetime.now(timezone.utc).isoformat()

    if not api_key:
        return {
            "source": "fred",
            "error": "FRED_API_KEY not configured",
            "indicators": [],
            "fetched_at": fetched_at,
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            indicators = []
            for sid in series_ids:
                try:
                    obs = await _fetch_series(client, sid, api_key, limit=2)
                    indicators.append(obs)
                except Exception as e:
                    indicators.append({"series_id": sid, "error": str(e)})

        return {
            "source": "fred",
            "indicators": indicators,
            "fetched_at": fetched_at,
        }
    except Exception as e:
        return {
            "source": "fred",
            "error": str(e),
            "indicators": [],
            "fetched_at": fetched_at,
        }
