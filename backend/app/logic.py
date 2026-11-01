"""Pure, testable domain rules. No unsupported fundamental factors are invented."""
import math,re,statistics
from decimal import Decimal, ROUND_HALF_UP

POSITIVE={'beat','beats','upgrade','upgrades','growth','gain','gains','surge','surges','profit','record','raises','strong','buy'}
NEGATIVE={'miss','misses','downgrade','downgrades','loss','losses','falls','fall','drops','drop','cuts','weak','sell','lawsuit'}
def sentiment(title):
    words=re.findall(r'[a-z]+',title.lower())
    positive=sum(w in POSITIVE for w in words);negative=sum(w in NEGATIVE for w in words)
    return float((positive-negative)/(positive+negative)) if positive+negative else 0.0

def ticker(value):
    value=str(value).strip().upper().replace('-','.')
    if not re.fullmatch(r'[A-Z0-9.]{1,16}',value):
        raise ValueError('Invalid ticker')
    return value

def percentile(value, peers, higher):
    if value is None or not peers:return None
    # Midrank ties; a singleton or entirely tied peer set receives 50, not 100.
    below=sum(x<value for x in peers);equal=sum(x==value for x in peers)
    rank=(below+equal/2)/len(peers)*100
    return rank if higher else 100-rank

def scores(rows):
    output=[]
    for row in rows:
        peers=[r for r in rows if r['sector']==row['sector']]
        factors={}; counts={}
        for field,higher in [('pe',False),('ps',False),('pb',False),('dividend_yield',True)]:
            valid=lambda x: x is not None and math.isfinite(float(x)) and (x>=0 if higher else x>0)
            vals=[float(r[field]) for r in peers if valid(r.get(field))]
            value=row.get(field)
            factors[field]=percentile(float(value),vals,higher) if valid(value) else None
            counts[field]=len(vals)
        valuation=[factors[f] for f in ('pe','ps','pb') if factors[f] is not None]
        # Require two valuation ratios and dividend data; no implicit reweighting.
        v=statistics.mean(valuation) if len(valuation)>=2 else None
        d=factors['dividend_yield']
        total=round(.75*v+.25*d,2) if v is not None and d is not None else None
        output.append(dict(row,score=total,valuation=v,dividend=d,factor_scores=factors,
                           peer_counts=counts,score_model='Valuation 75% + dividend 25%; fundamental growth and profitability unavailable'))
    return output

def trade_amount(qty,price):
    return (Decimal(qty)*Decimal(price)).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)

def risk(series):
    """Fixed current holdings, adjusted-price returns; not realised trading history."""
    if len(series)<3:return {'annualised_volatility':None,'max_drawdown':None,'observations':len(series)}
    returns=[b/a-1 for a,b in zip(series,series[1:]) if a>0]
    peak=series[0];dd=0
    for value in series:
        peak=max(peak,value)
        dd=min(dd,value/peak-1)
    return {'annualised_volatility':statistics.stdev(returns)*math.sqrt(252),
            'max_drawdown':dd,'observations':len(series)}
