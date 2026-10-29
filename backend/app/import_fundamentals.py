"""Load audited SEC extraction CSV. SQL constraints retain provenance and reject invalid periods."""
import csv,argparse
from pathlib import Path
from .db import sql
FIELDS=['ticker','as_of','period_start','period_end','previous_period_end','revenue','previous_revenue','net_income','filed_on','revenue_tag','income_tag','current_accn','previous_accn','income_accn','source_url']
def load(path):
    with path.open(newline='') as f:rows=list(csv.DictReader(f))
    if not rows:raise ValueError('Fundamentals file is empty')
    with sql() as c:
        for row in rows:
            if not set(FIELDS)<=row.keys():raise ValueError('Missing fundamental provenance columns')
            c.execute('INSERT INTO annual_fundamentals('+','.join(FIELDS)+') VALUES('+','.join(['%s']*len(FIELDS))+') ON CONFLICT(ticker) DO UPDATE SET '+','.join(k+'=EXCLUDED.'+k for k in FIELDS[1:]),[row[k] for k in FIELDS])
    print('Fundamental records imported:',len(rows))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path,nargs='?',default=Path('/data/fundamentals.csv'));load(p.parse_args().path)
