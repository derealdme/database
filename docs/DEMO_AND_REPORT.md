# Team demo and report preparation

## Ten-minute presentation outline

| Time | Presenter | Evidence to show |
|---|---|---|
| 0:00–1:15 | Desmond | Problem, dataset sources, architecture, stock explorer |
| 1:15–3:00 | Damien | Relational ERD, score inputs, sector percentile and missing-data treatment |
| 3:00–4:30 | Adora | SQL screener joins/filters and 2–5 company comparison |
| 4:30–6:30 | Au Myat | Portfolio buy/sell, insufficient-cash rejection, atomic transaction and constraints |
| 6:30–8:30 | Calson | Mongo document model, indexes, news aggregation and research-note CRUD |
| 8:30–10:00 | Team, assigned speaker | Verified benchmark, limitations, improvements and conclusion |

Keep background before relational demo, then NoSQL demo, then analysis, matching the brief. Every team member must present and display their name. Rehearse below ten minutes; do not assume this timing is guaranteed.

## Suggested demonstration

1. Search AAPL and show company/sector context; filter positive P/E <= 20 and dividend yield >= 1.
2. Open a score breakdown and explain why lower positive P/E receives a higher valuation percentile, while negative/missing P/E does not become zero.
3. Compare AAPL and MSFT. Explain the financial snapshot date limitation.
4. Create a portfolio dated 2020-01-02; buy one AAPL adjusted-price unit, advance to 2020-02-03, inspect the performance chart, then sell it. Submit an unaffordable trade and show unchanged cash and ledger.
5. Show PostgreSQL constraints and row locking in source, not just UI screenshots. Show the exact native CI run demonstrating concurrent-request protection.
6. Filter news by AAPL. Show monthly Mongo aggregation and explain the lexicon's limitations.
7. Create, edit and delete a research note to demonstrate document CRUD.
8. Run the benchmark on identical data, verify equal output, explain the environment and avoid blanket SQL-versus-NoSQL claims.

## Final report outline (maximum ten body pages)

1. Background and scope (0.5 page).
2. Dataset description, counts, date coverage, joins and data quality (1 page).
3. Relational design, ERD, normalisation and constraints (1.5 pages).
4. NoSQL model, schema choices, indexes and cross-store consistency (1 page).
5. Implementation of five functions, with representative queries (2 pages).
6. Tests and actual measured results (1 page).
7. Performance methodology and actual benchmark results (1 page).
8. Limitations, alternatives, contributions and reflections (1 page).
9. Conclusion (0.5 page).

Use the module's actual template from XSite; this is only an outline. Include code/setup manual separately. Never describe unrun tests, synthetic screenshots, or planned features as completed. REPORT_DRAFT.md now provides substantive content, and the private package includes the ten-slide editable PowerPoint. Final report formatting, authentic reflections and team review remain.

## Questions each member should be able to answer

- Why this data belongs in its chosen store, and what alternative was considered.
- Which primary key/index supports the feature and how to inspect its query plan.
- Which validation happens at the database versus API layer.
- What happens when data is missing, a request fails or the importer is rerun.
- What the feature does not claim (especially scores, sentiment and risk).
- Which code they reviewed or changed and which tests they personally ran.
