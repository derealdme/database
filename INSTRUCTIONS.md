# INSTRUCTIONS: finishing `project/final`

For the model (or teammate) doing the remaining work. Do the steps in order, one step per chat.

## Rules

1. **Only touch the files named in the step.** If you think another file needs changing, stop and ask.
2. **Stop and ask if anything is unclear**, if a command fails twice, or if a test can only pass by changing app code. Do not guess.
3. Never weaken a test to make it pass. Never delete `todo(...)` without writing a real assertion in its place.
4. Do not rename the API keys `profitability` / `growth` or the SQL columns `*_score`. Only labels change.
5. Commit at the end of each step: `git commit -m "Step N: <title>"`. Commit under the teammate who owns the feature (see PLAN.md).
6. All commands run from the repo root unless a step says otherwise.

## Already done (step 0, do not redo)

- Branch `project/final` from `project/quantscorev2`.
- README rewritten; SETUP.md counts fixed (49 endpoints, 8 views, 3 procedures, 2 triggers).
- Proxy relabel: `FACTOR_LABELS` / `FACTOR_NOTES` in `backend/app/services/scoring.py`, `frontend/src/lib/factors.js`, used by Scores, StockDetail, Screener, Dashboard. "Growth" preset renamed "Momentum".
- Skeletons: `backend/tests/`, `.github/workflows/ci.yml`, `backend/app/services/throughput.py`, `GET /api/benchmark/throughput` (returns 501 until step 6).

Baseline now: `cd backend && pytest -q` → **17 failed, 2 passed, 7 skipped**. That is expected.

---

## Step 1. Environment

**Files:** none.
**Do:** `docker compose up -d`, copy `.env.example` to `.env`, then:
```bash
cd backend && python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```
**Proof:** `pytest -q` prints `17 failed, 2 passed, 7 skipped`. Anything else: stop and ask.

## Step 2. Unit tests (no database)

**Files:** `backend/tests/unit/test_scoring.py`, `test_security.py`, `test_schemas.py` only.
**Do:** Replace every `todo("step 2", ...)` with real assertions. The string inside each `todo` is the exact assertion to write. Copy the shape of `test_default_weights_sum_to_one`. Use `pytest.raises(ValidationError)` from `pydantic` and `pytest.raises(HTTPException)` from `fastapi`. In `test_security.py`, import `hash_password`, `verify_password`, `create_access_token`, `_decode` from `app.core.security`; never call `current_user` (it needs MySQL).
**Proof:** `cd backend && pytest -q tests/unit` → only the 3 tests in `test_throughput_helpers.py` fail.

## Step 3. CI seed fixture

**Files:** `backend/tests/fixtures/seed_ci.py` only.
**Do:** Replace the `raise SystemExit` with a script that inserts exactly what its docstring lists, using `app.db.mysql` and `app.db.mongo` (add `sys.path` insert for `backend/` at the top, like `backend/run.py`). Use `INSERT IGNORE` / `upsert` so it can run twice. Prices must be positive and dated within the last 30 calendar days of the data you insert. Read `backend/sql/01_schema.sql` for column names; do not guess them.
**Proof:** with Step 1's containers and a fresh schema (`cd etl && python step1_schema.py`), run `cd backend && python tests/fixtures/seed_ci.py` twice. Both runs exit 0 and `SELECT COUNT(*) FROM stocks` = 3.

## Step 4. Integration tests (MySQL + Mongo)

**Files:** `backend/tests/integration/test_trades.py`, `test_mongo.py` only.
**Do:** Replace each `todo("step 4", ...)`. Create a fresh portfolio per test via `app.services.portfolio.create_portfolio` for the seed user. Trades: call `app.db.mysql.call_trade_procedure(...)` and expect an exception whose text contains `INSUFFICIENT_CASH` / `INSUFFICIENT_HOLDINGS`; then re-read `cash_balance` and the transaction count and assert they did not change. CHECK test: insert into `stock_prices` with `close_price = -1` and expect an exception mentioning `chk_price_pos`. Notes: use `app.services.notes` functions.
**Proof:** `cd backend && RUN_INTEGRATION=1 pytest -q tests/integration/test_trades.py tests/integration/test_mongo.py` → all pass.

## Step 5. Concurrency test

**Files:** `backend/tests/integration/test_concurrency.py` only.
**Do:** One portfolio with cash for ~10 buys. Use `concurrent.futures.ThreadPoolExecutor(max_workers=20)` to submit 20 buys of the same ticker; count successes and `INSUFFICIENT_CASH` failures. Assert `cash_balance >= 0`, successes ≤ 10, and holdings quantity in `v_portfolio_holdings` equals the sum of BUY quantities in `transactions`. The procedure locks with `SELECT ... FOR UPDATE`, so this should pass; if it does not, stop and report. Do not change the SQL.
**Proof:** run the command below 5 times; all 5 pass.
`cd backend && RUN_INTEGRATION=1 pytest -q tests/integration/test_concurrency.py`

## Step 6. Throughput benchmark

**Files:** `backend/app/services/throughput.py`, `backend/tests/unit/test_throughput_helpers.py`, `docs/performance-analysis.md` only.
**Do:**
1. Implement `percentile`, `summarise`, `run_level` exactly as their docstrings say. Do not change the constants or the design notes at the top. `run_level`: warm up for `WARMUP_S` (discard timings), then each worker loops until `duration_s` elapses, timing every call with `time.perf_counter()`.
2. Replace the 3 `todo("step 6", ...)` tests.
3. With the full Kaggle data loaded (SETUP.md §4, not the CI seed), run `cd backend && python -m app.services.throughput > ../docs/throughput.json`.
4. Add a section "Throughput" to `docs/performance-analysis.md`: one table, columns Store, Query, Workers, req/s, p95 ms; then the environment (CPU, RAM, OS, Docker or native) and one sentence noting the MySQL pool limit of 30 at 32 workers. Copy numbers from the JSON; do not round differently or invent any.

**Proof:** `cd backend && pytest -q tests/unit` → all pass. `docs/throughput.json` has 24 rows (2 stores × 3 queries × 4 levels).

## Step 7. CI green

**Files:** `.github/workflows/ci.yml` only (and only if a step fails).
**Do:** Push the branch. Open the Actions tab.
**Proof:** all three jobs (unit, integration, frontend) green. If a job fails for a reason not in this file, paste the log and stop.

## Known weaknesses (say so in the report; do not hide them)

- Profitability proxy is price-based, so it is correlated with valuation.
- Growth proxy is price momentum, not fundamental growth.
- Sentiment is an unvalidated keyword baseline.
- Throughput at 32 workers on MySQL includes connection-pool wait.
