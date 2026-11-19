"""Check repository Markdown references and release manifest hashes offline."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':
    count=0
    for p in [ROOT/'README.md',ROOT/'README.zh-CN.md',ROOT/'CONTRIBUTING.md',ROOT/'SECURITY.md',*(ROOT/'docs').glob('*.md')]:
        if not p.exists():
            raise AssertionError('Required document missing: '+p.name)
        for match in re.finditer(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)',p.read_text(encoding='utf-8')):
            target=urlsplit(match[1])
            if target.scheme or target.netloc or not target.path:
                continue
            path=(p.parent/unquote(target.path)).resolve()
            assert path.is_relative_to(ROOT) and path.exists(),f'Broken documentation link in {p.name}: {target.path}'
            count+=1
    manifest=ROOT/'docs/FILE_MANIFEST.json'
    if manifest.exists():
        for entry in json.loads(manifest.read_text())['files']:
            p=ROOT/entry['path']
            assert p.is_file(),f'Manifest missing file: {entry["path"]}'
            assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],f'Manifest differs: {entry["path"]}'
    print('PASS:',count,'local Markdown references; release manifest integrity verified when present.')
