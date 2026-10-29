"""Equivalent SQL/Mongo aggregate on an identical bounded price subset. No fabricated results."""
import argparse,json,time,statistics,platform,csv,gzip
from datetime import date
from datetime import datetime,timezone
from .db import sql,mongo

def benchmark(limit,repeats,csv_path=None):
    with sql() as c:
        data=c.execute('SELECT ticker,date,volume FROM prices ORDER BY ticker,date LIMIT %s',(limit,)).fetchall()
    if csv_path:
        opener=gzip.open if str(csv_path).endswith('.gz') else open
        with opener(csv_path,'rt',newline='') as f:
            data=[{'ticker':r['ticker'],'date':date.fromisoformat(r['date']),'volume':int(r['volume'])} for r in csv.DictReader(f)][:limit]
    if not data:raise RuntimeError('Import data first')
    # Isolated benchmark data; never modify application prices/news.
    with sql() as c:
        c.execute('CREATE TABLE IF NOT EXISTS benchmark_prices(ticker text,date date,volume bigint,PRIMARY KEY(ticker,date))')
        c.execute('TRUNCATE benchmark_prices')
        with c.cursor() as cur:cur.executemany('INSERT INTO benchmark_prices VALUES(%s,%s,%s)',[(r['ticker'],r['date'],r['volume']) for r in data])
        c.execute('ANALYZE benchmark_prices')
    coll=mongo().benchmark_prices;coll.delete_many({})
    coll.insert_many([{'ticker':r['ticker'],'date':datetime.combine(r['date'],datetime.min.time(),tzinfo=timezone.utc),'volume':r['volume']} for r in data])
    coll.create_index([('ticker',1),('date',1)],unique=True)
    pipeline=[{'$group':{'_id':'$ticker','n':{'$sum':1},'volume':{'$sum':'$volume'}}},{'$sort':{'_id':1}}]
    def sql_query(c):return c.execute('SELECT ticker,count(*) AS n,sum(volume) AS volume FROM benchmark_prices GROUP BY ticker ORDER BY ticker').fetchall()
    def mongo_query():return list(coll.aggregate(pipeline))
    with sql() as c:
        expected=sql_query(c);observed=mongo_query()
        assert [(r['ticker'],r['n'],int(r['volume'])) for r in expected]==[(r['_id'],r['n'],r['volume']) for r in observed],'Results differ'
        timings={'sql':[],'mongo':[]}
        # Alternating order reduces systematic ordering bias. Warm connections, serial client.
        for i in range(repeats):
            for name in (['sql','mongo'] if i%2==0 else ['mongo','sql']):
                start=time.perf_counter()
                sql_query(c) if name=='sql' else mongo_query()
                timings[name].append((time.perf_counter()-start)*1000)
        plan=c.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT ticker,count(*),sum(volume) FROM benchmark_prices GROUP BY ticker ORDER BY ticker').fetchone()
        sql_version=c.execute('SELECT version() AS version').fetchone()['version']
    mongo_version=mongo().command('buildInfo')['version']
    return {'postgres_version':sql_version,'mongodb_version':mongo_version,'rows':len(data),'dataset':str(csv_path) if csv_path else 'application prices','repeats':repeats,'equivalent_results':True,'environment':platform.platform(),
      'scope':'Warm sequential group-by workload; not concurrent throughput, not a general database ranking.',
      'milliseconds':{k:{'median':statistics.median(v),'min':min(v),'max':max(v),'samples':v,'serial_queries_per_second':1000/statistics.mean(v)} for k,v in timings.items()},'sql_plan':plan}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=50000);p.add_argument('--repeats',type=int,default=20);p.add_argument('--csv');a=p.parse_args()
    if a.limit<1 or a.repeats<2:p.error('limit >=1 and repeats >=2 required')
    print(json.dumps(benchmark(a.limit,a.repeats,a.csv),indent=2,default=str))
