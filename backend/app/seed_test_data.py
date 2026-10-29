"""Synthetic disposable-CI fixtures, never research evidence."""
import os
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from .db import sql,mongo
from .import_data import init

def seed():
    if os.getenv('QUANT_ALLOW_TEST_SEED')!='1':raise RuntimeError('Explicit disposable database opt-in required')
    init()
    with sql() as c:
        if c.execute('SELECT count(*) AS n FROM stocks').fetchone()['n']:raise RuntimeError('Refusing to seed nonempty database')
        for sector in ['Technology','Other']:
            c.execute('INSERT INTO sectors(name) VALUES(%s) ON CONFLICT DO NOTHING',(sector,))
        for t,pe,ps,pb,dy,sector in [('AAPL',10,2,3,1,'Technology'),('MSFT',20,4,6,2,'Technology'),('TIED',20,4,6,0,'Technology'),('MISSING',-1,None,None,None,'Other')]:
            c.execute('INSERT INTO stocks(ticker,name,sector_id) SELECT %s,%s,id FROM sectors WHERE name=%s',(t,t+' synthetic fixture',sector))
            c.execute('INSERT INTO financials(ticker,pe,ps,pb,dividend_yield) VALUES(%s,%s,%s,%s,%s)',(t,pe,ps,pb,dy))
        for t,revenue,income in [('AAPL',120,12),('MSFT',150,30)]:
            c.execute("""INSERT INTO annual_fundamentals VALUES
              (%s,'2020-06-05','2019-01-01','2019-12-31','2018-12-31',%s,100,%s,
              '2020-02-01','Revenues','NetIncomeLoss','SYNTHETIC','SYNTHETIC','SYNTHETIC','https://example.com/synthetic')""",(t,revenue,income))
        rows=[]
        for t in ['AAPL','MSFT']:
            for i in range(522):
                d=date(2019,1,1)+timedelta(days=i)
                if d>date(2020,6,5) or d.weekday()>4:continue
                price=Decimal('100')+Decimal(i)/100
                rows.append((t,d,price,price+1,price-1,price,price,1000))
        with c.cursor() as cur:cur.executemany('INSERT INTO prices VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',rows)
    mongo().news.insert_one({'_id':'synthetic-ci-news','ticker':'AAPL','title':'Synthetic CI headline',
      'date':datetime(2020,6,5,tzinfo=timezone.utc),'sentiment':1.0,'source':'SYNTHETIC CI FIXTURE'})
if __name__=='__main__':seed()
