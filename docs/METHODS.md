# Methods and data limitations

## Score v0.1

For each sector, valid positive P/E, P/S and P/B values are ranked with midrank percentile: `(number below + 0.5 * number equal) / count * 100`. Lower multiples receive `100 - percentile`; dividend yield uses percentile directly, including valid zero yields. A singleton/all-tied peer set scores 50. Negative P/E, missing values and nonfinite values are excluded, not coerced to zero.

Valuation is the mean of available ratio scores, requiring at least two of three ratios. The overall score is 75% valuation plus 25% dividend, requiring both components. Missing components give N/A rather than silent reweighting. Peer counts and underlying metrics are displayed. The stock_scores SQL view computes ranks, tie counts and peer counts with window functions over the entire imported company universe before filtering so filtering does not alter peer rankings.

This is an educational heuristic, not a validated investment model. High yield can reflect distress; low ratios can reflect risk. Sector means are sensitive to outliers. No claim is made that score ordering predicts returns. The optional four-factor model adds SEC annual facts as described below.

## Temporal integrity

Source company-snapshot date is unknown. Do not infer it solely from filenames, constituent names or prices. The UI states this limitation. Historical price/news date overlap does not make the financial snapshot point-in-time correct. There is no score backtest, performance forecast or financial recommendation.

Ticker normalisation replaces hyphens with periods. Renames, mergers and corporate identities are not inferred. Different historical constituent lists create survivorship/coverage bias. 503 price files contain only 501 distinct row-level tickers: `BF.B.csv` and `BRK.B.csv` contain headers only. Empty files contribute no prices. The importer also checks row tickers against filenames and rejects mismatches if present. The financial universe has 505 records, 391 matching distinct price tickers and 424 matching news tickers across the source history. Check the JSON audit for the exact three-way overlap.

All 505 financial records have source low > source high. Import swaps those bounds with an explicit counter and retains the raw files. This repairs ordering but is not independent verification of the values or dates. There are two missing P/E and eight missing P/B values.

## News sentiment

Tokenise headline words to lowercase. Count fixed positive/negative keywords. Score `(positive - negative)/(positive + negative)`, or zero when neither appears. Repeated keyword occurrences count. Store `headline-lexicon-v1; unvalidated baseline` on each document.

This provides a reproducible pipeline and aggregation demonstration. It does not establish NLP accuracy. Manually label a sample and evaluate agreement before claiming quality. Words such as 'buy' in quoted analyst remarks, negation and company names can mislead this approach. A future trained financial classifier requires its own evaluation and runtime budget.

## Portfolio risk

New portfolios use adjusted-close units and a simulation date that can only advance. Execution uses the latest adjusted close on/before that date, no more than seven days old. Both advance and trade operations lock the portfolio row. Adjusted prices incorporate provider adjustments; units are not literal historical shares. Reinvested distributions are implicit, with no additional dividend cash, fees or slippage. Legacy raw-close portfolios retain fixed dates. Mark-to-market uses the same basis as execution.

For each current holding, normalise its historical adjusted-close series by adjusted close at the simulation date and multiply by current simulation-basis price and quantity. Sum across holdings on common dates, add fixed cash, and use up to 252 latest common observations. Daily simple returns yield sample standard deviation multiplied by sqrt(252). Maximum drawdown is the minimum value/running peak minus one. Fewer than three observations returns unavailable risk. Historical holdings composition is held constant: this is hypothetical exposure risk, not realised trading performance.

## Four-factor SEC sample

`scripts/fetch_fundamentals.py` extracts annual USD revenue and matching net income from SEC companyfacts, restricted to 10-K facts filed on or before 2020-06-05. Annual durations must be 330–400 days; prior-year ends must be 300–430 days apart; latest period must be at most 550 days old. Revenue must be positive. Latest eligible filings can restate earlier periods, but no filing after the cutoff is accepted. Matching annual start/end is required for income and revenue. Revenue tag, income tag, accession identifiers and source URL are retained. Revenue growth is `(revenue / previous_revenue - 1) * 100`; profitability is `net_income / revenue * 100`.

Selection is purposeful, up to five eligible companies per source sector, not a representative market sample. Current SEC ticker mapping may omit renamed/delisted companies. The provenance JSON reports accepted and skipped records. Higher growth/margin gets higher sector/as-of midrank percentile. At least two sampled sector peers and all four components are required for the equal-weight combined score. Small peer groups make ranks coarse. Baseline valuation peers still use the full original sector universe, whereas growth/profitability peers use the smaller SEC sample. This asymmetry and the undated original ratios prohibit a point-in-time trading claim.

## Transaction-aware performance

For each imported trading date plus simulation endpoints, aggregate signed trade quantities whose `traded_on` is no later than that date. Cash equals initial cash minus buys plus sells. Value equals cash plus positive holdings valued at the most recent price on/before that date using the portfolio's price basis. A held asset with a missing or more-than-seven-day-old quote makes that day's value unavailable, and incomplete histories suppress total return. Total return is final value / initial cash - 1; deposits/withdrawals are unsupported. Multiple same-day trades appear in end-of-day balances. `execution_date` records the quote date; `traded_on` records the simulation date, preventing a weekend trade from being backdated into Friday's history.

This NAV history differs from the trailing risk panel, which holds current composition constant. Changing source adjusted prices after import can change historical NAV; archive source checksums and do not mix provider revisions when interpreting results.
