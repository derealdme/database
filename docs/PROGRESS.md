# Submission progress — 29 October 2026

## Completed in this milestone
- Recovered the saved v0.1 application after workspace maintenance.
- Restored SQL-based scoring using sector-partitioned window functions and JSONB breakdowns.
- Added a parity test against the independent Python reference, including tied and missing metrics.
- Added explicitly synthetic, guarded CI fixtures, separate from real research data.
- Added GitHub Actions for PostgreSQL 17/MongoDB 8 integration, simultaneous trades, frontend build, benchmark equivalence and deployment-image build.

## Verification
The historical v0.1 evidence is in VERIFICATION.md. It must not be treated as verification of subsequent edits. Consult the GitHub Actions run for the exact commit before claiming native database checks passed. CI fixtures do not establish data quality or financial validity.

## Remaining work, in priority order
1. Establish suitable dated fundamentals for the proposed growth/profitability factors, or explicitly adopt a justified two-factor scope. Do not invent values or relabel price momentum as fundamental growth.
2. Extend the fixed-date portfolio simulator with a documented time progression/corporate-action policy if retaining the broader proposal scope.
3. Add date controls, pagination and more edge-case coverage; strengthen sentiment evaluation.
4. Verify Docker setup on a clean machine and run meaningful benchmarks on real imported data, retaining environment and query plans.
5. Complete an attribute-level ERD, final report using the XSite template, PowerPoint, and final code/data/manual package.
6. Team-only: actual contributions/reflections, peer review, and all five members' presentation recording.

## Repository policy
Development remains on project/quantscore-submission; main is the review baseline. Original large data ZIPs are not committed to this public repository. The final submission package must include the required data. No secrets or user credentials belong in source control.
