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
