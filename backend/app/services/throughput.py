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
import math
import platform
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
    if not values:
        raise ValueError("percentile() of an empty list")
    ordered = sorted(values)
    n = len(ordered)
    rank = max(1, min(n, math.ceil((p / 100.0) * n)))
    return float(ordered[rank - 1])


def summarise(latencies_ms: list[float], errors: int, wall_s: float) -> dict:
    """Turn raw timings from one run into the reported row.

    Returns {"requests", "errors", "req_per_s", "p50_ms", "p95_ms"};
    req_per_s = len(latencies_ms) / wall_s, rounded to 1 dp; ms to 2 dp.
    """
    requests = len(latencies_ms)
    req_per_s = round(requests / wall_s, 1) if wall_s > 0 else 0.0
    if latencies_ms:
        p50_ms = round(percentile(latencies_ms, 50), 2)
        p95_ms = round(percentile(latencies_ms, 95), 2)
    else:
        p50_ms = None
        p95_ms = None
    return {
        "requests": requests,
        "errors": errors,
        "req_per_s": req_per_s,
        "p50_ms": p50_ms,
        "p95_ms": p95_ms,
    }


def run_level(fn: Callable[[], Any], workers: int,
              duration_s: float = DURATION_S) -> dict:
    """Call fn from `workers` threads in a loop for duration_s seconds.

    Each thread records per-call latency in ms and counts exceptions.
    Returns summarise(...) for the combined timings.
    """
    # Warm-up: discard timings so the first connection / cold cache does
    # not pollute the measured level.
    warmup_until = time.monotonic() + WARMUP_S
    while time.monotonic() < warmup_until:
        try:
            fn()
        except Exception:
            pass

    latencies: list[float] = []
    errors = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal errors
        local_latencies: list[float] = []
        local_errors = 0
        end_at = time.monotonic() + duration_s
        while time.monotonic() < end_at:
            start = time.perf_counter()
            try:
                fn()
            except Exception:
                local_errors += 1
                continue
            local_latencies.append((time.perf_counter() - start) * 1000)
        with lock:
            latencies.extend(local_latencies)
            errors += local_errors

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        for future in futures:
            future.result()
    wall_s = time.perf_counter() - wall_start

    return summarise(latencies, errors, wall_s)


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
