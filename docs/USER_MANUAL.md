# QuantScore user manual

## Installation

Use Docker Desktop or Docker Engine with Compose. Extract the submission ZIP, open its `QuantScore` folder, and confirm the three original ZIPs are in `data/`. No API keys are required. The supplied SEC CSV avoids downloading SEC data during installation.

```sh
docker compose up -d --build
docker compose run --rm app python -m app.import_data
```

Wait for the importer to finish. Open http://localhost:8000 and click Refresh data. The import defaults to 2019-01-01 through 2020-06-05. See README.md for alternate dates and setup troubleshooting. Database volumes survive `docker compose down`; `down -v` permanently deletes them.

## Explore and compare

Enter a company/ticker, optionally select a sector, maximum positive P/E, minimum yield, sort order and score model, then press Apply. Previous/Next changes pages of 50 companies. Select 2–5 checkboxes and choose Compare. Selection persists across pages.

Baseline scoring uses valuation 75% and dividend yield 25%. The SEC sample model uses valuation, dividends, revenue growth and net margin at 25% each. Only 52 companies have sourced annual fundamentals; sufficient components and at least two sampled sector peers are required for a combined score. N/A is meaningful missing coverage. The original valuation/dividend snapshot is undated, so neither model provides validated historical signals.

Click a company to see the component breakdown and valid peers. With SEC facts, the detail also shows annual period, cutoff, filing reference and source link. Change From/To dates and click Update chart. Charts show adjusted prices, not source snapshot prices. Research notes are shared by the local demo account; create, edit or delete them on this page.

## Paper portfolio

Create a named portfolio with $100,000 at a date inside the imported price range. For a progression demo choose 2020-01-02. Enter an available ticker, BUY or SELL, and quantity, then Place simulated trade. Quantities are adjusted-price units rather than literal shares. Prices incorporate provider corporate-action adjustments and implicitly reinvest distributions. No extra dividend cash, fees or slippage is added.

A trade uses the latest price no later than the simulation date, at most seven days old. Insufficient cash or holdings rejects the operation without changing balances. A request UUID prevents duplicate processing when the exact same request is retried. The browser generates a new UUID for each submitted action, so two deliberate submissions are two trades.

Choose a later date and press Advance date. Dates cannot move backward or exceed imported prices. Advancement rejects missing/stale prices for held assets. The value chart reconstructs end-of-day cash and positions from trade simulation dates. The ledger separately displays quote date. Previous/Next pages through the ledger.

The trailing risk panel holds current holdings constant and estimates volatility/drawdown from common historical adjusted returns. It differs from the transaction-aware portfolio value history. Existing portfolios created by the older raw-close version retain fixed dates; create a new portfolio to use advancement.

Rename and Delete apply to the selected portfolio. Deletion removes its holdings and ledger after confirmation. No real orders or broker accounts are involved.

## News

Choose an optional ticker and From/To date range, then Filter news. Previous/Next pages through headlines. The monthly table uses the same ticker/date filter and displays up to 100 latest ticker/month groups. Source links open separately. Sentiment counts fixed positive/negative words and is not a trained or validated classifier.

## Verification and benchmark

After import:

```sh
docker compose run --rm -e QUANT_INTEGRATION=1 -e QUANT_CONCURRENCY=1 app python -m pytest -q
docker compose run --rm app python -m app.benchmark --limit 50000 --repeats 20 > benchmark.json
```

Tests create and remove isolated portfolios and notes. Benchmark preparation replaces only its dedicated `benchmark_prices` table/collection. Preserve benchmark.json with machine details and database versions; warm serial query timing does not establish general database superiority. Do not run competing benchmark processes concurrently.

## Common problems

| Symptom | Action |
|---|---|
| Blank explorer | Wait for import; check ZIP filenames; Refresh data |
| Database unavailable | Inspect `docker compose ps` and service logs |
| N/A four-factor score | Select a covered company such as AAPL; inspect peer/input coverage |
| No recent price | Use a covered ticker/date; never substitute a future quote |
| Cannot advance | Select a later in-range date; check held-ticker coverage or legacy policy |
| Missing news | Try another range/ticker; archive ends in 2020 |
| Port conflict | Change the localhost host port in compose.yaml |

The application shares one classroom demo identity and binds locally. Authentication and production operations are outside this submission implementation.
