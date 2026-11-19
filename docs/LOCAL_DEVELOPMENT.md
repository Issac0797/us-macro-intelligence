# Local development and checks

Use Node.js 24 LTS and Python 3.12+ (3.13 used in local validation). Static build needs only Node. Full runtime requires PostgreSQL; Docker Compose uses PostgreSQL 18. Do not point the public static site at the local API.

## Native full terminal

From the repository root, create your own `.env` from `.env.example`, configure `POSTGRES_PASSWORD` and a matching URL-encoded password in `DATABASE_URL`, create a local `macro` database, and install dependencies. Do not overwrite existing settings.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
.venv/Scripts/python.exe -m pip install --no-deps -e ./backend
cd backend
../.venv/Scripts/alembic.exe upgrade head
../.venv/Scripts/python.exe -m app.sync --full
../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another shell run `npm.cmd ci --prefix frontend`, then `npm.cmd run dev --prefix frontend`. The Node server proxies `/api/v1/*` to the private loopback backend; API keys remain server-side. Backend runtime does not fall back to SQLite; SQLite is a test fixture only. The bundled source uses portable paths; optional local launch scripts expect an already configured local environment and are not installers. Existing developer databases are deliberately absent from this release.

## CI-equivalent validation

```sh
python -m pip install -r backend/requirements.lock -r scripts/release/requirements-checks.txt
python -m pip install --no-deps -e backend
npm ci --prefix frontend
npm ci --prefix showcase
npm test --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix showcase
npm run typecheck --prefix showcase
python -m pytest backend/tests -q
python scripts/release/validate_snapshot.py
python scripts/release/test_release.py
npm run build:showcase
python scripts/release/test_routes.py
python scripts/release/scan_public.py --root .
```

Run the source scan in a clean candidate/clone, before creating local `.env` or state. It intentionally blocks private runtime files. The same scan includes the exported output when present and skips installed dependencies/build caches. Dependency vulnerability databases are checked by `npm audit` for both apps and `pip-audit` against the pinned Python lock. A scan is a defense in depth, not proof that every secret format is detectable.

For PostgreSQL integration tests, supply `TEST_DATABASE_URL` through your shell's private environment. The fixture creates/drops a random `test_*` schema and runs SQLite and PostgreSQL cases; it does not clear production tables. CI provides a disposable PostgreSQL service. Never put production credentials into logs, workflow files or command-line arguments.

## Snapshot refresh (maintainer only)

```sh
python scripts/release/export_snapshot.py --refresh-approved
python scripts/release/validate_snapshot.py
python scripts/release/test_release.py
```

Refresh contacts only the BLS public API and Federal Reserve Board. It requires the existing Fed HTML parser dependency (`beautifulsoup4`) and the validation requirements, not a key or database. Network retrieval never happens during a website build. Capture raw source evidence under ignored `.local/snapshot-sources`; review permission changes, observations, nulls and coverage before committing only the approved JSON. BLS unregistered API quotas apply: do not repeatedly refresh while debugging. `--use-cached-sources` is for resuming an interrupted export; review evidence capture times before publishing a resumed snapshot.

The snapshot generator records SHA-256 of original responses. These prove the captured bytes' identity, not the authenticity of an untrusted source. A maintainer must continue to verify official HTTPS origins, units, permissions and source semantics. Latest observations may be revised and are not ALFRED vintages.
