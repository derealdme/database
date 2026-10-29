from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pathlib import Path
from fastapi import FastAPI,HTTPException,Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,field_validator
from bson import ObjectId
from pymongo.errors import PyMongoError
import psycopg
from .db import sql,mongo
from .logic import ticker,trade_amount,risk

app=FastAPI(title='QuantScore',version='0.2.0',description='Historical stock research and adjusted-price paper simulation; local classroom demo.')

@app.exception_handler(psycopg.OperationalError)
def pg_error(request,exc):return JSONResponse(status_code=503,content={'detail':'PostgreSQL unavailable. Check database setup.'})
@app.exception_handler(psycopg.errors.UniqueViolation)
def duplicate_error(request,exc):return JSONResponse(status_code=409,content={'detail':'A unique identifier is already in use.'})

@app.exception_handler(PyMongoError)
def mongo_error(request,exc):return JSONResponse(status_code=503,content={'detail':'MongoDB unavailable. Check database setup.'})

def symbol(value):
    try:return ticker(value)
    except ValueError as e:raise HTTPException(422,str(e))

def all_stocks():
    with sql() as c:return c.execute('SELECT * FROM research_scores ORDER BY ticker').fetchall()

def apply_model(row,model):
    row=dict(row);row['baseline_score']=row['score'];row['active_model']=model
    if model=='four_factor':
        row['score']=row['four_factor_score']
        row['score_model']='Four factors, 25% each. SEC annual growth/margin plus undated valuation/dividend snapshot. Mixed-date research, not a backtest signal.'
    return row

def existing_stock(t):
    with sql() as c:
        if not c.execute('SELECT 1 FROM stocks WHERE ticker=%s',(t,)).fetchone():raise HTTPException(404,'Stock not found')

def document(d):
    d=dict(d);d['id']=str(d.pop('_id'));return d

@app.get('/api/health')
def health():
    with sql() as c:c.execute('SELECT 1')
    mongo().command('ping')
    return {'postgres':'ok','mongodb':'ok'}

@app.get('/api/meta')
def meta():
    with sql() as c:
        totals=c.execute('SELECT count(*) AS price_rows,min(date) AS first_date,max(date) AS last_date FROM prices').fetchone()
        totals['companies']=c.execute('SELECT count(*) AS n FROM stocks').fetchone()['n']
        totals['sectors']=c.execute('SELECT * FROM sector_averages ORDER BY sector').fetchall()
        totals['imports']=c.execute('SELECT source,details,completed_at FROM import_runs ORDER BY id DESC LIMIT 5').fetchall()
    totals['news']=mongo().news.count_documents({})
    totals['financial_snapshot']='Unverified source date. Financial ratios are not point-in-time trading signals.'
    return totals

@app.get('/api/stocks')
def stocks(q:str='',sector:str='',max_pe:float|None=Query(None,gt=0),min_yield:float|None=Query(None,ge=0),min_score:float=Query(0,ge=0,le=100),sort:Literal['ticker','score','pe','dividend_yield']='ticker',model:Literal['baseline','four_factor']='baseline',limit:int=Query(50,ge=1,le=600),offset:int=Query(0,ge=0)):
    score_column='four_factor_score' if model=='four_factor' else 'score'
    order={'ticker':'ticker ASC','score':score_column+' DESC NULLS LAST,ticker ASC','pe':'pe ASC NULLS LAST,ticker ASC','dividend_yield':'dividend_yield DESC NULLS LAST,ticker ASC'}[sort]
    where="""(ticker ILIKE %s OR name ILIKE %s) AND (%s='' OR sector=%s)
       AND (%s::numeric IS NULL OR (pe>0 AND pe<=%s))
       AND (%s::numeric IS NULL OR dividend_yield>=%s)
       AND (%s=0 OR """+score_column+""">=%s)"""
    args=('%'+q+'%','%'+q+'%',sector,sector,max_pe,max_pe,min_yield,min_yield,min_score,min_score)
    with sql() as c:
        total=c.execute('SELECT count(*) AS n FROM research_scores WHERE '+where,args).fetchone()['n']
        rows=c.execute('SELECT * FROM research_scores WHERE '+where+' ORDER BY '+order+' LIMIT %s OFFSET %s',args+(limit,offset)).fetchall()
    return {'total':total,'items':[apply_model(r,model) for r in rows],'offset':offset,'limit':limit,'has_more':offset+len(rows)<total}

@app.get('/api/compare')
def compare(tickers:str,model:Literal['baseline','four_factor']='baseline'):
    selected={symbol(t) for t in tickers.split(',') if t.strip()}
    if not 2<=len(selected)<=5:raise HTTPException(422,'Select 2 to 5 stocks')
    rows=[r for r in all_stocks() if r['ticker'] in selected]
    if len(rows)!=len(selected):raise HTTPException(404,'One or more stocks not found')
    return [apply_model(r,model) for r in rows]

@app.get('/api/stocks/{stock}')
def detail(stock:str,model:Literal['baseline','four_factor']='baseline'):
    t=symbol(stock);rows=[r for r in all_stocks() if r['ticker']==t]
    if not rows:raise HTTPException(404,'Stock not found')
    with sql() as c:
        rows[0]['sector_average']=c.execute('SELECT * FROM sector_averages WHERE sector=%s',(rows[0]['sector'],)).fetchone()
    return apply_model(rows[0],model)

@app.get('/api/stocks/{stock}/prices')
def prices(stock:str,start:date=date(2019,1,1),end:date=date(2020,6,5),limit:int=Query(1500,ge=1,le=5000)):
    t=symbol(stock)
    if start>end:raise HTTPException(422,'Start must precede end')
    with sql() as c:return c.execute('SELECT date,close,adjusted_close,volume FROM prices WHERE ticker=%s AND date BETWEEN %s AND %s ORDER BY date LIMIT %s',(t,start,end,limit)).fetchall()

@app.get('/api/news')
def news(stock:str='',start:date|None=None,end:date|None=None,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):
    filt={}
    if stock:filt['ticker']=symbol(stock)
    if start and end and start>end:raise HTTPException(422,'Start must precede end')
    if start or end:
        filt['date']={}
        if start:filt['date']['$gte']=datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc)
        if end:filt['date']['$lt']=datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc)
    return [document(d) for d in mongo().news.find(filt).sort([('date',-1),('_id',1)]).skip(offset).limit(limit)]

@app.get('/api/sentiment')
def sentiment_summary(stock:str='',start:date|None=None,end:date|None=None):
    stages=[];filt={}
    if stock:filt['ticker']=symbol(stock)
    if start and end and start>end:raise HTTPException(422,'Start must precede end')
    if start or end:
        filt['date']={}
        if start:filt['date']['$gte']=datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc)
        if end:filt['date']['$lt']=datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc)
    if filt:stages.append({'$match':filt})
    stages += [{'$group':{'_id':{'ticker':'$ticker','month':{'$dateToString':{'format':'%Y-%m','date':'$date'}}},'articles':{'$sum':1},'average':{'$avg':'$sentiment'}}},{'$sort':{'_id.month':-1,'_id.ticker':1}},{'$limit':100}]
    return list(mongo().news.aggregate(stages))

class Note(BaseModel):
    ticker:str
    text:str=Field(min_length=1,max_length=4000)
    @field_validator('text')
    @classmethod
    def nonempty(cls,v):
        if not v.strip():raise ValueError('Text cannot be blank')
        return v.strip()

@app.get('/api/notes')
def notes(stock:str,offset:int=Query(0,ge=0)):return [document(d) for d in mongo().notes.find({'ticker':symbol(stock)}).sort([('updated_at',-1),('_id',1)]).skip(offset).limit(100)]

@app.post('/api/notes',status_code=201)
def create_note(body:Note):
    t=symbol(body.ticker);existing_stock(t)
    d={'ticker':t,'text':body.text,'updated_at':datetime.now(timezone.utc)}
    d['_id']=mongo().notes.insert_one(d).inserted_id
    return document(d)

def note_id(v):
    if not ObjectId.is_valid(v):raise HTTPException(422,'Invalid note id')
    return ObjectId(v)

@app.put('/api/notes/{id}')
def update_note(id:str,body:Note):
    t=symbol(body.ticker);existing_stock(t)
    result=mongo().notes.update_one({'_id':note_id(id)},{'$set':{'ticker':t,'text':body.text,'updated_at':datetime.now(timezone.utc)}})
    if not result.matched_count:raise HTTPException(404,'Note not found')
    return {'updated':True}

@app.delete('/api/notes/{id}')
def delete_note(id:str):
    if not mongo().notes.delete_one({'_id':note_id(id)}).deleted_count:raise HTTPException(404,'Note not found')
    return {'deleted':True}

class Portfolio(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    initial_cash:Decimal=Field(default=Decimal('100000'),gt=0,le=1000000000,max_digits=14,decimal_places=4)
    as_of:date=date(2020,6,5)

class Rename(BaseModel):name:str=Field(min_length=1,max_length=80)
class Trade(BaseModel):
    ticker:str
    side:Literal['BUY','SELL']
    quantity:Decimal=Field(gt=0,le=1000000,max_digits=14,decimal_places=6)
    request_id:UUID

@app.get('/api/portfolios')
def portfolios():
    with sql() as c:return c.execute('SELECT * FROM portfolios WHERE user_id=1 ORDER BY id').fetchall()

@app.post('/api/portfolios',status_code=201)
def create_portfolio(body:Portfolio):
    with sql() as c:
        available=c.execute('SELECT min(date) AS lo,max(date) AS hi FROM prices').fetchone()
        if available['lo'] is None or not available['lo']<=body.as_of<=available['hi']:raise HTTPException(422,'Choose a date inside the imported price range')
        return c.execute("INSERT INTO portfolios(user_id,name,initial_cash,cash,as_of,started_on,price_basis) VALUES(1,%s,%s,%s,%s,%s,'adjusted_close') RETURNING *",(body.name,body.initial_cash,body.initial_cash,body.as_of,body.as_of)).fetchone()

@app.patch('/api/portfolios/{pid}')
def rename_portfolio(pid:int,body:Rename):
    with sql() as c:
        r=c.execute('UPDATE portfolios SET name=%s WHERE id=%s AND user_id=1 RETURNING *',(body.name,pid)).fetchone()
        if not r:raise HTTPException(404,'Portfolio not found')
        return r

@app.delete('/api/portfolios/{pid}')
def delete_portfolio(pid:int):
    with sql() as c:
        if not c.execute('DELETE FROM portfolios WHERE id=%s AND user_id=1 RETURNING id',(pid,)).fetchone():raise HTTPException(404,'Portfolio not found')
    return {'deleted':True}

@app.post('/api/portfolios/{pid}/trades',status_code=201)
def trade(pid:int,body:Trade):
    t=symbol(body.ticker)
    with sql() as c:
        # All trades for a portfolio lock the same row, serialising cash/holdings checks.
        p=c.execute('SELECT * FROM portfolios WHERE id=%s AND user_id=1 FOR UPDATE',(pid,)).fetchone()
        if not p:raise HTTPException(404,'Portfolio not found')
        existing=c.execute('SELECT * FROM trades WHERE request_id=%s',(body.request_id,)).fetchone()
        if existing:
            if (existing['portfolio_id'],existing['ticker'],existing['side'],existing['quantity'])!=(pid,t,body.side,body.quantity):raise HTTPException(409,'Request ID already used for another trade')
            return existing
        quote_column='adjusted_close' if p['price_basis']=='adjusted_close' else 'close'
        quote=c.execute('SELECT '+quote_column+' AS close,date FROM prices WHERE ticker=%s AND date<=%s ORDER BY date DESC LIMIT 1',(t,p['as_of'])).fetchone()
        if not quote or (p['as_of']-quote['date']).days>7:raise HTTPException(422,'No recent price available at portfolio date')
        amount=trade_amount(body.quantity,quote['close'])
        if amount<=0:raise HTTPException(422,'Trade value is below precision limit')
        h=c.execute('SELECT quantity FROM holdings WHERE portfolio_id=%s AND ticker=%s',(pid,t)).fetchone()
        held=h['quantity'] if h else Decimal(0)
        if body.side=='BUY' and amount>p['cash']:raise HTTPException(409,'Insufficient cash')
        if body.side=='SELL' and body.quantity>held:raise HTTPException(409,'Insufficient holdings')
        delta=body.quantity if body.side=='BUY' else -body.quantity
        c.execute('UPDATE portfolios SET cash=cash+%s WHERE id=%s',(-amount if body.side=='BUY' else amount,pid))
        c.execute('INSERT INTO holdings VALUES(%s,%s,%s) ON CONFLICT(portfolio_id,ticker) DO UPDATE SET quantity=EXCLUDED.quantity',(pid,t,held+delta))
        return c.execute('INSERT INTO trades(portfolio_id,ticker,side,quantity,price,amount,execution_date,request_id,traded_on) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(pid,t,body.side,body.quantity,quote['close'],amount,quote['date'],body.request_id,p['as_of'])).fetchone()

@app.get('/api/portfolios/{pid}')
def portfolio_detail(pid:int):
    with sql() as c:
        p=c.execute('SELECT * FROM portfolios WHERE id=%s AND user_id=1',(pid,)).fetchone()
        if not p:raise HTTPException(404,'Portfolio not found')
        quote_column='adjusted_close' if p['price_basis']=='adjusted_close' else 'close'
        holdings=c.execute('''SELECT h.ticker,h.quantity,q.close,q.date FROM holdings h
          LEFT JOIN LATERAL (SELECT '''+quote_column+''' AS close,date FROM prices WHERE ticker=h.ticker AND date<=%s ORDER BY date DESC LIMIT 1) q ON true
          WHERE h.portfolio_id=%s AND h.quantity>0''',(p['as_of'],pid)).fetchall()
        p['holdings']=holdings
        p['trades']=c.execute('SELECT * FROM trades WHERE portfolio_id=%s ORDER BY id DESC LIMIT 100',(pid,)).fetchall()
        p['value']=p['cash']+sum(h['quantity']*h['close'] for h in holdings)
        p['risk_label']='Trailing risk of fixed current holdings; separate from the transaction-aware performance history.'
        if holdings:
            # Require common trading dates; anchor adjusted series to current raw close.
            series=c.execute('''WITH series AS (
               SELECT pr.date,sum(pr.adjusted_close / anchor.adjusted_close * current.close * h.quantity) AS value,count(*) AS n
               FROM holdings h JOIN prices pr ON pr.ticker=h.ticker
               JOIN LATERAL (SELECT adjusted_close,close FROM prices WHERE ticker=h.ticker AND date<=%s ORDER BY date DESC LIMIT 1) anchor ON true
               JOIN LATERAL (SELECT '''+quote_column+''' AS close FROM prices WHERE ticker=h.ticker AND date<=%s ORDER BY date DESC LIMIT 1) current ON true
               WHERE h.portfolio_id=%s AND h.quantity>0 AND pr.date<=%s
               GROUP BY pr.date)
               SELECT date,value FROM series WHERE n=%s ORDER BY date DESC LIMIT 252''',(p['as_of'],p['as_of'],pid,p['as_of'],len(holdings))).fetchall()
            p['risk']=risk([float(r['value']+p['cash']) for r in reversed(series)])
        else:p['risk']=risk([])
        return p

class Advance(BaseModel):
    as_of:date

@app.post('/api/portfolios/{pid}/advance')
def advance_portfolio(pid:int,body:Advance):
    with sql() as c:
        p=c.execute('SELECT * FROM portfolios WHERE id=%s AND user_id=1 FOR UPDATE',(pid,)).fetchone()
        if not p:raise HTTPException(404,'Portfolio not found')
        if p['price_basis']!='adjusted_close':raise HTTPException(409,'Legacy raw-close portfolios remain fixed-date. Create an adjusted-price portfolio to advance.')
        if body.as_of<=p['as_of']:raise HTTPException(422,'Simulation date must move forward')
        maximum=c.execute('SELECT max(date) AS d FROM prices').fetchone()['d']
        if body.as_of>maximum:raise HTTPException(422,'Date exceeds imported prices')
        missing=c.execute("""SELECT h.ticker FROM holdings h LEFT JOIN LATERAL
          (SELECT date FROM prices WHERE ticker=h.ticker AND date<=%s ORDER BY date DESC LIMIT 1) q ON true
          WHERE h.portfolio_id=%s AND h.quantity>0 AND (q.date IS NULL OR %s-q.date>7)""",(body.as_of,pid,body.as_of)).fetchall()
        if missing:raise HTTPException(422,'Missing recent prices for: '+', '.join(r['ticker'] for r in missing))
        c.execute('UPDATE portfolios SET as_of=%s WHERE id=%s',(body.as_of,pid))
    return {'as_of':body.as_of,'price_basis':'adjusted_close'}

@app.get('/api/portfolios/{pid}/performance')
def performance(pid:int):
    with sql() as c:
        p=c.execute('SELECT * FROM portfolios WHERE id=%s AND user_id=1',(pid,)).fetchone()
        if not p:raise HTTPException(404,'Portfolio not found')
        basis='adjusted_close' if p['price_basis']=='adjusted_close' else 'close'
        # Daily end-of-day holdings and cash are reconstructed from the immutable trade ledger.
        rows=c.execute("""WITH dates AS (
          SELECT DISTINCT date AS d FROM prices WHERE date BETWEEN %s AND %s
          UNION SELECT %s::date UNION SELECT %s::date
        ), ledger AS (
          SELECT d.d,t.ticker,sum(CASE WHEN t.side='BUY' THEN t.quantity ELSE -t.quantity END) AS quantity
          FROM dates d JOIN trades t ON t.portfolio_id=%s AND t.traded_on<=d.d
          GROUP BY d.d,t.ticker
        ), valuations AS (
          SELECT l.d,sum(l.quantity*q.price) AS holdings,
            bool_or(q.date IS NULL OR l.d-q.date>7) AS incomplete
          FROM ledger l LEFT JOIN LATERAL (SELECT """+basis+""" AS price,date FROM prices
             WHERE ticker=l.ticker AND date<=l.d ORDER BY date DESC LIMIT 1) q ON true
          WHERE l.quantity>0 GROUP BY l.d
        ) SELECT dates.d AS date,
          CASE WHEN coalesce(v.incomplete,false) THEN NULL ELSE
          %s+coalesce((SELECT sum(CASE WHEN side='BUY' THEN -amount ELSE amount END)
            FROM trades WHERE portfolio_id=%s AND traded_on<=dates.d),0)+coalesce(v.holdings,0) END AS value
        FROM dates LEFT JOIN valuations v ON v.d=dates.d ORDER BY dates.d""",
        (p['started_on'],p['as_of'],p['started_on'],p['as_of'],pid,p['initial_cash'],pid)).fetchall()
    complete=all(r['value'] is not None for r in rows)
    return {'items':rows,'complete':complete,'initial_cash':p['initial_cash'],
      'total_return':float(rows[-1]['value']/p['initial_cash']-1) if complete and rows else None,
      'method':'End-of-day transaction-aware NAV. Adjusted-price units assume reinvested distributions; no separate dividends, fees or real share quantities.'}

@app.get('/api/portfolios/{pid}/trades')
def trade_history(pid:int,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
    with sql() as c:
        if not c.execute('SELECT 1 FROM portfolios WHERE id=%s AND user_id=1',(pid,)).fetchone():raise HTTPException(404,'Portfolio not found')
        total=c.execute('SELECT count(*) AS n FROM trades WHERE portfolio_id=%s',(pid,)).fetchone()['n']
        rows=c.execute('SELECT * FROM trades WHERE portfolio_id=%s ORDER BY id DESC LIMIT %s OFFSET %s',(pid,limit,offset)).fetchall()
    return {'items':rows,'total':total,'offset':offset,'has_more':offset+len(rows)<total}

static=Path(__file__).parents[1]/'static'
if static.exists():app.mount('/',StaticFiles(directory=static,html=True),name='frontend')
