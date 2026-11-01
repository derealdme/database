"""Clean the three extracted Kaggle datasets to a common 2018-01-01..2020-12-31 window.

Run from project root:  python scripts/clean_data.py --data data --out data/cleaned

Source CSVs are only read, never modified. Writes exactly three files:
  cleaned_companies_info.csv  S&P 500 financial snapshot (undated: no date filter possible)
  cleaned_stock_prices.csv    all per-ticker price files combined, filtered to the window
  cleaned_financial_news.csv  raw_analyst_ratings.csv + raw_partner_headlines.csv combined, filtered,
                              de-duplicated across both files, with a `source` column
analyst_ratings_processed.csv is not included: ~99% of its rows repeat raw_analyst_ratings.csv
with truncated timestamps and without url/publisher. Row counts per drop reason are printed.
"""
import argparse
from pathlib import Path
import pandas as pd

START=pd.Timestamp('2018-01-01',tz='UTC')
END=pd.Timestamp('2021-01-01',tz='UTC')  # exclusive upper bound, i.e. through 2020-12-31

COMPANIES='S&P 500 Companies with Financial Information/constituents-financials_csv.csv'
PRICES='S&P 500 Stock Data From Listing Day to 2023'
NEWS_DIR='daily financial news for 6000+ stocks'
NEWS=['raw_analyst_ratings.csv','raw_partner_headlines.csv']
OUTPUTS={'companies':'cleaned_companies_info.csv','prices':'cleaned_stock_prices.csv','news':'cleaned_financial_news.csv'}

def canon(s):
    # Same rule as the importer: trim, upper-case, hyphen -> period (BRK-B -> BRK.B).
    return s.astype('string').str.strip().str.upper().str.replace('-','.',regex=False)

def blank(s):
    return s.isna() | (s.astype('string').str.strip()=='')

def clean_companies(src,out):
    df=pd.read_csv(src)
    report={'rows_in':len(df)}
    df['Symbol']=canon(df['Symbol'])
    missing=blank(df['Symbol']) | blank(df['Name']) | blank(df['Sector'])
    df=df[~missing]
    report['dropped_missing_symbol_name_sector']=int(missing.sum())
    before=len(df);df=df.drop_duplicates('Symbol');report['dropped_duplicate_symbol']=before-len(df)
    # Every source row has 52 Week Low > 52 Week High; repair ordering, keep the values.
    swap=df['52 Week Low']>df['52 Week High']
    df.loc[swap,['52 Week Low','52 Week High']]=df.loc[swap,['52 Week High','52 Week Low']].values
    report['swapped_52_week_bounds']=int(swap.sum())
    report['missing_ratio_values_kept_as_null']={c:int(df[c].isna().sum()) for c in ['Price/Earnings','Price/Book','Price/Sales','Dividend Yield']}
    report['note']='Undated snapshot: date window not applicable. Missing ratios stay null; they are not primary data.'
    df.to_csv(out,index=False)
    report['rows_out']=len(df)
    return report

def clean_prices(folder,out):
    report={'files':0,'empty_files':[],'rows_in':0,'dropped_missing_ticker_or_date':0,'dropped_outside_window':0,
            'dropped_missing_ohlcv':0,'dropped_invalid_values':0,'dropped_ticker_filename_mismatch':0,'dropped_duplicates':0}
    frames=[]
    for f in sorted(folder.glob('*.csv')):
        report['files']+=1
        df=pd.read_csv(f)
        if df.empty:report['empty_files'].append(f.name);continue
        report['rows_in']+=len(df)
        df['Ticker']=canon(df['Ticker'])
        df['Date']=pd.to_datetime(df['Date'],errors='coerce',utc=True)
        bad=blank(df['Ticker']) | df['Date'].isna()
        report['dropped_missing_ticker_or_date']+=int(bad.sum());df=df[~bad]
        mismatch=df['Ticker']!=canon(pd.Series([f.stem]))[0]
        report['dropped_ticker_filename_mismatch']+=int(mismatch.sum());df=df[~mismatch]
        outside=(df['Date']<START)|(df['Date']>=END)
        report['dropped_outside_window']+=int(outside.sum());df=df[~outside]
        cols=['Open','High','Low','Close','Adj Close','Volume']
        na=df[cols].isna().any(axis=1)
        report['dropped_missing_ohlcv']+=int(na.sum());df=df[~na]
        # Same validity rules as the prices table CHECK constraints.
        invalid=(df[['Open','High','Low','Close','Adj Close']]<=0).any(axis=1)|(df['High']<df['Low'])|(df['Volume']<0)
        report['dropped_invalid_values']+=int(invalid.sum());df=df[~invalid]
        frames.append(df)
    df=pd.concat(frames,ignore_index=True)
    before=len(df);df=df.drop_duplicates(['Ticker','Date']);report['dropped_duplicates']=before-len(df)
    df['Date']=df['Date'].dt.strftime('%Y-%m-%d')
    df['Volume']=df['Volume'].astype('int64')
    df.sort_values(['Ticker','Date']).to_csv(out,index=False)
    report.update(rows_out=len(df),tickers_out=int(df['Ticker'].nunique()),min_date=df['Date'].min(),max_date=df['Date'].max())
    return report

def clean_news(sources,out):
    """Stream each news file in chunks into one CSV; duplicates are detected across files."""
    report={};seen=set();first=True;total=0;tickers=set();lo=hi=None
    for src in sources:
        r={'rows_in':0,'dropped_missing_ticker_headline_or_date':0,'dropped_outside_window':0,'dropped_duplicates':0,'rows_out':0}
        for df in pd.read_csv(src,chunksize=250_000):
            r['rows_in']+=len(df)
            df=df[['headline','url','publisher','date','stock']].copy()
            df['stock']=canon(df['stock'])
            df['headline']=df['headline'].astype('string').str.strip()
            # Analyst timestamps carry -04:00/-05:00 offsets; partner rows are naive (treated as UTC).
            df['date']=pd.to_datetime(df['date'],errors='coerce',utc=True,format='ISO8601')
            bad=blank(df['stock'])|blank(df['headline'])|df['date'].isna()
            r['dropped_missing_ticker_headline_or_date']+=int(bad.sum());df=df[~bad]
            outside=(df['date']<START)|(df['date']>=END)
            r['dropped_outside_window']+=int(outside.sum());df=df[~outside]
            key=list(zip(df['stock'],df['date'],df['headline']))
            dup=pd.Series([k in seen for k in key],index=df.index)|df.duplicated(['stock','date','headline'])
            seen.update(key)
            r['dropped_duplicates']+=int(dup.sum());df=df[~dup]
            if df.empty:continue
            tickers.update(df['stock'].unique())
            lo=min(lo,df['date'].min()) if lo is not None else df['date'].min()
            hi=max(hi,df['date'].max()) if hi is not None else df['date'].max()
            df['date']=df['date'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            df['source']=src.name
            df.to_csv(out,index=False,mode='w' if first else 'a',header=first);first=False
            r['rows_out']+=len(df)
        report[src.name]=r;total+=r['rows_out']
        print(' ',src.name,r,flush=True)
    report.update(rows_out=total,tickers_out=len(tickers),min_date=str(lo),max_date=str(hi))
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--out',type=Path,default=Path('data/cleaned'))
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    print('Window: 2018-01-01 to 2020-12-31 inclusive (UTC)')
    print('companies',clean_companies(a.data/COMPANIES,a.out/OUTPUTS['companies']),flush=True)
    print('prices',clean_prices(a.data/PRICES,a.out/OUTPUTS['prices']),flush=True)
    print('news',clean_news([a.data/NEWS_DIR/f for f in NEWS],a.out/OUTPUTS['news']),flush=True)
    print('Saved',', '.join(str(a.out/f) for f in OUTPUTS.values()))

if __name__=='__main__':
    main()
