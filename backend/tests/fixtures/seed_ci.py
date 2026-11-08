"""Step 3. Tiny seed for CI (the Kaggle data is not in the repo).

Run from backend/ after the schema is loaded:  python tests/fixtures/seed_ci.py
Must insert: 2 sectors, 3 stocks (AAPL, MSFT, XOM), 1 financial_snapshot
each, ~30 days of stock_prices each, CALL sp_refresh_latest_prices(),
1 test user, ~20 news_articles in Mongo. Idempotent: safe to run twice.
"""
raise SystemExit("seed_ci.py not implemented yet (INSTRUCTIONS.md step 3)")
