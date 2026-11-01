"""Stream original ZIPs. Repeatable upserts, explicit date filter, source provenance."""
import argparse,csv,io,json,zipfile,hashlib,math
from datetime import date,datetime,timezone
from pathlib import Path
from decimal import Decimal,InvalidOperation
from pymongo import UpdateOne
from .db import sql,mongo,init_mongo
from .logic import ticker,sentiment

def rows(z,name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',errors='replace'))

def numeric(v):
    try:
        n=Decimal(v)
        return n if n.is_finite() else None
    except (InvalidOperation,TypeError):return None

def batches(items,size=2000):
    chunk=[]
    for item in items:
        chunk.append(item)
        if len(chunk)==size:yield chunk;chunk=[]
    if chunk:yield chunk

def init():
    schema=Path(__file__).resolve().parents[2]/'sql'/'001_schema.sql'
    if not schema.exists():schema=Path('/app/sql/001_schema.sql')
    with sql() as c:c.execute(schema.read_text())
    init_mongo()

def load(root,start,end):
    stats={'start':str(start),'end':str(end),'companies':0,'prices':0,'news_candidates':0,'price_rejected':0,'news_rejected':0,'high_low_swapped':0,'filename_ticker_rejected':0}
    with zipfile.ZipFile(root/'financialinformation.zip') as z,sql() as c:
        for r in rows(z,'constituents-financials_csv.csv'):
            t=ticker(r['Symbol'])
            c.execute('INSERT INTO sectors(name) VALUES(%s) ON CONFLICT DO NOTHING',(r['Sector'],))
            c.execute('''INSERT INTO stocks(ticker,name,sector_id,sec_url) SELECT %s,%s,id,%s FROM sectors WHERE name=%s
                         ON CONFLICT(ticker) DO UPDATE SET name=EXCLUDED.name,sector_id=EXCLUDED.sector_id,sec_url=EXCLUDED.sec_url''',(t,r['Name'],r['SEC Filings'],r['Sector']))
            low=numeric(r['52 Week Low']);high=numeric(r['52 Week High'])
            if low is not None and high is not None and low>high:low,high=high,low;stats['high_low_swapped']+=1
            values=[numeric(r[k]) for k in ['Price','Price/Earnings','Dividend Yield','Earnings/Share']]
            values += [low,high]+[numeric(r[k]) for k in ['Market Cap','EBITDA','Price/Sales','Price/Book']]
            c.execute('''INSERT INTO financials(ticker,price,pe,dividend_yield,eps,low_52,high_52,market_cap,ebitda,ps,pb)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(ticker) DO UPDATE SET
              price=EXCLUDED.price,pe=EXCLUDED.pe,dividend_yield=EXCLUDED.dividend_yield,eps=EXCLUDED.eps,
              low_52=EXCLUDED.low_52,high_52=EXCLUDED.high_52,market_cap=EXCLUDED.market_cap,ebitda=EXCLUDED.ebitda,ps=EXCLUDED.ps,pb=EXCLUDED.pb''',[t]+values)
            stats['companies']+=1
        universe={r['ticker'] for r in c.execute('SELECT ticker FROM stocks')}
    print('Companies imported',stats['companies'],flush=True)
    with zipfile.ZipFile(root/'listingdayto2023.zip') as z:
        for filename in z.namelist():
            if not filename.endswith('.csv'):continue
            if ticker(Path(filename).stem) not in universe:continue
            def price_rows():
                for r in rows(z,filename):
                    try:
                        d=date.fromisoformat(r['Date']);t=ticker(r['Ticker'])
                        if t!=ticker(Path(filename).stem):
                            stats['filename_ticker_rejected']+=1
                            continue
                        if not start<=d<=end or t not in universe:continue
                        vals=[numeric(r[k]) for k in ['Open','High','Low','Close','Adj Close']]
                        volume=int(r['Volume'])
                        if any(v is None or v<=0 for v in vals) or vals[1]<vals[2] or volume<0:raise ValueError()
                        yield [t,d]+vals+[volume]
                    except (ValueError,KeyError,TypeError):stats['price_rejected']+=1
            for batch in batches(price_rows()):
                with sql() as c:
                    with c.cursor() as cur:cur.executemany('''INSERT INTO prices VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(ticker,date) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
                        close=EXCLUDED.close,adjusted_close=EXCLUDED.adjusted_close,volume=EXCLUDED.volume''',batch)
                stats['prices']+=len(batch)
    print('Prices imported',stats['prices'],flush=True)
    with zipfile.ZipFile(root/'financialnews.zip') as z:
        def news_ops():
            for r in rows(z,'raw_analyst_ratings.csv'):
                try:
                    t=ticker(r['stock'])
                    if t not in universe:continue
                    d=datetime.fromisoformat(r['date']).astimezone(timezone.utc)
                    if not start<=d.date()<=end:continue
                    title=r['headline'].strip()
                    if not title:raise ValueError()
                    key=hashlib.sha256(f'{t}|{d.isoformat()}|{title}'.encode()).hexdigest()
                    doc={'ticker':t,'date':d,'title':title,'url':r.get('url',''),'publisher':r.get('publisher',''),
                         'sentiment':sentiment(title),'sentiment_method':'headline-lexicon-v1; unvalidated baseline',
                         'source':'raw_analyst_ratings.csv'}
                    stats['news_candidates']+=1
                    yield UpdateOne({'_id':key},{'$set':doc},upsert=True)
                except (ValueError,TypeError,KeyError):stats['news_rejected']+=1
        for batch in batches(news_ops()):mongo().news.bulk_write(batch,ordered=False)
    stats['news_total_after_import']=mongo().news.count_documents({})
    with sql() as c:c.execute('INSERT INTO import_runs(source,details) VALUES(%s,%s::jsonb)',('uploaded Kaggle ZIPs',json.dumps(stats)))
    print(json.dumps(stats,indent=2),flush=True)
    return stats

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=Path('/data'))
    parser.add_argument('--start',type=date.fromisoformat,default=date(2019,1,1))
    parser.add_argument('--end',type=date.fromisoformat,default=date(2020,6,5))
    parser.add_argument('--init-only',action='store_true')
    a=parser.parse_args()
    if a.start>a.end:parser.error('start must precede end')
    init()
    if not a.init_only:load(a.data,a.start,a.end)
