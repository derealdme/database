# Performance Analysis — MySQL vs MongoDB

Measured on the loaded QuantScore dataset. Reproduce from the **SQL vs NoSQL**
page in the app, or:

```bash
curl "http://127.0.0.1:8000/api/benchmark/run?ticker=AAPL&runs=7&days=2200"
```

## Method

A comparison is only meaningful if both engines answer the *same question*
over the *same rows* with *comparable resources*. Three things had to be
equalised before any number here was worth reporting.

**1. Same data.** `etl/step4_benchmark.py` mirrors each corpus into the other
engine — the news documents into MySQL `bench_news`, the price rows into
MongoDB `bench_prices`. Each engine therefore plays to its strength on one
dataset and against its grain on the other.

**2. Same indexes.** The MySQL index set on `bench_news` mirrors MongoDB's
one-for-one:

| MongoDB | MySQL |
|---|---|
| `{ticker: 1, published_at: -1}` | `idx_bench_ticker_time` |
| `{published_at: -1}` | `idx_bench_time` |
| `{sentiment.label: 1, published_at: -1}` | `idx_bench_sentiment_time` |
| text index on `headline` | `FULLTEXT ftx_bench_headline` |

**3. Same cache.** MongoDB runs with `--wiredTigerCacheSizeGB 1`. MySQL's
default `innodb_buffer_pool_size` is 128 MB, smaller than the working set,
so it was raised to 1 G in `docker-compose.yml`.

**Measurement.** Each scenario runs once to warm the cache, then seven more
times; the median is reported with the standard deviation.

### The two results that changed — and why they matter

Both initial runs looked decisive in MongoDB's favour. Both were measuring
configuration, not database technology.

| Scenario | Unequal indexes | Unequal cache | Equalised | MongoDB |
|---|---|---|---|---|
| Range scan + filter | 236.84 ms | 43.99 ms | **17.22 ms** | 9.57 ms |
| Grouped aggregation | 2470.13 ms | 2365.31 ms | **818.77 ms** | 1509.94 ms |

Adding `(sentiment_label, published_at)` turned a *33× MongoDB win* on the
range scan into a *1.8×* one. Raising the buffer pool to match MongoDB's
cache turned the grouped aggregation from a *1.6× MongoDB win* into a
*1.8× MySQL win* — the result flipped sides.

**This is the most useful finding in the study.** Most published "NoSQL is
faster than SQL" comparisons are measuring an index that was never created
or a cache that was never sized, not the engines.

## Results

Dataset: 325,118 news rows / 325,118 news documents; 698,614 price rows /
400,000 price documents. Median of 7 runs, Windows 11, MySQL 8.4 and
MongoDB 7.0 in Docker, 1 GB cache each.

| Scenario | What it asks | MySQL | MongoDB | Faster |
|---|---|---|---|---|
| Point lookup | 50 newest headlines for one ticker | 13.13 ms | **4.66 ms** | MongoDB 2.8× |
| Range scan + filter | Negative headlines in a date window | 17.22 ms | **9.57 ms** | MongoDB 1.8× |
| Grouped aggregation | Count + mean sentiment per ticker | **818.77 ms** | 1509.94 ms | MySQL 1.8× |
| Time bucketing | Monthly volume and mean sentiment | **375.36 ms** | 544.09 ms | MySQL 1.5× |
| Full-text search | Headlines matching "earnings" | 417.88 ms | **5.33 ms** | MongoDB 78× |
| Time-series scan | Full price history for one ticker | 50.35 ms | **16.80 ms** | MongoDB 3.0× |
| Join vs embedded lookup | Top movers with company + sector | **16.28 ms** | 261.75 ms | MySQL 16× |

**MySQL 3 wins, MongoDB 4 wins.** Total 1,709 ms vs 2,352 ms.

## Interpretation

**Where MongoDB wins.** Point lookups, range scans and time-series scans all
return whole records that MongoDB stores contiguously as one BSON document,
while MySQL assembles a row from a clustered index and projects typed
columns. Real, but modest — 1.8×–3.0× once indexing and cache are equal.

The exception is full-text search at **78×**. MySQL's `MATCH … AGAINST` in
natural-language mode computes a relevance score for every matching row
before applying `LIMIT`; MongoDB's text index streams matches and stops
early. For a headline-search feature this is a genuine architectural
advantage, and it is why the sentiment feed is served from MongoDB.

**Where MySQL wins.** The join scenario is the clearest result in the table
at **16×**. Joining three indexed tables is precisely what a relational
optimiser is built for, while `$lookup` is a per-document nested loop with
no hash-join strategy available. Anything combining entities belongs on the
relational side — which is how the portfolio, holdings and screener features
are built.

Grouped aggregation and time bucketing also go to MySQL once the cache is
sized properly: `GROUP BY` over an indexed column into a temporary table
beats `$group` streaming through documents, and `DATE_FORMAT` is cheaper
than `$dateTrunc` at this scale.

**What the index is worth.** The same point lookup, with every index on
`bench_news` hidden from the optimiser:

| | Median |
|---|---|
| With indexes | 11.47 ms |
| Forced full scan | 185.08 ms |
| **Speed-up** | **16.1×** |

`EXPLAIN` on the indexed version reports `type=ref`,
`key=idx_bench_ticker_time`, `rows=942`, `Extra=Backward index scan` — the
optimiser walks the composite index backwards and never touches the other
324,000 rows. Hiding the indexes forces a scan of all of them.

## Conclusion for the architecture

The measurements support the split the application actually uses:

| Data | Store | Evidence |
|---|---|---|
| Users, portfolios, trades | MySQL | Needs ACID; joins win 16× |
| Companies, fundamentals, prices | MySQL | Joins and `GROUP BY`; composite PK gives a 16× index win |
| News headlines + sentiment | MongoDB | Text search 78×, point lookups 2.8× |
| Company profiles | MongoDB | Variable schema — a modelling question, not a speed one |
| Activity logs | MongoDB | TTL expiry, no referential integrity needed |

## Throughput under concurrent load

The results above are single-request latency: one query, measured median of
seven sequential runs. The proposal also asked for *throughput* — how many
requests per second each store sustains as concurrent load rises — which is
a different question. Measured by `backend/app/services/throughput.py`:

- The same 3 of the 7 scenarios above, reused unmodified: point lookup,
  grouped aggregation, time-series scan (same queries, same indexes, same
  `bench_news` / `bench_prices` mirrored data as the latency section).
- 1, 4, 16, 32 concurrent worker threads, each looping the query for a fixed
  10 s window per level, after a 2 s warm-up (discarded).
- MySQL's connection pool is `pool_size=10 + max_overflow=20 = 30`, below the
  32-worker level by design — that figure is reported as measured, not hidden
  by resizing the pool.

Environment: Python 3.14.3, Darwin/arm64 (Apple Silicon), Docker Desktop,
MySQL 8.4 and MongoDB 7.0.14 containers on the same host. **A different
machine from the latency section above** (that was Windows 11) — absolute
numbers are not comparable between the two sections; the shape of each
store's scaling curve is.

### Point lookup (50 most recent headlines for one ticker)

| Store | Workers | req/s | p50 ms | p95 ms |
|---|---|---|---|---|
| MySQL | 1 | 1,437.7 | 0.69 | 0.72 |
| MySQL | 4 | 3,046.5 | 1.29 | 1.66 |
| MySQL | 16 | 3,216.2 | 4.76 | 7.73 |
| MySQL | 32 | 3,157.2 | 9.02 | 15.23 |
| MongoDB | 1 | 2,616.3 | 0.34 | 0.58 |
| MongoDB | 4 | 9,516.3 | 0.41 | 0.57 |
| MongoDB | 16 | 8,240.9 | 1.79 | 3.70 |
| MongoDB | 32 | 7,966.8 | 3.63 | 8.24 |

MySQL's throughput is flat from 16 to 32 workers while p50 nearly doubles
(4.76 → 9.02 ms): the 30-connection pool is close to saturated, so extra
workers mostly queue. MongoDB peaks at 4 workers (9,516 req/s) and declines
past that; with no server-side connection ceiling here, the drop is
client-side — a Python thread pool contending on the GIL for a
sub-millisecond query, not the database.

### Grouped aggregation (article count + mean sentiment per ticker)

| Store | Workers | req/s | p50 ms | p95 ms |
|---|---|---|---|---|
| MySQL | 1 | 7.3 | 135.15 | 143.71 |
| MySQL | 4 | 8.2 | 481.83 | 532.78 |
| MySQL | 16 | 7.8 | 2,055.65 | 2,599.21 |
| MySQL | 32 | 7.8 | 3,863.99 | 4,297.44 |
| MongoDB | 1 | 10.0 | 99.57 | 101.04 |
| MongoDB | 4 | 37.3 | 106.42 | 111.38 |
| MongoDB | 16 | 58.0 | 274.38 | 369.53 |
| MongoDB | 32 | 56.0 | 560.77 | 691.30 |

The sharpest contrast in the benchmark. MySQL's throughput never rises past
~8 req/s regardless of worker count — the `GROUP BY … HAVING` is effectively
serialised server-side, so concurrent clients only queue: p50 grows 28×
(135 ms → 3,864 ms) for no throughput gain. MongoDB's `$group` pipeline
scales to 58 req/s at 16 workers (5.8×) before plateauing, with p50 growing
only 2.8×.

**This conflicts with the latency section above**, which found MySQL 1.8×
faster than MongoDB on this same query shape (818.77 ms vs 1,509.94 ms,
`days=2200`). Here, at a single worker, MongoDB is faster (99.57 ms vs
135.15 ms, `days=365`). Two things differ between the two measurements, not
one: the machine (Windows 11 vs this Apple Silicon Mac) and the date window
(2,200 days vs 365 days, which changes how many rows the `HAVING n >= 20`
aggregation touches). **Before this goes in the report, re-run one of the
two benchmarks so both use the same machine and the same `days` window** —
otherwise this table and the "Grouped aggregation … goes to MySQL" claim
above are not actually comparable, and the report would be asserting two
different things from two different setups.

### Time-series scan (full price history for one ticker)

| Store | Workers | req/s | p50 ms | p95 ms |
|---|---|---|---|---|
| MySQL | 1 | 160.3 | 6.44 | 7.17 |
| MySQL | 4 | 251.5 | 15.52 | 20.96 |
| MySQL | 16 | 258.5 | 59.74 | 92.81 |
| MySQL | 32 | 254.5 | 113.23 | 193.03 |
| MongoDB | 1 | 370.6 | 2.76 | 3.07 |
| MongoDB | 4 | 1,911.9 | 1.97 | 2.91 |
| MongoDB | 16 | 2,020.4 | 7.63 | 12.56 |
| MongoDB | 32 | 1,972.9 | 15.54 | 26.94 |

Same shape as the point lookup: both stores plateau past 4 workers, but
MongoDB's plateau sits 7–8× higher than MySQL's (~2,000 vs ~255 req/s) at
every concurrency level beyond one worker.

### What this adds, and one thing it does not show

- Errors were 0 throughout, including at 32 MySQL workers past the
  30-connection pool. SQLAlchemy's pool blocks and waits rather than
  raising, so saturation shows up as latency, not failures — **absence of
  errors at 32 workers does not mean the pool has spare capacity**, only
  that it queues instead of rejecting.
- Point lookup and time-series scan are directionally consistent with the
  latency section (MongoDB faster, by a wider margin here) — those two are
  safe to cite together. Grouped aggregation is not, for the reason above,
  and should be re-measured on one machine before the report cites a
  specific multiplier for it.
- These three scenarios were chosen as one representative query per shape
  (point read, aggregate, range scan); the other 4 scenarios in the latency
  table (range scan + filter, time bucketing, full-text search, join vs
  lookup) were not re-run under concurrent load.

Raw results: `docs/throughput.json`.

## Caveats

- Single machine, no network latency. The *latency* section above has no
  concurrent load; see "Throughput under concurrent load" for req/s under
  contention.
- Both engines run in Docker on the same host and compete for CPU; a local
  MariaDB install would differ.
- The news corpus covers 2018–2020 (the overlap between the price and news
  datasets), so time bucketing spans about 30 months.
- Absolute numbers move by 20–30% between runs depending on what else the
  machine is doing. The *ordering* of the results is stable; treat the
  millisecond values as indicative.
- 128,707 duplicate headlines were removed at load time (see
  `etl/step3_documents.py`), so these figures are over unique stories.
