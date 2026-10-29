# QuantScore: relational and document databases for historical stock research

**Review draft, 29 October 2026.** This content is ready for team review, not final submission formatting. Transfer it into the actual XSite template, use Calibri 12 and verify the ten-body-page limit. Add the attribute-level ERD from ERD.md and authentic team contributions/reflections. The original source ZIPs stay outside the public repository.

## 1. Background and scope

QuantScore is a local historical research application built with React, FastAPI, PostgreSQL and MongoDB. It supports company search, transparent sector scoring, screening/comparison, simulated portfolios, and news analysis with research notes. These functions demonstrate how relational constraints and transactions can coexist with document-oriented storage and aggregation behind one interface.

The application uses archived data. It does not connect to a broker, execute real orders or provide a validated investment strategy. One shared classroom demo account keeps the scope focused on database design. A public multi-user deployment would require authentication, authorization, secret management, monitoring and backup procedures.

PostgreSQL stores companies, financial measurements, prices and all portfolio monetary records. MongoDB stores news and notes. The choice follows the operations required: portfolio balances need an atomic relational transaction, while headlines and notes use flexible documents and indexed aggregation. News could also be represented relationally; document storage is a design choice rather than evidence that SQL cannot handle it.

## 2. Data and preparation

The supplied company file contains 505 companies in 11 sectors. The source price ZIP contains 503 CSV files but 501 distinct row-level tickers and 4,195,702 rows. BF.B and BRK.B files contain headers only. The raw analyst news source contains 1,407,328 rows across 6,204 tickers. Across the source history, 391 company tickers match prices and 424 match news. Different coverage and historical constituent lists introduce selection and survivorship bias.

The default import selects 2019-01-01 through 2020-06-05, producing 140,665 prices and 76,342 deduplicated headlines from 76,378 eligible news candidates. Original source SHA-256 values and audit counters appear in data-audit.json. ZIP input is streamed and batches are upserted. A retry can continue after a failed batch; decreasing the import window does not remove already imported observations.

All 505 company records have source low above source high. The importer explicitly orders the two bounds and records the correction. Two P/E and eight P/B values are missing. Missing ratios stay null rather than becoming zero. Ticker normalization replaces hyphens with periods, but does not infer mergers or historical renames. Filename/row ticker mismatches are rejected.

The supplied financial snapshot has no verified observation date. To support revenue growth and profitability, a bounded SEC companyfacts extraction adds 52 companies across all 11 source sectors. Eligible facts are annual USD 10-K revenue and matching-period income filed no later than 2020-06-05. The extractor requires 330–400-day annual periods, positive current/prior revenue and suitably spaced prior-year ends. It retains tags, filing accession IDs and source URLs. Ten sectors have five accepted companies each; telecommunications has two. This purposeful sample is not representative market coverage. Dated SEC facts do not make the original undated ratios historically valid.

## 3. Relational design

The application has ten tables: sectors, stocks, financials, annual_fundamentals, prices, users, portfolios, holdings, trades and import_runs. The detailed attributes, data types and cardinalities are documented in ERD.md and implemented in 001_schema.sql.

Sector ID determines its unique name. Ticker identifies each company and its sector. Separate financials and annual_fundamentals tables distinguish the undated source snapshot from the selected annual SEC comparison. The current annual table stores one comparison per company; a multi-snapshot warehouse would need a compound temporal key. The composite price key `(ticker,date)` prevents duplicate daily observations and supports indexed historical quote lookup.

Users own portfolios. Holdings resolves the many-to-many relationship between portfolios and stocks using `(portfolio_id,ticker)`. Each trade references one portfolio and stock. The unique request UUID provides a second identifier for retry handling. Portfolio deletion cascades to its holdings and ledger. Referenced stocks cannot be deleted while operational rows depend on them.

CHECK constraints require positive prices and trade quantities, nonnegative cash/holdings/volume, ordered bounds and a valid trade side. Date constraints restrict the SEC period/filing/cutoff order. Foreign keys enforce company and portfolio references. Holdings and cash deliberately duplicate values derivable from the ledger to support current-state queries; every trade must update these summaries and the ledger atomically.

Views separate reusable query logic. stock_metrics joins company, sector and snapshot data. sector_averages computes conditional aggregates. stock_scores uses window functions for sector ranks, ties and valid-peer counts. research_scores adds annual growth/margin ranks and the optional combined model. Filters operate after sector rankings, so screening does not redefine a company's peer distribution.

## 4. Document design and consistency

News documents contain a deterministic SHA-256 `_id`, ticker, BSON UTC date, title, optional publisher/URL, sentiment and method description. The hash derives from ticker/time/headline, deduplicating repeated records while preserving associations with different companies. Indexes support ticker/date queries and date-only browsing. A validator requires key fields and constrains sentiment to [-1,1].

Research notes store ticker, text and updated timestamp, with a ticker/time index. The API supports document create/read/update/delete, validates company existence and rejects blank text. MongoDB does not enforce a foreign key to PostgreSQL. Direct writes can therefore create inconsistent ticker references. This boundary is explicit, and all monetary changes remain inside PostgreSQL rather than relying on a cross-store transaction.

Monthly news aggregation first matches the selected ticker/date range, groups by ticker and formatted month, then counts articles and averages sentiment. Sorting and limiting bound the returned groups. News pagination uses date plus document ID for deterministic ordering on an unchanged dataset.

## 5. Application functions

### Search, screening and comparison

The stock endpoint uses parameterized values and a whitelist for sortable columns. It supports ticker/name search, sector, positive maximum P/E, minimum yield and minimum score. SQL LIMIT/OFFSET returns pages and a matching count. Ticker breaks score ties. The interface compares two to five companies and provides historical price-date controls. Because scores are sector-relative, identical scores in different sectors do not imply identical financial characteristics.

### Scoring

For a valid metric, midrank percentile is `(number below + 0.5 × number equal) / peer count × 100`. Valuation metrics reverse the percentile so lower positive multiples score higher. Dividend yield uses the percentile directly and allows zero. Negative P/E, nulls and nonfinite values are excluded. All-tied peer groups receive 50.

Valuation averages available P/E, P/S and P/B scores, requiring at least two ratios. The baseline total is 75% valuation plus 25% dividend. The optional four-factor model allocates 25% each to valuation, dividend, annual revenue growth and net profit margin. Growth is `(revenue/previous revenue − 1) × 100`; margin is `net income/revenue × 100`. Higher values score higher among sampled sector peers at the same cutoff. At least two fundamental peers and all components are required. Missing components yield N/A without silent reweighting.

Valuation/dividend ranks use the full source sector universe, while growth/profitability ranks use the smaller SEC sample. This unequal coverage and the unverified original snapshot date limit interpretation. No score backtest, predictive accuracy or return claim is established.

### Portfolio operations

Each trade locks the portfolio row with SELECT FOR UPDATE, checks its retry ID, obtains a nonfuture quote, validates balances, updates cash and holdings, and inserts the ledger record in one transaction. An exception rolls everything back. Concurrent buys serialize on the same lock. Decimal arithmetic avoids binary floating-point errors in monetary calculations; rounded zero-value trades are rejected.

New portfolios trade adjusted-price units and advance only forward within imported coverage. A quote must be no more than seven days old. Adjusted units implicitly incorporate provider corporate-action adjustments and reinvested distributions; they are not literal historical shares. There are no additional dividend payments, fees, slippage, deposits or withdrawals. Older raw-close portfolios retain fixed-date operation.

The performance endpoint reconstructs end-of-day holdings and cash from trades whose simulation date is no later than each observation date. It values positive holdings using the latest eligible price. Missing/stale prices make the affected NAV unavailable and suppress total return for incomplete histories. Quote date is distinct from simulation date, preventing weekend operations from changing Friday's prior history. Final return is final NAV divided by initial cash minus one.

The trailing risk panel answers a different question: it holds current composition and cash constant, uses up to 252 common observations and computes sample daily-return volatility times square root of 252, plus maximum drawdown. It is exposure analysis rather than realized transaction history.

### News and notes

The headline baseline tokenizes words and computes `(positive count − negative count)/(positive count + negative count)`, or zero without matches. It is reproducible but unvalidated. Negation, quoted analyst language and context can cause errors. Monthly aggregation demonstrates database operations rather than classifier quality. The team should independently label a sample before reporting classification metrics.

## 6. Verification

Native CI run 40813508915 at commit 90e464bbc77410c6bed12ae017538974bb79c099 passed on PostgreSQL 17 and MongoDB 8.0. It ran 28 backend tests, five SEC extraction tests, repeated schema initialization, frontend and Docker builds, container smoke checks and browser workflows. Tests cover atomic rollback, retries, overspending concurrency, relational constraints, Mongo validation/CRUD, independent baseline-score parity, pagination, four-factor composition, date-range validation, forward advancement and transaction-aware NAV. SEC tests reject future restatements, mismatched quarterly income, invalid prior revenue and stale periods.

Browser checks exercise model selection, SEC source detail, chart dates, notes, comparison, portfolio creation/buy/advance/sell/deletion, news filtering and mobile overflow. CI uses explicitly synthetic application fixtures to make edge cases repeatable. Passing those tests does not independently validate financial datasets or prove usability on every device. Earlier real-data smoke evidence remains separately labelled in VERIFICATION.md.

## 7. Performance experiment

The benchmark loads identical `(ticker,date,volume)` rows into dedicated PostgreSQL and MongoDB benchmark stores. Both queries group by ticker and return row counts and total volume. Exact result equality is mandatory before timing. The script alternates warm serial queries, records all samples and median/minimum/maximum, includes database versions and PostgreSQL EXPLAIN ANALYZE/BUFFERS output, and reports serial queries per second rather than concurrent throughput.

A reproducible 50,000-row workload covering 139 tickers is prepared from the supplied price source in the default date window. Selection uses ticker/date order and is biased toward earlier ticker names. Native real-data timing has not been completed in this milestone. Synthetic CI timings are only correctness evidence. No database winner or measured speedup is claimed. The team can run the documented benchmark locally without publishing the source data.

## 8. Evaluation and remaining work

The implementation demonstrates a functioning SQL/NoSQL application, relational integrity, explicit transaction boundaries, window-function scoring and document aggregation/CRUD. Major limitations are temporal mismatch, partial ticker coverage, a small SEC sample, shared demo identity and unvalidated sentiment. Offset pagination can shift if records are concurrently inserted; cursor pagination is a suitable future extension. Price-provider revisions can change adjusted historical performance, so source versions and checksums matter.

Before submission, apply the actual XSite template and page/font limits, include a readable ERD, retain real benchmark evidence if performance claims are included, and rehearse the demo on a team machine. Each member must supply authentic contributions and reflections, complete required peer review and appear with their name in the presentation recording. Proposed feature ownership is not evidence of work actually performed. This draft intentionally contains no invented personal reflections.

## References and evidence

- Supplied INF2003_project_description.pdf: assessment scope, report, slides, code/data/manual and video requirements.
- Supplied financialinformation.zip, listingdayto2023.zip and financialnews.zip: audit counts/checksums in docs/data-audit.json.
- SEC companyfacts API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces . Per-company source URLs and accessions: data/fundamentals.csv.
- Implementation and schema: https://github.com/derealdme/database/tree/project/quantscore-submission .
- Native verification: https://github.com/derealdme/database/actions/runs/40813508915 .
