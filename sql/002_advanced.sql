-- Advanced relational features described in the final report (section 3).
-- Apply after 001_schema.sql and an import:  psql "$DATABASE_URL" -f sql/002_advanced.sql
-- Idempotent: safe to re-run.

-- 1. Cross-sectional index. The (ticker,date) PK serves per-stock ranges; "every stock on day D" needs date first.
CREATE INDEX IF NOT EXISTS prices_date_idx ON prices(date);

-- 2. Non-standard integrity constraint: no trade may execute after its portfolio's simulation date.
CREATE OR REPLACE FUNCTION trade_not_after_as_of() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.execution_date > (SELECT as_of FROM portfolios WHERE id = NEW.portfolio_id) THEN
    RAISE EXCEPTION 'Trade date % is after the portfolio simulation date', NEW.execution_date;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trades_not_after_as_of ON trades;
CREATE TRIGGER trades_not_after_as_of BEFORE INSERT OR UPDATE ON trades
  FOR EACH ROW EXECUTE FUNCTION trade_not_after_as_of();

-- 3. Deferred constraint trigger: a stored holding must equal BUY minus SELL in the trade ledger.
-- Checked at COMMIT because the API upserts holdings before inserting the trade row.
CREATE OR REPLACE FUNCTION holding_matches_ledger() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE stored numeric; ledger numeric;
BEGIN
  SELECT quantity INTO stored FROM holdings WHERE portfolio_id = NEW.portfolio_id AND ticker = NEW.ticker;
  IF NOT FOUND THEN RETURN NULL; END IF;  -- removed later in the same transaction
  SELECT coalesce(sum(CASE side WHEN 'BUY' THEN quantity ELSE -quantity END), 0) INTO ledger
  FROM trades WHERE portfolio_id = NEW.portfolio_id AND ticker = NEW.ticker;
  IF stored <> ledger THEN
    RAISE EXCEPTION 'Holding %/% is % but the ledger gives %', NEW.portfolio_id, NEW.ticker, stored, ledger;
  END IF;
  RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS holdings_match_ledger ON holdings;
CREATE CONSTRAINT TRIGGER holdings_match_ledger AFTER INSERT OR UPDATE ON holdings
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION holding_matches_ledger();

-- 4. View: ledger audit. Stored cash versus cash recomputed from the trade ledger (should always be zero drift).
CREATE OR REPLACE VIEW v_ledger_audit AS
SELECT p.id AS portfolio_id, p.name, p.cash AS stored_cash,
       p.initial_cash
         - coalesce(sum(t.amount) FILTER (WHERE t.side = 'BUY'), 0)
         + coalesce(sum(t.amount) FILTER (WHERE t.side = 'SELL'), 0) AS ledger_cash,
       count(t.id) AS trades
FROM portfolios p LEFT JOIN trades t ON t.portfolio_id = p.id
GROUP BY p.id;

-- 5. View: open positions with average buy price and unrealised P&L at the portfolio date (two LATERAL subqueries).
CREATE OR REPLACE VIEW v_positions AS
SELECT h.portfolio_id, h.ticker, se.name AS sector, h.quantity,
       c.buy_amount / NULLIF(c.buy_qty, 0) AS avg_buy_price,
       q.close AS last_close, q.date AS price_date,
       h.quantity * q.close AS market_value,
       h.quantity * (q.close - c.buy_amount / NULLIF(c.buy_qty, 0)) AS unrealised_pnl
FROM holdings h
JOIN portfolios p ON p.id = h.portfolio_id
JOIN stocks s ON s.ticker = h.ticker
JOIN sectors se ON se.id = s.sector_id
JOIN LATERAL (SELECT sum(quantity) FILTER (WHERE side = 'BUY') AS buy_qty,
                     sum(amount)   FILTER (WHERE side = 'BUY') AS buy_amount
              FROM trades t WHERE t.portfolio_id = h.portfolio_id AND t.ticker = h.ticker) c ON true
LEFT JOIN LATERAL (SELECT close, date FROM prices pr
                   WHERE pr.ticker = h.ticker AND pr.date <= p.as_of
                   ORDER BY date DESC LIMIT 1) q ON true
WHERE h.quantity > 0;

-- 6. View: sector-relative ranks using window functions (SQL counterpart of the Python score).
-- percent_rank differs slightly from the application's midrank for ties.
CREATE OR REPLACE VIEW v_sector_ranks AS
SELECT ticker, name, sector, pe, dividend_yield, market_cap,
       CASE WHEN pe > 0 THEN
         round((100 * (1 - percent_rank() OVER (PARTITION BY sector, pe > 0 ORDER BY pe)))::numeric, 1) END AS pe_score,
       CASE WHEN dividend_yield >= 0 THEN
         round((100 * percent_rank() OVER (PARTITION BY sector, dividend_yield >= 0 ORDER BY dividend_yield))::numeric, 1) END AS yield_score,
       rank() OVER (PARTITION BY sector ORDER BY market_cap DESC NULLS LAST) AS size_rank_in_sector,
       count(*) OVER (PARTITION BY sector) AS sector_size
FROM stock_metrics;

-- 7. Materialized view: monthly closes and returns (CTE + array_agg + lag). Refresh after each import:
--    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_monthly_returns;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_returns AS
WITH m AS (
  SELECT ticker, date_trunc('month', date)::date AS month,
         (array_agg(adjusted_close ORDER BY date DESC))[1] AS month_close,
         avg(volume)::bigint AS avg_volume, count(*) AS sessions
  FROM prices GROUP BY ticker, date_trunc('month', date))
SELECT ticker, month, month_close, avg_volume, sessions,
       month_close / lag(month_close) OVER (PARTITION BY ticker ORDER BY month) - 1 AS monthly_return
FROM m;
CREATE UNIQUE INDEX IF NOT EXISTS mv_monthly_returns_pk ON mv_monthly_returns(ticker, month);

-- ---------------------------------------------------------------------------
-- Report queries (read-only). Literal parameters are examples; the API binds them.
-- ---------------------------------------------------------------------------

-- Q1 Nested (correlated) screener: cheaper than the stock's own sector average P/E,
--    and paying more than the market-wide median dividend yield.
SELECT m.ticker, m.name, m.sector, m.pe, m.dividend_yield
FROM stock_metrics m
WHERE m.pe > 0
  AND m.pe < (SELECT avg(x.pe) FROM stock_metrics x WHERE x.sector = m.sector AND x.pe > 0)
  AND m.dividend_yield > (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY dividend_yield) FROM financials)
ORDER BY m.sector, m.pe;

-- Q2 Same result as Q1 with a window aggregate instead of a correlated subquery (performance comparison E2).
WITH w AS (
  SELECT m.*, avg(pe) FILTER (WHERE pe > 0) OVER (PARTITION BY sector) AS sector_pe
  FROM stock_metrics m),
med AS (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY dividend_yield) AS y FROM financials)
SELECT w.ticker, w.name, w.sector, w.pe, w.dividend_yield
FROM w, med
WHERE w.pe > 0 AND w.pe < w.sector_pe AND w.dividend_yield > med.y
ORDER BY w.sector, w.pe;

-- Q3 Sector exposure per portfolio: aggregate, then a window over the aggregate for percentage share.
SELECT portfolio_id, sector, sum(market_value) AS value,
       round(100 * sum(market_value) / sum(sum(market_value)) OVER (PARTITION BY portfolio_id), 2) AS pct_of_invested
FROM v_positions
GROUP BY portfolio_id, sector
ORDER BY portfolio_id, value DESC;

-- Q4 Monthly sector performance with best and worst stock (aggregate with ordered array_agg).
SELECT r.month, se.name AS sector,
       round(100 * avg(r.monthly_return), 2) AS avg_return_pct,
       (array_agg(r.ticker ORDER BY r.monthly_return DESC))[1] AS best,
       (array_agg(r.ticker ORDER BY r.monthly_return ASC))[1]  AS worst,
       count(*) AS stocks
FROM mv_monthly_returns r
JOIN stocks s ON s.ticker = r.ticker JOIN sectors se ON se.id = s.sector_id
WHERE r.monthly_return IS NOT NULL
GROUP BY r.month, se.name
ORDER BY r.month DESC, avg_return_pct DESC;

-- Q5 Market beta and correlation per stock against an equal-weighted universe (statistical aggregates).
WITH r AS (
  SELECT ticker, date,
         adjusted_close / lag(adjusted_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret
  FROM prices),
mkt AS (SELECT date, avg(ret) AS mret FROM r WHERE ret IS NOT NULL GROUP BY date)
SELECT r.ticker,
       round(regr_slope(r.ret::float8, mkt.mret::float8)::numeric, 3) AS beta,
       round(corr(r.ret::float8, mkt.mret::float8)::numeric, 3) AS correlation,
       count(*) AS days
FROM r JOIN mkt USING (date)
WHERE r.ret IS NOT NULL
GROUP BY r.ticker
HAVING count(*) >= 120
ORDER BY beta DESC;

-- Q6 20/50-day moving averages and crossover signals for one stock (window frames).
WITH ma AS (
  SELECT date, adjusted_close,
         avg(adjusted_close) OVER (ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
         avg(adjusted_close) OVER (ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS ma50,
         row_number() OVER (ORDER BY date) AS n
  FROM prices WHERE ticker = 'AAPL'),
x AS (SELECT *, lag(ma20) OVER (ORDER BY date) AS p20, lag(ma50) OVER (ORDER BY date) AS p50 FROM ma)
SELECT date, round(adjusted_close, 2) AS adj_close, round(ma20, 2) AS ma20, round(ma50, 2) AS ma50,
       CASE WHEN ma20 > ma50 AND p20 <= p50 THEN 'golden cross'
            WHEN ma20 < ma50 AND p20 >= p50 THEN 'death cross' END AS signal
FROM x
WHERE n >= 50 AND ((ma20 > ma50 AND p20 <= p50) OR (ma20 < ma50 AND p20 >= p50))
ORDER BY date;

-- Q7 Ledger drift check (should return no rows).
SELECT * FROM v_ledger_audit WHERE stored_cash <> ledger_cash;
