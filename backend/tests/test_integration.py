"""Run against imported databases: QUANT_INTEGRATION=1 python -m pytest tests/test_integration.py -v.
Creates/deletes isolated demo portfolios and notes; never truncates datasets.
"""
import os,uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import sql,mongo

pytestmark=pytest.mark.skipif(os.getenv('QUANT_INTEGRATION')!='1',reason='Requires running, imported SQL and Mongo databases')
client=TestClient(app)

@pytest.fixture
def portfolio():
    r=client.post('/api/portfolios',json={'name':'Integration test '+uuid.uuid4().hex[:8],'as_of':'2020-06-05','initial_cash':'1000'})
    assert r.status_code==201,r.text
    pid=r.json()['id']
    yield pid
    client.delete(f'/api/portfolios/{pid}')

def request(ticker='AAPL',side='BUY',quantity='1'):
    return {'ticker':ticker,'side':side,'quantity':quantity,'request_id':str(uuid.uuid4())}

def test_search_detail_compare():
    assert client.get('/api/health').status_code==200
    assert client.get('/api/meta').json()['news']>0
    r=client.get('/api/stocks?q=AAPL').json();assert r['total']>=1
    assert client.get('/api/stocks/AAPL').json()['ticker']=='AAPL'
    assert len(client.get('/api/compare?tickers=AAPL,MSFT').json())==2
    assert client.get('/api/compare?tickers=AAPL,NOTREAL').status_code==404
    rows=client.get('/api/stocks?max_pe=20&min_yield=1').json()['items']
    assert all(0<float(r['pe'])<=20 and float(r['dividend_yield'])>=1 for r in rows)

def test_buy_sell_and_idempotency(portfolio):
    url=f'/api/portfolios/{portfolio}'
    body=request();r=client.post(url+'/trades',json=body);assert r.status_code==201,r.text
    duplicate=client.post(url+'/trades',json=body);assert duplicate.json()['id']==r.json()['id']
    p=client.get(url).json();assert len(p['trades'])==1 and Decimal(p['cash'])<1000
    assert p['risk']['observations']>2
    conflict=dict(body,quantity='2');assert client.post(url+'/trades',json=conflict).status_code==409
    assert client.post(url+'/trades',json=request(side='SELL')).status_code==201
    p=client.get(url).json();assert Decimal(p['cash'])==1000 and p['holdings']==[]

def test_failed_trades_rollback(portfolio):
    url=f'/api/portfolios/{portfolio}'
    for body in [request(quantity='1000000'),request(side='SELL'),request(ticker='NOTREAL')]:
        assert client.post(url+'/trades',json=body).status_code in (409,422)
    p=client.get(url).json();assert Decimal(p['cash'])==1000 and p['trades']==[] and p['holdings']==[]

def test_portfolio_crud(portfolio):
    url=f'/api/portfolios/{portfolio}'
    assert client.patch(url,json={'name':'Renamed test'}).json()['name']=='Renamed test'
    assert client.delete(url).status_code==200
    assert client.get(url).status_code==404

def test_mongo_notes_and_aggregation():
    r=client.post('/api/notes',json={'ticker':'AAPL','text':'Integration test'});assert r.status_code==201,r.text
    nid=r.json()['id']
    try:
        assert any(n['id']==nid for n in client.get('/api/notes?stock=AAPL').json())
        assert client.put('/api/notes/'+nid,json={'ticker':'AAPL','text':'Updated test'}).status_code==200
        assert any(n['text']=='Updated test' for n in client.get('/api/notes?stock=AAPL').json())
        assert client.get('/api/news?stock=AAPL').status_code==200
        assert len(client.get('/api/sentiment?stock=AAPL').json())>0
    finally:assert client.delete('/api/notes/'+nid).status_code==200

def test_sql_constraints():
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        with sql() as c:c.execute("INSERT INTO portfolios(user_id,name,initial_cash,cash,as_of,started_on) VALUES(1,'invalid',100,-1,'2020-06-05','2020-06-05')")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with sql() as c:c.execute("INSERT INTO financials(ticker) VALUES('NOTREAL')")

def test_mongo_validator():
    from pymongo.errors import WriteError
    with pytest.raises(WriteError):mongo().news.insert_one({'ticker':'AAPL','title':'Invalid; intentionally missing date and sentiment'})

@pytest.mark.skipif(os.getenv('QUANT_CONCURRENCY')!='1',reason='Run on native PostgreSQL, not a single-session embedded engine')
def test_concurrent_buys_cannot_overspend():
    from concurrent.futures import ThreadPoolExecutor
    with sql() as c:
        price=c.execute("SELECT adjusted_close AS close FROM prices WHERE ticker='AAPL' AND date<='2020-06-05' ORDER BY date DESC LIMIT 1").fetchone()['close']
    r=client.post('/api/portfolios',json={'name':'Concurrent test','as_of':'2020-06-05','initial_cash':str((price*Decimal('1.5')).quantize(Decimal('.0001')))})
    assert r.status_code==201
    pid=r.json()['id'];url=f'/api/portfolios/{pid}'
    try:
        def buy(_):return client.post(url+'/trades',json=request()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(buy,range(2)))
        assert sorted(statuses)==[201,409]
        p=client.get(url).json();assert Decimal(p['cash'])>=0 and len(p['trades'])==1
    finally:client.delete(url)

def test_sql_scoring_matches_independent_reference():
    from app.logic import scores
    with sql() as c:
        raw=c.execute('SELECT * FROM stock_metrics ORDER BY ticker').fetchall()
        actual={r['ticker']:r for r in c.execute('SELECT * FROM stock_scores')}
    for expected in scores(raw):
        result=actual[expected['ticker']]
        assert (result['score'] is None)==(expected['score'] is None)
        if expected['score'] is not None:assert float(result['score'])==pytest.approx(expected['score'],abs=.011)
        for factor in ['pe','ps','pb','dividend_yield']:
            assert result['peer_counts'][factor]==expected['peer_counts'][factor]
            x,y=result['factor_scores'][factor],expected['factor_scores'][factor]
            if y is None:assert x is None
            else:assert float(x)==pytest.approx(y,abs=1e-9)


def test_pagination_has_stable_order():
    first=client.get('/api/stocks?sort=score&limit=1').json()
    second=client.get('/api/stocks?sort=score&limit=1&offset=1').json()
    assert first['total']==second['total'] and first['has_more']
    assert first['items'][0]['ticker']!=second['items'][0]['ticker']
    assert client.get('/api/stocks?offset=-1').status_code==422

def test_four_factor_score_uses_sourced_components():
    r=client.get('/api/stocks/AAPL?model=four_factor');assert r.status_code==200,r.text
    s=r.json();assert s['fundamental_peers']>=2
    expected=sum(float(s[k]) for k in ['valuation','dividend','growth','profitability'])/4
    assert float(s['score'])==pytest.approx(expected,abs=.011)
    assert s['filed_on']<=s['fundamentals_as_of'] and s['source_url']
    assert client.get('/api/stocks?model=unknown').status_code==422

def test_date_range_validation_and_news_pagination():
    for path in ['/api/stocks/AAPL/prices','/api/news','/api/sentiment']:
        assert client.get(path+'?start=2020-06-05&end=2019-01-01').status_code==422
    assert client.get('/api/news?stock=AAPL&start=1900-01-01&end=1900-01-02').json()==[]
    assert client.get('/api/sentiment?stock=AAPL&start=1900-01-01&end=1900-01-02').json()==[]
    a=client.get('/api/news?limit=1').json();b=client.get('/api/news?limit=1&offset=1').json()
    assert not b or a[0]['id']!=b[0]['id']

def test_advance_and_transaction_aware_performance():
    r=client.post('/api/portfolios',json={'name':'Performance test','as_of':'2020-01-02','initial_cash':'10000'})
    assert r.status_code==201,r.text
    url=f"/api/portfolios/{r.json()['id']}"
    try:
        buy=client.post(url+'/trades',json=request(quantity='2'));assert buy.status_code==201,buy.text
        assert client.post(url+'/advance',json={'as_of':'2020-02-03'}).status_code==200
        sell=client.post(url+'/trades',json=request(side='SELL'));assert sell.status_code==201,sell.text
        assert client.post(url+'/advance',json={'as_of':'2020-03-02'}).status_code==200
        history=client.get(url+'/performance').json();p=client.get(url).json()
        assert history['complete'] and len(history['items'])>20
        assert float(history['items'][-1]['value'])==pytest.approx(float(p['value']))
        # A future sale cannot change the holdings/cash on the first simulation day.
        assert float(history['items'][0]['value'])==pytest.approx(10000,abs=.001)
        assert history['total_return']==pytest.approx(float(p['value'])/10000-1)
        ledger=client.get(url+'/trades?limit=1').json();assert ledger['total']==2 and ledger['has_more']
        assert ledger['items'][0]['traded_on']=='2020-02-03'
        assert client.get(url+'/trades?limit=1&offset=1').json()['items'][0]['id']==buy.json()['id']
        assert client.post(url+'/advance',json={'as_of':'2020-01-01'}).status_code==422
        assert client.post(url+'/advance',json={'as_of':'2099-01-01'}).status_code==422
        assert client.get(url).json()['as_of']=='2020-03-02'
    finally:client.delete(url)

def test_legacy_portfolio_cannot_advance(portfolio):
    with sql() as c:c.execute("UPDATE portfolios SET price_basis='close' WHERE id=%s",(portfolio,))
    assert client.post(f'/api/portfolios/{portfolio}/advance',json={'as_of':'2020-06-06'}).status_code==409
