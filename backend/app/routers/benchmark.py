"""SQL vs NoSQL performance analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import benchmark as service
from app.services import throughput

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.get("/run")
def run(ticker: str = Query("AAPL", min_length=1, max_length=10),
        days: int = Query(365, ge=30, le=3650),
        runs: int = Query(5, ge=1, le=15),
        only: str | None = Query(None, description="comma-separated scenario keys")):
    keys = [k.strip() for k in only.split(",")] if only else None
    return service.run(ticker, days, runs, keys)


@router.get("/explain")
def explain(ticker: str = Query("AAPL", min_length=1, max_length=10)):
    return service.explain_plan(ticker)


@router.get("/index-impact")
def index_impact(ticker: str = Query("AAPL", min_length=1, max_length=10),
                 runs: int = Query(3, ge=1, le=10)):
    return service.index_impact(ticker, runs)


@router.get("/throughput")
def throughput_run(ticker: str = Query("AAPL", min_length=1, max_length=10),
                   duration: float = Query(5.0, ge=1.0, le=30.0)):
    """Requests/s and p95 at 1, 4, 16, 32 workers. Stub until step 6."""
    try:
        return throughput.run(ticker, duration_s=duration)
    except NotImplementedError as exc:
        raise HTTPException(501, f"Throughput benchmark not implemented yet ({exc})")
