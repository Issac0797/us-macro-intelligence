"""Schema plus fail-closed license, provenance, ordering and coverage checks."""
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
def validate(path=None):
    path=Path(path or ROOT/'showcase/public/data/snapshot.json')
    data=json.loads(path.read_text(encoding='utf-8'))
    from jsonschema import Draft202012Validator
    schema=json.loads((ROOT/'data/snapshot.schema.json').read_text())
    Draft202012Validator(schema,format_checker=Draft202012Validator.FORMAT_CHECKER).validate(data)
    registry=json.loads((ROOT/'data/licenses.json').read_text(encoding='utf-8'))
    allowed={s['id']:s for s in registry['series'] if s['status']=='approved' and s['permission']=='public-domain'}
    assert data['is_live'] is False
    generated=datetime.fromisoformat(data['generated_at']);assert generated.tzinfo
    assert generated.date()<=date.today(), 'Future generation date'
    ids=[s['id'] for s in data['series']]
    assert len(ids)==len(set(ids)) and set(ids)==set(allowed), 'Snapshot differs from reviewed whitelist'
    downloads=set()
    for s in data['series']:
        for k,v in allowed[s['id']].items():
            assert s.get(k)==v, f'License/metadata mismatch: {s["id"]}.{k}'
        assert s['generated_at']==data['generated_at']
        dates=[o['date'] for o in s['observations']]
        assert dates==sorted(set(dates)), 'Duplicate or unordered dates'
        assert s['coverage']==dict(start=dates[0],end=dates[-1],count=len(dates))
        assert dates[-1]<=generated.date().isoformat()
        assert all(o['value'] is None or math.isfinite(o['value']) for o in s['observations'])
        assert any(o['value'] is not None for o in s['observations'])
        if s['provider']=='bls':
            assert all(d.endswith('-01') for d in dates)
        downloads.add(s['download_url'])
    for url,digest in data['source_checksums'].items():
        parsed=urlparse(url)
        assert parsed.scheme=='https' and parsed.hostname in {'api.bls.gov','www.federalreserve.gov'}
        assert not parsed.username and not parsed.password
        assert len(digest)==64 and all(c in '0123456789abcdef' for c in digest)
    for s in data['series']:
        assert any(url==s['download_url'] or url.startswith(s['download_url']+'?startyear=') for url in data['source_checksums'])
    assert registry['fed_policy']['status']=='approved'
    decision_dates=[]
    for d in data['fed_decisions']:
        assert d['lower']<=d['upper'] and d['units']=='Percent'
        assert urlparse(d['source_url']).hostname=='www.federalreserve.gov'
        assert d['source_url'].endswith('monetary'+d['date'].replace('-','')+'a.htm')
        assert d['source_url'] in data['source_checksums']
        assert d['date']<=generated.date().isoformat()
        decision_dates.append(d['date'])
    assert decision_dates==sorted(set(decision_dates))
    return data

if __name__=='__main__':
    d=validate(sys.argv[1] if len(sys.argv)>1 else None)
    print('PASS: JSON Schema, license whitelist, provenance, dates, values and coverage;',len(d['series']),'series')
