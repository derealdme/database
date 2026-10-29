CREATE TABLE IF NOT EXISTS sectors (
 id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS stocks (
 ticker text PRIMARY KEY, name text NOT NULL,
 sector_id integer NOT NULL REFERENCES sectors(id),
 sec_url text,
 CHECK (length(ticker) BETWEEN 1 AND 16)
);
CREATE TABLE IF NOT EXISTS financials (
 ticker text PRIMARY KEY REFERENCES stocks(ticker),
 snapshot_date date,
 source text NOT NULL DEFAULT 'constituents-financials_csv.csv; snapshot date unverified',
 price numeric, pe numeric, dividend_yield numeric, eps numeric,
 low_52 numeric, high_52 numeric, market_cap numeric,
 ebitda numeric, ps numeric, pb numeric,
 CHECK (low_52 IS NULL OR high_52 IS NULL OR low_52<=high_52)
);
CREATE TABLE IF NOT EXISTS prices (
 ticker text NOT NULL REFERENCES stocks(ticker), date date NOT NULL,
 open numeric NOT NULL CHECK(open>0), high numeric NOT NULL CHECK(high>0),
 low numeric NOT NULL CHECK(low>0), close numeric NOT NULL CHECK(close>0),
 adjusted_close numeric NOT NULL CHECK(adjusted_close>0), volume bigint NOT NULL CHECK(volume>=0),
 PRIMARY KEY(ticker,date), CHECK(high>=low)
);
CREATE TABLE IF NOT EXISTS users (
 id integer PRIMARY KEY, display_name text NOT NULL
);
INSERT INTO users VALUES(1,'Team demo') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS portfolios (
 id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 user_id integer NOT NULL REFERENCES users(id), name text NOT NULL CHECK(length(name) BETWEEN 1 AND 80),
 initial_cash numeric(20,4) NOT NULL CHECK(initial_cash>0),
 cash numeric(20,4) NOT NULL CHECK(cash>=0),
 as_of date NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS holdings (
 portfolio_id integer NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
 ticker text NOT NULL REFERENCES stocks(ticker), quantity numeric(20,6) NOT NULL CHECK(quantity>=0),
 PRIMARY KEY(portfolio_id,ticker)
);
CREATE TABLE IF NOT EXISTS trades (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 portfolio_id integer NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
 ticker text NOT NULL REFERENCES stocks(ticker), side text NOT NULL CHECK(side IN ('BUY','SELL')),
 quantity numeric(20,6) NOT NULL CHECK(quantity>0), price numeric(20,8) NOT NULL CHECK(price>0),
 amount numeric(20,4) NOT NULL CHECK(amount>0), execution_date date NOT NULL,
 request_id uuid NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trades_portfolio_idx ON trades(portfolio_id,id DESC);
CREATE TABLE IF NOT EXISTS import_runs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, source text NOT NULL,
 details jsonb NOT NULL, completed_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE VIEW stock_metrics AS
SELECT s.ticker,s.name,se.name AS sector,f.pe,f.ps,f.pb,f.dividend_yield,
 f.eps,f.ebitda,f.market_cap,f.price AS snapshot_price,f.low_52,f.high_52,f.snapshot_date,
 EXISTS(SELECT 1 FROM prices p WHERE p.ticker=s.ticker) AS has_prices
FROM stocks s JOIN sectors se ON se.id=s.sector_id LEFT JOIN financials f USING(ticker);
CREATE OR REPLACE VIEW sector_averages AS
SELECT sector,count(*) AS companies,
 avg(pe) FILTER(WHERE pe>0) AS avg_pe,
 avg(ps) FILTER(WHERE ps>0) AS avg_ps,
 avg(pb) FILTER(WHERE pb>0) AS avg_pb,
 avg(dividend_yield) FILTER(WHERE dividend_yield>=0) AS avg_dividend_yield
FROM stock_metrics GROUP BY sector;

CREATE OR REPLACE VIEW stock_scores AS
WITH valid AS (
 SELECT m.ticker,m.sector,v.metric,v.value,v.higher
 FROM stock_metrics m CROSS JOIN LATERAL (VALUES
 ('pe',m.pe,false),('ps',m.ps,false),('pb',m.pb,false),('dividend_yield',m.dividend_yield,true)
 ) v(metric,value,higher)
 WHERE v.value IS NOT NULL AND v.value::text NOT IN ('NaN','Infinity','-Infinity')
 AND ((v.higher AND v.value>=0) OR (NOT v.higher AND v.value>0))
), ranked AS (
 SELECT *,rank() OVER(PARTITION BY sector,metric ORDER BY value) AS pos,
 count(*) OVER(PARTITION BY sector,metric,value) AS ties,
 count(*) OVER(PARTITION BY sector,metric) AS peers FROM valid
), factors AS (
 SELECT *,CASE WHEN higher THEN (pos-1+ties/2.0)/peers*100
 ELSE 100-(pos-1+ties/2.0)/peers*100 END AS value_score FROM ranked
), components AS (
 SELECT ticker,CASE WHEN count(*) FILTER(WHERE metric<>'dividend_yield')>=2
 THEN avg(value_score) FILTER(WHERE metric<>'dividend_yield') END AS valuation,
 max(value_score) FILTER(WHERE metric='dividend_yield') AS dividend,
 jsonb_object_agg(metric,value_score) AS scores FROM factors GROUP BY ticker
), counts AS (
 SELECT sector,jsonb_object_agg(metric,peers) AS peers
 FROM (SELECT DISTINCT sector,metric,peers FROM ranked) x GROUP BY sector
)
SELECT m.*,c.valuation,c.dividend,round(.75*c.valuation+.25*c.dividend,2) AS score,
 jsonb_build_object('pe',c.scores->'pe','ps',c.scores->'ps','pb',c.scores->'pb','dividend_yield',c.scores->'dividend_yield') AS factor_scores,
 jsonb_build_object('pe',coalesce(n.peers->'pe','0'::jsonb),'ps',coalesce(n.peers->'ps','0'::jsonb),
 'pb',coalesce(n.peers->'pb','0'::jsonb),'dividend_yield',coalesce(n.peers->'dividend_yield','0'::jsonb)) AS peer_counts,
 'Valuation 75% + dividend 25%; growth and profitability excluded from baseline'::text AS score_model
FROM stock_metrics m LEFT JOIN components c USING(ticker) LEFT JOIN counts n ON n.sector=m.sector;

-- Compatible migration: old portfolios remain fixed raw-close simulations.
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS started_on date;
UPDATE portfolios SET started_on=as_of WHERE started_on IS NULL;
ALTER TABLE portfolios ALTER COLUMN started_on SET NOT NULL;
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS price_basis text NOT NULL DEFAULT 'close'
 CHECK(price_basis IN ('close','adjusted_close'));
ALTER TABLE trades ADD COLUMN IF NOT EXISTS traded_on date;
UPDATE trades SET traded_on=execution_date WHERE traded_on IS NULL;
ALTER TABLE trades ALTER COLUMN traded_on SET NOT NULL;
CREATE INDEX IF NOT EXISTS trades_history_idx ON trades(portfolio_id,traded_on,ticker);

CREATE TABLE IF NOT EXISTS annual_fundamentals (
 ticker text PRIMARY KEY REFERENCES stocks(ticker), as_of date NOT NULL,
 period_start date NOT NULL, period_end date NOT NULL, previous_period_end date NOT NULL,
 revenue numeric NOT NULL CHECK(revenue>0), previous_revenue numeric NOT NULL CHECK(previous_revenue>0),
 net_income numeric NOT NULL, filed_on date NOT NULL,
 revenue_tag text NOT NULL, income_tag text NOT NULL,
 current_accn text NOT NULL, previous_accn text NOT NULL, income_accn text NOT NULL, source_url text NOT NULL,
 CHECK(period_start<period_end AND previous_period_end<period_end AND period_end<=filed_on AND filed_on<=as_of)
);
CREATE OR REPLACE VIEW research_scores AS
WITH metrics AS (
 SELECT f.*,s.sector_id,100*(revenue/previous_revenue-1) AS revenue_growth,
 100*net_income/revenue AS net_margin FROM annual_fundamentals f JOIN stocks s USING(ticker)
), ranked AS (
 SELECT *,count(*) OVER(PARTITION BY sector_id,as_of) AS fundamental_peers,
 (rank() OVER(PARTITION BY sector_id,as_of ORDER BY revenue_growth)-1+
 count(*) OVER(PARTITION BY sector_id,as_of,revenue_growth)/2.0)/count(*) OVER(PARTITION BY sector_id,as_of)*100 AS growth,
 (rank() OVER(PARTITION BY sector_id,as_of ORDER BY net_margin)-1+
 count(*) OVER(PARTITION BY sector_id,as_of,net_margin)/2.0)/count(*) OVER(PARTITION BY sector_id,as_of)*100 AS profitability
 FROM metrics
)
SELECT s.*,f.revenue_growth,f.net_margin,f.growth,f.profitability,
 f.fundamental_peers,f.as_of AS fundamentals_as_of,f.period_end,f.previous_period_end,f.filed_on,
 f.source_url,f.current_accn,f.previous_accn,f.income_accn,
 CASE WHEN f.fundamental_peers>=2 THEN round((s.valuation+s.dividend+f.growth+f.profitability)/4,2) END AS four_factor_score
FROM stock_scores s LEFT JOIN ranked f USING(ticker);
