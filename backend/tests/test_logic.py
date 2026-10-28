from decimal import Decimal
import pytest
from app.logic import scores,percentile,trade_amount,risk,sentiment,ticker
from app.import_data import numeric,batches

def record(t,pe,ps,pb,div,sector='Tech'):
    return {'ticker':t,'sector':sector,'pe':pe,'ps':ps,'pb':pb,'dividend_yield':div}

def test_score_direction_and_sector_isolation():
    rows=[record('A',10,1,1,4),record('B',20,2,2,0),record('C',1,1,1,99,'Other')]
    a,b,c=scores(rows)
    assert a['score']==75 and b['score']==25 and c['score']==50

def test_missing_not_zero_and_negative_pe_excluded():
    a=scores([record('A',-2,None,1,None)])[0]
    assert a['score'] is None and a['factor_scores']['pe'] is None
    assert a['dividend'] is None
    assert scores([record('B',2,2,None,0)])[0]['score']==50

def test_ties():assert percentile(3,[3,3,3],True)==50

def test_no_nan_scores():
    assert scores([record('A',float('nan'),float('inf'),None,0)])[0]['score'] is None

def test_money_rounding():
    assert trade_amount(Decimal('0.123456'),Decimal('123.456789'))==Decimal('15.2415')

def test_risk_drawdown():
    result=risk([100,120,90,100]);assert result['max_drawdown']==-.25
    assert result['annualised_volatility']>0
    assert risk([100,100,100])['annualised_volatility']==0
    assert risk([100])['max_drawdown'] is None

def test_ticker():
    assert ticker(' brk-b ')=='BRK.B'
    with pytest.raises(ValueError):ticker("'; DROP TABLE stocks;")

def test_sentiment_baseline():
    assert sentiment('Company beats estimates, raises outlook')==1
    assert sentiment('Company misses estimates, cuts outlook')==-1
    assert sentiment('Company announces results')==0

def test_numeric_and_batches():
    assert numeric('NaN') is None and numeric('') is None
    assert numeric('0')==0
    assert list(batches(range(5),2))==[[0,1],[2,3],[4]]
