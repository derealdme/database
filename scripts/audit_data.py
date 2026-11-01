"""Read-only ZIP audit. Run from project root: python scripts/audit_data.py --data data."""
import argparse,csv,io,json,zipfile,collections,hashlib
from pathlib import Path
from datetime import datetime,date,timezone

def canon(t):return t.strip().upper().replace('-','.')
def records(z,f):
    with z.open(f) as stream:yield from csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig',errors='replace'))

def audit(root):
    result={'scope':'Original uploads, unmodified. Tickers normalised with hyphens to periods; corporate renames are not inferred.'}
    result['archives']={}
    for name in ['financialinformation.zip','financialnews.zip','listingdayto2023.zip']:
        p=root/name
        with zipfile.ZipFile(p) as z:
            result['archives'][name]={'compressed_bytes':p.stat().st_size,'expanded_bytes':sum(i.file_size for i in z.infolist()),'files':len(z.infolist()),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}
    with zipfile.ZipFile(root/'financialinformation.zip') as z:
        companies=list(records(z,'constituents-financials_csv.csv'))
        universe={canon(r['Symbol']) for r in companies}
        result['financials']={'rows':len(companies),'sectors':len({r['Sector'] for r in companies}),'columns':list(companies[0]),'snapshot_date':None,
          'missing':{k:sum(r[k].strip() in ('','NaN','nan','N/A') for r in companies) for k in companies[0]},
          'reversed_52_week_bounds':sum(float(r['52 Week Low'])>float(r['52 Week High']) for r in companies)}
    ticks={}
    for archive in ['listingdayto2023.zip','financialnews.zip']:
        count=0;lo='9999';hi='';tick=collections.Counter();selected=0;eligible=set();mismatch=[]
        with zipfile.ZipFile(root/archive) as z:
            files=['raw_analyst_ratings.csv'] if archive=='financialnews.zip' else [f for f in z.namelist() if f.endswith('.csv')]
            empty=[]
            for f in files:
                file_tickers=set()
                for r in records(z,f):
                    t=canon(r.get('Ticker') or r.get('stock') or '');d=(r.get('Date') or r.get('date') or '')[:10]
                    if archive=='financialnews.zip':d=datetime.fromisoformat(r['date']).astimezone(timezone.utc).date().isoformat()
                    count+=1;tick[t]+=1;file_tickers.add(t);lo=min(lo,d);hi=max(hi,d)
                    if t in universe and '2019-01-01'<=d<='2020-06-05':selected+=1;eligible.add(t)
                if not file_tickers:empty.append(f)
                if archive=='listingdayto2023.zip' and file_tickers-{canon(Path(f).stem)}:mismatch.append({'file':f,'tickers':sorted(file_tickers)})
        result[archive]={'rows':count,'min_date':lo,'max_date':hi,'distinct_tickers':len(tick),'company_ticker_overlap':len(universe & tick.keys()),
          'default_window_candidates':selected,'default_window_tickers':len(eligible),'filename_ticker_mismatches':mismatch,'empty_files':empty}
        ticks[archive]=set(tick)
        print(archive,result[archive],flush=True)
    result['three_way_ticker_overlap']=len(universe & ticks['listingdayto2023.zip'] & ticks['financialnews.zip'])
    result['companies_without_prices']=sorted(universe-ticks['listingdayto2023.zip'])
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path('data'));p.add_argument('--out',type=Path,default=Path('docs/data-audit.json'));a=p.parse_args()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(audit(a.data),indent=2));print('Saved',a.out)
