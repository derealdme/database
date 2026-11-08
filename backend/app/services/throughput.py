"""Throughput benchmark (STUB -- see INSTRUCTIONS.md step 6).

benchmark.py measures single-request latency. The proposal also promised
throughput, so this module answers a different question: how many
requests per second each store sustains as concurrency rises.

Design (fixed, do not change):
  * Same 3 queries per store, reused from benchmark._scenarios so both
    files measure the same thing: point_lookup, group_by, timeseries_scan.
  * Worker levels 1, 4, 16, 32, run with a ThreadPoolExecutor.
  * Each level runs for a fixed wall-clock DURATION_S after a warm-up.
  * Report per (store, query, workers): requests, errors, req_per_s,
    p50_ms, p95_ms.
  * MySQL pool is pool_size=10 + max_overflow=20 = 30 connections, which
    is below 32 workers. The 32-worker MySQL figure therefore includes
    pool wait time. Report it; do not silently resize the pool.

Run from backend/:  python -m app.services.throughput
"""
from __future__ import annotations

import json
import platform
from typing import Any, Callable

WORKER_LEVELS: tuple[int, ...] = (1, 4, 16, 32)
QUERY_KEYS: tuple[str, ...] = ("point_lookup", "group_by", "timeseries_scan")
STORES: tuple[str, ...] = ("mysql", "mongo")
DURATION_S: float = 10.0
WARMUP_S: float = 2.0


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile, p in [0, 100]. Empty list -> ValueError.

    Example: percentile([1, 2, 3, 4], 50) == 2.0; p=95 on 1..100 == 95.0
    """
    raise NotImplementedError("INSTRUCTIONS.md step 6")


def summarise(latencies_ms: list[float], errors: int, wall_s: float) -> dict:
    """Turn raw timings from one run into the reported row.

    Returns {"requests", "errors", "req_per_s", "p50_ms", "p95_ms"};
    req_per_s = len(latencies_ms) / wall_s, rounded to 1 dp; ms to 2 dp.
    """
    raise NotImplementedError("INSTRUCTIONS.md step 6")


def run_level(fn: Callable[[], Any], workers: int,
              duration_s: float = DURATION_S) -> dict:
    """Call fn from `workers` threads in a loop for duration_s seconds.

    Each thread records per-call latency in ms and counts exceptions.
    Returns summarise(...) for the combined timings.
    """
    raise NotImplementedError("INSTRUCTIONS.md step 6")


def _queries(ticker: str) -> dict[tuple[str, str], Callable[[], Any]]:
    """{(store, query_key): callable}, built from benchmark._scenarios."""
    from app.services import benchmark

    out: dict[tuple[str, str], Callable[[], Any]] = {}
    for sc in benchmark._scenarios(ticker, 365):
        if sc["key"] in QUERY_KEYS:
            out[("mysql", sc["key"])] = sc["sql"]
            out[("mongo", sc["key"])] = sc["mongo"]
    return out


def run(ticker: str = "AAPL", levels: tuple[int, ...] = WORKER_LEVELS,
        duration_s: float = DURATION_S) -> dict:
    """Full matrix: every store x query x worker level."""
    rows = []
    for (store, key), fn in _queries(ticker.upper()).items():
        for workers in levels:
            row = run_level(fn, workers, duration_s)
            rows.append({"store": store, "query": key, "workers": workers, **row})
    return {
        "ticker": ticker.upper(),
        "duration_s": duration_s,
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "system": platform.system(),
        },
        "results": rows,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
