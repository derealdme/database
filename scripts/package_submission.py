"""Build a private source/data/manual ZIP; does not upload or publish any data."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--deck',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];output=a.output.resolve()
    if output.exists():raise SystemExit('Refusing to overwrite an existing package')
    tracked=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
    entries={name:root/name for name in tracked}
    for name in ['financialinformation.zip','listingdayto2023.zip','financialnews.zip']:
        path=root/'data'/name
        if not path.is_file():raise SystemExit('Required source missing: '+name)
        entries['data/'+name]=path
    # Private derived benchmark rows are never included in the public git tree.
    fixture=root/'data/benchmark-prices.csv.gz'
    if fixture.is_file():entries['data/benchmark-prices.csv.gz']=fixture
    if a.deck:
        if not a.deck.is_file():raise SystemExit('Deck missing')
        entries['docs/QuantScore-demo.pptx']=a.deck.resolve()
    manifest={'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'files':{}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in sorted(entries.items()):
            if not path.is_file():raise SystemExit('Tracked file missing: '+name)
            digest=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
            manifest['files'][name]={'sha256':digest.hexdigest(),'bytes':path.stat().st_size}
            z.write(path,'QuantScore/'+name,compress_type=zipfile.ZIP_STORED if path.suffix in {'.zip','.gz','.pptx'} else zipfile.ZIP_DEFLATED)
        z.writestr('QuantScore/SUBMISSION_MANIFEST.json',json.dumps(manifest,indent=2))
    print(json.dumps({'output':str(output),'bytes':output.stat().st_size,'files':len(entries),'git_commit':manifest['git_commit']}))
if __name__=='__main__':main()
