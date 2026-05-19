import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from analysis import run_analysis
from fetchers import (
    fetch_fred_indicators,
    fetch_gurufocus,
    fetch_reddit_sentiment,
    fetch_stocktwits,
)

DIGESTS_DIR = Path(__file__).parent.parent / "data" / "digests"
DIGESTS_DIR.mkdir(parents=True, exist_ok=True)

ET = pytz.timezone("America/New_York")

app = FastAPI(
    title="Market Intelligence Digest API",
    description="Real-time market sentiment and swing trade signals",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_running_sessions: set[str] = set()


# ---------------------------------------------------------------------------
# Core digest logic
# ---------------------------------------------------------------------------

async def _gather_raw_data() -> dict:
    results = await asyncio.gather(
        fetch_reddit_sentiment(),
        fetch_stocktwits(),
        fetch_fred_indicators(),
        fetch_gurufocus(),
        return_exceptions=True,
    )
    labels = ["reddit", "stocktwits", "fred", "gurufocus"]
    return {
        label: (r if not isinstance(r, Exception) else {"error": str(r)})
        for label, r in zip(labels, results)
    }


async def _save_digest(digest: dict) -> Path:
    ts = datetime.now(ET).strftime("%Y-%m-%d_%H%M")
    session = digest.get("session", "manual")
    filename = DIGESTS_DIR / f"digest_{ts}_{session}.json"
    async with aiofiles.open(filename, "w") as f:
        await f.write(json.dumps(digest, indent=2, default=str))
    return filename


async def run_digest(session: str) -> dict:
    raw = await _gather_raw_data()
    digest = await run_analysis(raw, session=session)
    await _save_digest(digest)
    return digest


# ---------------------------------------------------------------------------
# APScheduler — 6 AM and 6 PM ET
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler(timezone=ET)


@app.on_event("startup")
async def startup():
    scheduler.add_job(
        run_digest,
        CronTrigger(hour=6, minute=0, timezone=ET),
        args=["morning"],
        id="morning_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        run_digest,
        CronTrigger(hour=18, minute=0, timezone=ET),
        args=["evening"],
        id="evening_digest",
        replace_existing=True,
    )
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_digest_files() -> list[dict]:
    digests = []
    for path in sorted(DIGESTS_DIR.glob("digest_*.json"), reverse=True):
        try:
            digests.append(json.loads(path.read_text()))
        except Exception:
            pass
    return digests


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler.running,
        "next_runs": [
            {
                "job_id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ],
    }


@app.get("/status")
async def status():
    digests = _load_digest_files()
    return {
        "digest_count": len(digests),
        "latest_digest_at": digests[0].get("created_at") if digests else None,
        "running_sessions": list(_running_sessions),
        "scheduler_jobs": [
            {
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ],
    }


@app.get("/digest/latest")
async def digest_latest():
    digests = _load_digest_files()
    if not digests:
        raise HTTPException(status_code=404, detail="No digests available yet")
    return digests[0]


@app.get("/digest/all")
async def digest_all(limit: int = 20):
    digests = _load_digest_files()
    return {
        "count": len(digests),
        "digests": digests[:limit],
    }


@app.post("/digest/run/{session}")
async def digest_run(session: str, background_tasks: BackgroundTasks):
    safe_session = session.replace("/", "_").replace("..", "")[:32]

    if safe_session in _running_sessions:
        raise HTTPException(status_code=409, detail=f"Session '{safe_session}' already running")

    async def _run_and_cleanup(s: str):
        _running_sessions.add(s)
        try:
            await run_digest(s)
        finally:
            _running_sessions.discard(s)

    background_tasks.add_task(_run_and_cleanup, safe_session)
    return {
        "status": "started",
        "session": safe_session,
        "message": f"Digest '{safe_session}' running in background. Poll /digest/latest for results.",
    }
