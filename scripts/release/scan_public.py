"""Conservative source/artifact checks; print locations, never matching values."""
import argparse
import os
from pathlib import Path
import re
import sys

RULES={
    'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'token':r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{24,})\b',
    'personal-windows-path':r'(?i)[A-Z]:[\\/]Users[\\/][^\s"\x27<>]+',
    'private-IP':r'(?<![\d.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![\d.])',
    'credential-connection-string':r'(?i)(?:postgres(?:ql)?(?:\+psycopg)?|mysql|redis)://[^\s/:]+:(?!CHANGE_ME_LOCAL_ONLY@)[^\s@]+@',
    'secret-assignment':r'(?i)(?:api[_-]?key|token|password|secret)\s*[=:]\s*[\"\x27]?(?!ci_ephemeral_test_only\b|CHANGE_ME_LOCAL_ONLY\b)[A-Za-z0-9_/+\-]{16,}',
}
EXCLUDE={'.git','node_modules','.venv','__pycache__','.pytest_cache','.next'}
BANNED_SUFFIX={'.dump','.backup','.sql','.db','.sqlite','.sqlite3','.key','.pem','.p12','.log'}
def scan(root):
    failures=[];count=0
    for current,dirs,names in os.walk(root):
        dirs[:]=[d for d in dirs if d not in EXCLUDE and not d.startswith('.next') and not (d=='shared' and (Path(current)/d).relative_to(root).as_posix()=='showcase/shared')]
        for name in names:
            path=Path(current)/name;relative=path.relative_to(root).as_posix()
            if name.startswith('.env') and name!='.env.example' or path.suffix.lower() in BANNED_SUFFIX or any(part in {'.local','logs','pgdata'} for part in path.relative_to(root).parts):
                failures.append((relative,'forbidden-file'));continue
            count+=1
            if path.suffix.lower() in {'.png','.jpg','.jpeg','.woff','.woff2','.ico','.zip','.pdf'}:
                continue
            data=path.read_bytes()
            if b'\x00' in data[:8000]:
                failures.append((relative,'unreviewed-binary'));continue
            text=data.decode('utf-8',errors='replace')
            for category,pattern in RULES.items():
                if re.search(pattern,text):
                    failures.append((relative,category))
    for path,category in failures:
        print(f'BLOCKED: {path} [{category}]')
    if failures:
        raise SystemExit(1)
    print(f'PASS: {count} files; no forbidden artifacts or configured credential/path/IP patterns detected.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    args=parser.parse_args();scan(args.root.resolve())
