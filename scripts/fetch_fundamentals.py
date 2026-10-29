"""Download a bounded SEC research sample; no authentication, < 2 requests/second.
Raw cache is excluded from git. Every accepted measurement retains filing provenance.
"""
import csv,io,json,time,zipfile,urllib.request,argparse
from datetime import date
from pathlib import Path

AGENT='QuantScore academic database research https://github.com/derealdme/database'
TAGS=['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','RevenueFromContractWithCustomerIncludingAssessedTax']
def fetch(url,path):
    if path.exists():return json.loads(path.read_text())
    time.sleep(.6)
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'application/json'}),timeout=40) as r:raw=r.read()
    result=json.loads(raw);path.write_bytes(raw);return result

def annual(facts,tag,as_of):
    result={}
    for r in facts.get(tag,{}).get('units',{}).get('USD',[]):
        if not all(k in r for k in ['start','end','filed','val','accn']):continue
        duration=(date.fromisoformat(r['end'])-date.fromisoformat(r['start'])).days
        if r.get('form')!='10-K' or not 330<=duration<=400 or r['filed']>as_of or r['end']>as_of:continue
        key=(r['start'],r['end'])
        if key not in result or r['filed']>result[key]['filed']:result[key]=r
    return result

def extract(payload,ticker,as_of):
    facts=payload.get('facts',{}).get('us-gaap',{})
    options=[]
    for tag in TAGS:
        records=annual(facts,tag,as_of)
        for period,current in records.items():
            if current['val']<=0:continue
            if (date.fromisoformat(as_of)-date.fromisoformat(current['end'])).days>550:continue
            prior=[r for r in records.values() if 300<=(date.fromisoformat(current['end'])-date.fromisoformat(r['end'])).days<=430 and r['val']>0]
            income=None
            for income_tag in ['NetIncomeLoss','ProfitLoss']:
                income=annual(facts,income_tag,as_of).get(period)
                if income:break
            if not prior or not income:continue
            previous=max(prior,key=lambda r:r['end'])
            options.append({'ticker':ticker,'as_of':as_of,'period_start':current['start'],'period_end':current['end'],
              'previous_period_end':previous['end'],'revenue':current['val'],'previous_revenue':previous['val'],
              'net_income':income['val'],'filed_on':max(current['filed'],previous['filed'],income['filed']),
              'revenue_tag':tag,'income_tag':income_tag,'current_accn':current['accn'],'previous_accn':previous['accn'],
              'income_accn':income['accn'],'source_url':f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(payload['cik']):010d}.json"})
    return max(options,key=lambda r:r['period_end']) if options else None

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path('data'));p.add_argument('--as-of',default='2020-06-05');p.add_argument('--per-sector',type=int,default=5);a=p.parse_args()
    date.fromisoformat(a.as_of);cache=a.data/'sec-cache';cache.mkdir(parents=True,exist_ok=True)
    mapping=fetch('https://www.sec.gov/files/company_tickers.json',cache/'tickers.json')
    mapping={r['ticker'].replace('-','.'):r['cik_str'] for r in mapping.values()}
    with zipfile.ZipFile(a.data/'financialinformation.zip') as z:
        companies=list(csv.DictReader(io.TextIOWrapper(z.open('constituents-financials_csv.csv'),encoding='utf-8-sig')))
    counts={};accepted=[];skipped=[]
    # Choose familiar examples first, then fill each sector quota in stable ticker order.
    priority={'AAPL','MSFT','INTC','CSCO','ORCL','JNJ','PFE','MRK','ABT','AMGN','JPM','BAC','WFC','GS','MS','KO','PEP','PG','COST','WMT','XOM','CVX','COP','SLB','HAL','AMZN','HD','LOW','MCD','NKE','NEE','DUK','SO','D','AEP','MMM','CAT','HON','GE','UPS','T','VZ','AMT','PLD','SPG','O','PSA','APD','SHW','ECL','FCX','NUE'}
    for c in sorted(companies,key=lambda c:(c['Symbol'] not in priority,c['Symbol'])):
        sector=c['Sector'];t=c['Symbol'].replace('-','.')
        if counts.get(sector,0)>=a.per_sector or t not in mapping:continue
        try:
            cik=mapping[t];url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'
            row=extract(fetch(url,cache/f'{cik}.json'),t,a.as_of)
            if row:
                row['sector']=sector;accepted.append(row);counts[sector]=counts.get(sector,0)+1
                print(t,sector,row['period_end'],flush=True)
            else:skipped.append({'ticker':t,'reason':'No matching annual USD revenue pair and net income available by cutoff'})
        except Exception as e:
            skipped.append({'ticker':t,'reason':str(e)});print('Skipped',t,str(e),flush=True)
    if accepted:
        with (a.data/'fundamentals.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(accepted[0]));w.writeheader();w.writerows(accepted)
    report={'source':'SEC companyfacts API','as_of':a.as_of,'accepted':len(accepted),'sectors':counts,'skipped':skipped,
     'selection':'Purposeful bounded sample, not representative coverage; financial snapshot valuation/dividends remain undated.'}
    (a.data/'fundamentals-provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
