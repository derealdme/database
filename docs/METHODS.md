# Methods and data limitations

## Score v0.1

For each sector, valid positive P/E, P/S and P/B values are ranked with midrank percentile: `(number below + 0.5 * number equal) / count * 100`. Lower multiples receive `100 - percentile`; dividend yield uses percentile directly, including valid zero yields. A singleton/all-tied peer set scores 50. Negative P/E, missing values and nonfinite values are excluded, not coerced to zero.

Valuation is the mean of available ratio scores, requiring at least two of three ratios. The overall score is 75% valuation plus 25% dividend, requiring both components. Missing components give N/A rather than silent reweighting. Peer counts and underlying metrics are displayed. The stock_scores SQL view computes ranks, tie counts and peer counts with window functions over the entire imported company universe before filtering so filtering does not alter peer rankings.

This is an educational heuristic, not a validated investment model. High yield can reflect distress; low ratios can reflect risk. Sector means are sensitive to outliers. No claim is made that score ordering predicts returns. The original proposal's fundamental growth/profitability factors require additional data. This revision must be approved as the team's chosen scope before submission.

## Temporal integrity

Source company-snapshot date is unknown. Do not infer it solely from filenames, constituent names or prices. The UI states this limitation. Historical price/news date overlap does not make the financial snapshot point-in-time correct. There is no score backtest, performance forecast or financial recommendation.

Ticker normalisation replaces hyphens with periods. Renames, mergers and corporate identities are not inferred. Different historical constituent lists create survivorship/coverage bias. 503 price files contain only 501 distinct row-level tickers: `BF.B.csv` and `BRK.B.csv` contain headers only. Empty files contribute no prices. The importer also checks row tickers against filenames and rejects mismatches if present. The financial universe has 505 records, 391 matching distinct price tickers and 424 matching news tickers across the source history. Check the JSON audit for the exact three-way overlap.

All 505 financial records have source low > source high. Import swaps those bounds with an explicit counter and retains the raw files. This repairs ordering but is not independent verification of the values or dates. There are two missing P/E and eight missing P/B values.

## News sentiment

Tokenise headline words to lowercase. Count fixed positive/negative keywords. Score `(positive - negative)/(positive + negative)`, or zero when neither appears. Repeated keyword occurrences count. Store `headline-lexicon-v1; unvalidated baseline` on each document.

This provides a reproducible pipeline and aggregation demonstration. It does not establish NLP accuracy. Manually label a sample and evaluate agreement before claiming quality. Words such as 'buy' in quoted analyst remarks, negation and company names can mislead this approach. A future trained financial classifier requires its own evaluation and runtime budget.

## Portfolio risk

The portfolio date is fixed on creation. Execution uses latest raw close on/before it, no more than seven days old. This supports a transactional allocation simulator without claiming to handle subsequent corporate actions. Mark-to-market is cash plus quantity times close.

For each current holding, normalise its historical adjusted-close series by adjusted close at the simulation date and multiply by current raw close and quantity. Sum across holdings on common dates, add fixed cash, and use up to 252 latest common observations. Daily simple returns yield sample standard deviation multiplied by sqrt(252). Maximum drawdown is the minimum value/running peak minus one. Fewer than three observations returns unavailable risk. Historical holdings composition is held constant: this is hypothetical exposure risk, not realised trading performance.
