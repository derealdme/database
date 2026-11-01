# Verification status

Build milestone: 28 October 2026. This is a functional first implementation, not a claim that all final-submission checks are complete.

## Executed successfully

- Full read-only audit of all 4,195,702 price rows and 1,407,328 rows in the selected raw analyst-news source. The news ZIP also includes two alternate files that are not jointly imported.
- Financial data audit: 505 companies, 11 sectors, 505 reversed high/low pairs, two missing P/E and eight missing P/B values.
- Corrected audit handling of empty CSVs. BF.B.csv and BRK.B.csv contain only headers; there are no detected filename/row ticker mismatches.
- React/Vite production build.
- Python module compilation.
- 14 pure/domain and API-validation tests.
- Seven database integration tests: search/filter/detail/compare; buy/sell and idempotency; rollback on rejected trades; portfolio CRUD; Mongo note CRUD and news aggregation; SQL check/FK constraints; Mongo document validation.
- Combined test run: **21 passed, one skipped**. The skipped test is native PostgreSQL simultaneous-buy concurrency.
- Real source import for 2019-01-01 to 2020-06-05: **505 companies, 140,665 price records, 76,378 candidate news rows and 76,342 unique news documents**.

- Browser smoke test passed: stock details, note create/edit/delete, AAPL/MSFT comparison, portfolio create/buy/sell/delete and news filtering. No browser runtime errors and no document overflow at 390px width.
- Benchmark smoke run on 1,000 identical rows, two repetitions: query outputs matched. Timing data is retained for reproducibility only; this is not a native SQL-versus-NoSQL performance result.

## Test environment and limits

The runtime did not provide Docker or native PostgreSQL. SQL tests ran against the PostgreSQL engine embedded in **PGlite**, exposed through its socket adapter. Mongo tests ran against an actual temporary **MongoDB 8.2.6** process. The delivered Compose configuration instead targets **PostgreSQL 17 and MongoDB 8.0**. Native Compose execution and version-specific differences must be checked on a teammate's machine.

PGlite's connection multiplexing is not native PostgreSQL concurrency. Native simultaneous-buy testing remains necessary; the test is included and gated by `QUANT_CONCURRENCY=1`. No PostgreSQL-versus-MongoDB performance conclusion is justified from this environment.

One test-run deprecation warning came from FastAPI/Starlette's httpx TestClient compatibility. The tests passed. It is not suppressed; future dependency upgrades should address it deliberately.

## Final submission work still needed

1. Run `docker compose up -d --build` and import the source ZIPs on a teammate's machine.
2. Run integration tests with both `QUANT_INTEGRATION=1` and `QUANT_CONCURRENCY=1` on native PostgreSQL.
3. Execute the benchmark on the target hardware and retain real results/environment details.
4. Team review of the reduced score model and fixed-date simulator; verify whether these meet the intended proposal scope.
5. Evaluate sentiment quality on a manually labelled sample if making any accuracy claims.
6. Each teammate reviews and explains their assigned code, records actual contributions and rehearses the demo.
7. Write the final report using the actual XSite template and measured results; create final slides and record all five members. The included report/demo outline is preparatory material.

Browser results are recorded in `browser-verification.json` when successfully completed. Internal screenshot review was used for desktop/mobile layout checks; screenshots are not included as submission evidence.
