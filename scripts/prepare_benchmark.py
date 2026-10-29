"""Derive a bounded factual ticker/date/volume workload from the supplied price ZIP."""
import csv,gzip,hashlib,io,json,zipfile
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1];data=root/'data';source=data/'listingdayto2023.zip'
    with zipfile.ZipFile(data/'financialinformation.zip') as z:
        tickers={r['Symbol'].replace('-','.') for r in csv.DictReader(io.TextIOWrapper(z.open('constituents-financials_csv.csv'),encoding='utf-8-sig'))}
    rows=[]
    with zipfile.ZipFile(source) as z:
        for name in sorted(z.namelist()):
            if Path(name).stem.replace('-','.') not in tickers:continue
            with z.open(name) as f:
                for r in csv.DictReader(io.TextIOWrapper(f)):
                    if '2019-01-01'<=r['Date']<='2020-06-05':rows.append((r['Ticker'].replace('-','.'),r['Date'],int(r['Volume'])))
    rows=sorted(rows)[:50000]
    target=data/'benchmark-prices.csv.gz'
    text=io.StringIO(newline='');w=csv.writer(text);w.writerow(['ticker','date','volume']);w.writerows(rows)
    target.write_bytes(gzip.compress(text.getvalue().encode(),mtime=0))
    report={'source':'User-supplied listingdayto2023.zip','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'selection':'Financial-universe tickers; 2019-01-01 through 2020-06-05; ticker/date ascending; first 50000 rows',
      'rows':len(rows),'tickers':len({r[0] for r in rows}),'first_date':min(r[1] for r in rows),'last_date':max(r[1] for r in rows),
      'fixture_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
      'scope':'Factual ticker/date/volume tuples only; bounded biased workload, not a market-wide or concurrent benchmark.'}
    (data/'benchmark-provenance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
