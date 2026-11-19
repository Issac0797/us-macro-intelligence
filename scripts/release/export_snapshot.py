"""Explicit opt-in refresh of approved ORIGINAL-agency data. Never invoked by builds.

No database, .env, API key, local research state, or FRED downloads are read.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def export(start_year=2020, use_cached_sources=False):
    registry = json.loads((ROOT / 'data/licenses.json').read_text(encoding='utf-8'))
    approved = [s for s in registry['series'] if s['status'] == 'approved' and s['permission'] == 'public-domain']
    if len(approved) != len(registry['series']):
        raise ValueError('Registry contains unapproved export entries')
    now = datetime.now(timezone.utc)
    today = now.date()
    cache = ROOT / '.local/snapshot-sources'
    cache.mkdir(parents=True, exist_ok=True)
    records, checksums = [], {}

    def download(url, filename):
        # Cache is evidence only; an explicit refresh always downloads again.
        cached = cache / filename
        if use_cached_sources and cached.exists():
            raw = cached.read_bytes()
        else:
            with urlopen(Request(url, headers={'User-Agent':'US-Macro-Intelligence/0.1 (public-domain research snapshots)'}), timeout=60) as response:
                raw = response.read()
        if not raw:
            raise ValueError('Empty official source response')
        (cache / filename).write_bytes(raw)
        checksums[url] = hashlib.sha256(raw).hexdigest()
        return raw

    for s in approved:
        if s['provider'] != 'bls':
            continue
        observations = {}
        for year in range(start_year, today.year + 1, 3):
            end_year = min(year + 2, today.year)
            url = f"{s['download_url']}?startyear={year}&endyear={end_year}"
            result = json.loads(download(url, f"{s['native_id']}-{year}.json"))
            if result.get('status') != 'REQUEST_SUCCEEDED':
                raise ValueError(f"Official BLS request failed for {s['id']}")
            source = result['Results']['series']
            if len(source) != 1 or source[0]['seriesID'] != s['native_id']:
                raise ValueError('Unexpected BLS series identity')
            for o in source[0]['data']:
                if o['period'].startswith('M') and 1 <= int(o['period'][1:]) <= 12:
                    day = f"{o['year']}-{o['period'][1:]}-01"
                    if day <= today.isoformat():
                        value = None if o['value'] in ('-', '.', '', 'NA') else float(o['value'])
                        observations[day] = dict(date=day,value=value)
        if not observations:
            raise ValueError('No observations; refusing empty snapshot')
        records.append({**s,'observations':sorted(observations.values(),key=lambda x:x['date'])})
        print('Fetched approved BLS series:', s['id'], len(observations))

    fed = {s['native_id']:s for s in approved if s['provider']=='fed'}
    url = next(iter(fed.values()))['download_url']
    raw = download(url, 'FRB_h15_xml.zip')
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        with archive.open('H15_data.xml') as stream:
            for event, element in ET.iterparse(stream, events=['end']):
                if not element.tag.endswith('Series'):
                    continue
                native = element.attrib.get('SERIES_NAME')
                if native in fed:
                    s = fed[native]
                    points = []
                    for o in element:
                        if not o.tag.endswith('Obs'):
                            continue
                        day = o.attrib.get('TIME_PERIOD','')
                        if f'{start_year}-01-01' <= day <= today.isoformat():
                            raw_value = o.attrib.get('OBS_VALUE')
                            value = float(raw_value) if raw_value not in (None,'','ND','NA') and o.attrib.get('OBS_STATUS')=='A' else None
                            points.append(dict(date=day,value=value))
                    if not points:
                        raise ValueError(f"Empty approved series {native}")
                    records.append({**s,'observations':points})
                    print('Extracted approved H.15 series:',s['id'],len(points))
                element.clear()
    if {s['id'] for s in records} != {s['id'] for s in approved}:
        raise ValueError('Official XML missing required whitelist series')

    # Existing parser validates rates and publication dates; only selected facts exported.
    sys.path.insert(0,str(ROOT/'backend'))
    from app.fed.parsers import parse
    decisions=[]
    for day in ['2020-03-15','2022-03-16','2023-07-26','2024-09-18','2026-10-28']:
        url=f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{day.replace('-','')}a.htm"
        raw=download(url,f'policy-{day}.html')
        parsed=parse(raw.decode('utf-8-sig'),'statement')
        content=parsed['content']
        if parsed['published_at'].date().isoformat()!=day:
            raise ValueError('Policy publication date mismatch')
        decisions.append(dict(date=day,lower=float(content['lower']),upper=float(content['upper']),units='Percent',source='Board of Governors of the Federal Reserve System',source_url=url,verified_at=now.isoformat(),notice='Selected factual decision from a Board public-domain statement; not a complete policy chronology.'))
    for s in records:
        s['coverage']={'start':s['observations'][0]['date'],'end':s['observations'][-1]['date'],'count':len(s['observations'])}
        s['generated_at']=now.isoformat()
    payload=dict(schema_version=1,generated_at=now.isoformat(),is_live=False,revision_basis='Latest original-agency observations retrieved at snapshot generation; NOT historical vintages or release-time data.',series=records,fed_decisions=decisions,source_checksums=checksums)
    target=ROOT/'showcase/public/data/snapshot.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    from validate_snapshot import validate
    validate(temporary)
    temporary.replace(target)
    print('Validated and atomically replaced snapshot:',len(records),'series,',sum(len(s['observations']) for s in records),'observations')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh-approved',action='store_true',required=True,help='Explicitly download only approved original-agency sources')
    p.add_argument('--use-cached-sources',action='store_true',help='Resume an interrupted export using locally captured source evidence; missing sources are still downloaded')
    args=p.parse_args()
    export(use_cached_sources=args.use_cached_sources)
