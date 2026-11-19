"""Refresh source release hashes from reviewed/staged Git files, never the runtime."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':
    result=subprocess.run(['git','-C',str(ROOT),'ls-files','-z'],capture_output=True,check=True)
    files=[]
    for name in sorted(result.stdout.decode().split('\0')):
        if not name or name=='docs/FILE_MANIFEST.json':continue
        path=ROOT/name
        if path.is_file():files.append(dict(path=name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if not files:raise ValueError('Stage reviewed source files before refreshing the manifest')
    (ROOT/'docs/FILE_MANIFEST.json').write_text(json.dumps(dict(scope='Reviewed source release files; excludes this manifest and generated/installed files.',files=files),indent=2)+'\n',encoding='utf-8')
    print('Updated source manifest:',len(files),'files. Review and stage the manifest before committing.')
