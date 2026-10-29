# Submission progress — 29 October 2026

## Built

- SQL-native baseline scoring and optional four-factor model with traceable SEC annual facts for 52 companies across 11 sectors. Missing data stays N/A; mixed-date limitations are explicit.
- Compatible migration for portfolio starting dates, simulation trade dates and price basis. New adjusted-price portfolios advance forward and reconstruct daily NAV from the transaction ledger. Legacy portfolios retain their original policy.
- Interface controls for scoring model, chart/news date ranges, stock/news/ledger pagination and portfolio advancement/performance.
- Native database, concurrency, parser, migration and browser checks.
- Updated schema/method documentation, user manual, substantive report draft and ten-slide editable demo deck. The deck is included in the private package rather than requiring a public data upload.
- Reproducible private source/data/manual packaging with per-file SHA-256 manifest.
- Real-price benchmark preparation and CSV-input support, with 50,000 factual ticker/date/volume rows across 139 tickers prepared locally.

## Verified

Commit `90e464bbc77410c6bed12ae017538974bb79c099` passed native CI: https://github.com/derealdme/database/actions/runs/40813508915 . Results: 28 backend tests, five SEC extraction tests, repeated schema initialization, frontend build, equivalent-query benchmark smoke, Docker build, built-container health/API/static checks and Chromium workflows. PostgreSQL 17 and MongoDB 8.0 ran on Ubuntu 22.04. Synthetic CI fixtures establish functional behavior, not financial-data quality or real-data performance. Subsequent documentation/package-only edits do not change that application verification boundary.

Historical v0.1 real-data evidence remains in VERIFICATION.md and is not relabelled as a native v0.2 benchmark. The demo deck was rendered and checked as an editable PPTX, but has not been opened in Microsoft PowerPoint here.

## Still needed for submission

1. Run the native real-data benchmark locally, or explicitly authorize publishing the bounded derived price fixture for CI and confirm redistribution rights. Automatic approval review blocked publishing the fixture to this public repository because those rights are unconfirmed. The original ZIPs and derived price rows remain outside public git.
2. Apply the actual XSite report template, Calibri 12 and maximum ten body pages. The supplied brief identifies that template but does not include it. REPORT_DRAFT.md supplies content, not a claim of final-format compliance.
3. Team review and a clean installation rehearsal on the demonstration machine. CI verifies container execution but cannot establish that each teammate's machine works.
4. Authentic contributions/reflections, required peer review and a rehearsed video of at most ten minutes, with all five members presenting and named. These cannot be fabricated or recorded on the team's behalf.
5. Sentiment remains an explicitly unvalidated baseline. Independent human labels are needed before making accuracy claims. No trained classifier or authentication requirement was established by the supplied brief.

## Repository policy

Development remains on `project/quantscore-submission`, draft PR https://github.com/derealdme/database/pull/1 . Main is unchanged. Public source contains no original large dataset ZIPs, private derived price fixture or credentials. The private downloadable package includes the original data for the user's team review.
