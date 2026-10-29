# QuantScore

Development branch: `project/quantscore-submission`. See [current progress](docs/PROGRESS.md) and GitHub Actions for commit-specific verification.

A local, historical stock research application for INF2003. React + FastAPI + PostgreSQL + MongoDB.

## Quick start

Prerequisite: Docker Desktop (or Docker Engine with the Compose plugin), running. Allow several GB of disk space. Ports for PostgreSQL and MongoDB are internal to Docker; the UI binds to localhost only. No cloud accounts or API keys are needed.

1. Extract this project.
2. Put the original three uploads into `data/` with these exact names:
   - `financialinformation.zip`
   - `listingdayto2023.zip`
   - `financialnews.zip`
The normalized SEC sample is included in the repository and imported automatically alongside the original datasets.

3. Open a terminal in the project folder and run:

```sh
docker compose up -d --build
docker compose run --rm app python -m app.import_data
```

4. Open **http://localhost:8000**. API documentation: **http://localhost:8000/docs**.
5. Use Explore to search and filter, select checkboxes to Compare, open a company for its score/notes, create a Portfolio, and browse News.

The default import uses **2019-01-01 through 2020-06-05**, 505 companies and available matching prices/news. Company fundamentals are an undated snapshot: they must not be presented as known at the simulated trading date. Source ZIPs are streamed, not extracted wholesale. See `docs/data-audit.json` for actual source counts and SHA-256 checksums.

First import takes time and prints companies, prices and final counts. A second import upserts existing records. Do not run multiple importers at once. A failed batch can be retried; earlier batches remain committed. Keep the same import window for repeatability. Increasing the window adds data; decreasing it does **not** delete previously imported data.

For a wider date window:

```sh
docker compose run --rm app python -m app.import_data --start 2010-01-01 --end 2023-08-03
```

News ends in 2020 in this source; later prices do not imply later news coverage.

## Team ownership

| Owner | Feature | Main code |
|---|---|---|
| Desmond | Search, stock details, sector context | `sql/001_schema.sql`, stock endpoints |
| Damien | Transparent sector-relative scoring | `backend/app/logic.py`, score detail panel |
| Adora | SQL screener and comparison | stock filtering and compare endpoints |
| Au Myat | Transactions, holdings, portfolio risk | portfolio/trade endpoints |
| Calson | News, sentiment, MongoDB research-note CRUD | MongoDB setup, news/notes endpoints |

The API currently shares one local classroom demo user. This is deliberate: it is **not a multi-user authenticated service**. Do not expose it publicly without adding authentication, authorisation, credentials management and operational hardening.

## Important scope decisions

- Scoring offers the baseline **valuation 75% / dividend 25%** and a four-factor SEC sample model (25% each valuation, dividend, annual revenue growth and net margin). The committed `data/fundamentals.csv` retains filing provenance. Missing coverage or fewer than two fundamental peers produces N/A. Original valuation/dividend data remains undated, so this is mixed-date research, not a score backtest.
- New portfolios trade adjusted-price units and can advance forward through imported dates. Quotes must be at most seven days old. Adjusted units assume reinvested distributions, not actual share quantities; no real orders are sent. Existing raw-close portfolios retain their fixed-date policy.
- Risk is trailing volatility and maximum drawdown of **fixed current holdings**, using adjusted returns anchored to the portfolio price basis. A separate transaction-aware daily value chart reconstructs actual simulated cash and holdings from the ledger. No fees, slippage or dividend cash flows are modelled.
- News sentiment is an explicitly unvalidated keyword baseline. It can fail on negation and financial context.
- Price-file ticker mismatches are rejected. Corporate renames are not guessed.
- Source high/low labels are reversed for all 505 financial records. Import stores the lower value as low and higher as high; raw ZIPs remain unchanged.

## Checks

Pure logic and API validation tests (no database required):

```sh
docker compose run --rm app python -m pytest -q
```

After import, enable actual database integration tests:

```sh
docker compose run --rm -e QUANT_INTEGRATION=1 app python -m pytest -q
```

Integration tests create/delete isolated demo portfolios and notes. They verify cash rollback, idempotent retries, buy/sell, constraints, note CRUD, query filtering and aggregation. To test simultaneous buys on native PostgreSQL, add `-e QUANT_CONCURRENCY=1` to the integration-test command. This test must not be run against a single-session embedded engine.

Run the equivalent-workload benchmark:

```sh
docker compose run --rm app python -m app.benchmark --limit 50000 --repeats 20 > benchmark.json
```

It loads identical prices into separate benchmark tables/collections, checks equal results, alternates warm sequential SQL/Mongo aggregation queries and records latency samples. It replaces **benchmark-only** data on each run. Serial queries/second is not concurrent throughput. Run on native PostgreSQL and MongoDB before making performance claims; do not compare an embedded SQL engine against native MongoDB as a database ranking.

## Browser smoke test

With the app running and datasets imported, in `scripts/browser/` run `npm install`, `npx playwright install chromium`, then `npm test`. The default target is http://127.0.0.1:8000; override it with `BASE_URL`. This creates and removes a test portfolio and research note. It exercises stock details, note CRUD, comparison, buy/sell, news filtering and mobile page overflow.

## Development without Docker

Run PostgreSQL and MongoDB yourself, create a `quant` database and user, then set `DATABASE_URL` and `MONGO_URL` in your shell. Defaults in `backend/app/db.py` target localhost. In `backend/`, create a Python 3.12 virtual environment and install `requirements.txt`. Run `python -m app.import_data --data ../data`, then `python -m uvicorn app.main:app --reload`. In another terminal, `cd frontend`, run `npm ci`, then `npm run dev`. Vite proxies `/api` to port 8000.

## Stop, restart and troubleshoot

- Stop: `docker compose down`. Named database volumes remain.
- Restart: `docker compose up -d`.
- Logs: `docker compose logs --tail=100 app postgres mongo`.
- Blank explorer: wait for import completion and click Refresh data.
- Database unavailable: confirm both database health checks pass.
- Missing ZIP: confirm filenames and `data/` location.
- Port 8000 occupied: change the **host** port in `compose.yaml`, e.g. `127.0.0.1:8001:8000`.
- Resetting with `docker compose down -v` deletes all imported data, portfolios and notes. Only do this if you intend to discard them.

## Project layout

- `backend/app/`: API, importer, scoring/risk, Mongo indexes, benchmark.
- `backend/tests/`: unit, validation and opt-in database tests.
- `frontend/`: React source and locked npm dependencies.
- `sql/001_schema.sql`: ten relational tables, constraints, indexes and views.
- `docs/`: architecture, audited data facts, methods, demo plan and verification status.
- `scripts/audit_data.py`: reproducible read-only source audit.

Read `docs/PROGRESS.md` for current results and `docs/VERIFICATION.md` for historical v0.1 evidence before treating this build as submission-ready. Native Docker execution, concurrency testing and team review are required final checks. The package includes USER_MANUAL.md, REPORT_DRAFT.md and an editable demo deck. The report still needs the actual XSite template and authentic team reflections; the video must show every member. See SUBMISSION_CHECKLIST.md.

CI uses Ubuntu 22.04 because MongoDB 8.0 failed its startup kernel compatibility check on the ubuntu-latest runner. If Docker reports SERVER-121912 on your machine, use a supported host/kernel combination rather than disabling database safety checks. Official issue: https://jira.mongodb.org/browse/SERVER-121912 .


## Private submission package

Run `python scripts/package_submission.py --output /absolute/path/QuantScore-submission.zip --deck /absolute/path/QuantScore-demo.pptx` after all required source ZIPs are in data/. This creates a source/data/manual archive and checksum manifest without publishing it. The public repository excludes original source ZIPs and the derived real-price fixture. For a reproducible local benchmark fixture, run `python scripts/prepare_benchmark.py`, then `docker compose run --rm app python -m app.benchmark --csv /data/benchmark-prices.csv.gz --limit 50000 --repeats 20 > benchmark-real.json`.
