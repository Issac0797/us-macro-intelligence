# Iteration 9 acceptance — 2026-11-19

This table reports observed results, not intended cloud behavior. Status vocabulary: **PASS**, **PARTIAL**, **BLOCKED**, **NOT TESTED**.

| Acceptance item | Status | Observed result |
| --- | --- | --- |
| Independent clean source candidate | PASS | Explicit allowlist export; no original Git objects, database, logs, credentials or personal research |
| Source sensitive-information scan | PASS | Configured credential/key/token/path/private-IP patterns; exact private values checked separately without printing them |
| Original repository public-release safety | BLOCKED | Local database password in old README/example blobs; old object database must remain private |
| Credential rotation | PASS | New SCRAM credential works; old/wrong/empty passwords rejected; private .env updated and backend/Worker restored |
| MIT + dependency notices | PASS | Original code grant scoped separately from agency data, fixtures and dependencies |
| Snapshot permissions / schema | PASS | 13 approved original-agency series, 17,192 observation records (including nulls), 5 selected official Fed decisions; all observations equal captured official responses; unreviewed data excluded |
| Snapshot adversarial and scan checks | PASS | 8 tests reject unknown series, missing attribution, fake-live flag, invalid/duplicate dates, coverage/source/policy mismatches; 4 secret/path/runtime negative cases |
| Original frontend tests | PASS | 63 passed, 0 skipped; repeated successfully on Node 24.22.3 |
| Static calculation/configuration tests | PASS | 13 passed, including four-panel migration, exact-date cursor gaps, zoom-bound exports and allowlisted search |
| Original backend SQLite regression | PASS | 162 passed, 1 skipped; upstream Starlette deprecation warning retained |
| Original backend SQLite + PostgreSQL | PASS | 237 passed, 0 skipped; random isolated schemas; original frontend + backend total 300 passed |
| Both TypeScript checks | PASS | Original frontend and independent showcase |
| Original full terminal production build | PASS | Separate build succeeded; original dynamic routes preserved; active local build unchanged |
| Static Next.js export | PASS | Ten named routes plus actual 404; no dynamic API/server route in showcase |
| Static artifact/link checks | PASS | 94 generated files and 360 local HTML links; no terminal API path or configured sensitive patterns |
| Deep-link HTTP checks | PASS | Ten routes, explicit index documents, five static assets, unknown-route 404 on plain HTTP server |
| Clean clone website build | PASS | Independent local clone on official Node 24.22.3 / Windows; no .env, frontend/node_modules, DB URL or FRED key; 10-route export and artifact checks passed |
| Browser values / layout | PASS | Real CPI/UNRATE/payroll/10Y cards; Treasury comparison 2026-11-16 versus 2020-01-02; 13 source rows and four notice/download links |
| Language / light-dark / browser persistence | PASS | English light, Chinese dark, System current preference, DGS10/DGS2 save/reload verified |
| Chart interaction | PASS locally | Four charts matched cursor date 2024-06-14: monthly panels showed no native observation; DGS2 4.67 / DGS10 4.20. All four zoomed to 2023-05-11 through 2026-11-16 with equal stable event counts |
| Mobile layout | PASS | 390px viewport; no document horizontal overflow; charts remain rendered |
| Dependency vulnerability checks | PASS | Both npm audits: 0 reported; pinned Python lock: no known vulnerabilities reported |
| Windows full local terminal | PASS | Original startup script; backend health/series/overview and frontend return HTTP 200; existing 31-series catalog available |
| GitHub-hosted Actions execution | PASS | [Hosted quality run](https://github.com/Issac0797/us-macro-intelligence/actions/runs/44430086339) passed all checks and 325 tests on Ubuntu with disposable PostgreSQL |
| GitHub public clone over Internet | PASS | Actual HTTPS clone of public main, Node 24.22.3, no private env/key/database; static export and scans passed |
| Cloudflare Pages build / main deployment | PASS | https://us-macro-intelligence.pages.dev/ ; Git Integration, automatic main builds; initial deployment 23907fdc-9656-49cb-a5b8-4cd6b51b5d19 |
| PR preview deployment | PASS | PR #1 triggered Pages Git Integration; https://d1beb7df.us-macro-intelligence.pages.dev/ ; all ten HTTPS routes, 404, security headers and snapshot/notice byte checks passed; see PREVIEW_DEPLOYMENT.json |
| Public cloud routing / headers / snapshot | PASS | Ten HTTPS routes, unknown-route 404, same-origin CSP, nosniff, and four public data/notice files byte-identical to audited build; see PUBLIC_DEPLOYMENT.json |
| Failed cloud build retention / rollback | NOT TESTED | Documented procedure; no recovery exercise claimed |
| Public release authorization | PASS | Owner explicitly authorized public repository first, then static deployment on 2026-11-19 |

See [FEATURE_COVERAGE](FEATURE_COVERAGE.md), [SECURITY_AUDIT](SECURITY_AUDIT.md), [DATA_LICENSES](DATA_LICENSES.md), [DEPLOYMENT](DEPLOYMENT.md), [RELEASE_CHECKLIST](RELEASE_CHECKLIST.md) and [MAINTENANCE](MAINTENANCE.md). Screenshots are in `docs/screenshots/` and the exact source-file inventory is [FILE_MANIFEST](FILE_MANIFEST.json).

The original 300 tests and 25 static/snapshot/security tests passed: **325 total**. A second clean clone passed source manifest, JSON Schema, HTTP routes, 12 validation/security cases and static artifact scans. Local build logs are deliberately kept private because they contain workstation paths. Machine-readable safe results: [VALIDATION_RESULTS](VALIDATION_RESULTS.json).

Validation caveats: Windows checks, GitHub Ubuntu quality and the first Cloudflare build have passed. The standalone SQLite-only run intentionally skipped one unsupported case; the full SQLite/PostgreSQL run passed 237 with no skips. System theme was checked against the current host setting; the host OS setting was not changed. Regex scans and vulnerability databases have finite coverage. Cloud checks without observed evidence remain NOT TESTED; deployment does not imply that browser interactions or recovery exercises passed.

| Additional release check | Status | Evidence |
| --- | --- | --- |
| Windows system theme switching | NOT TESTED | Settings process did not expose a responsive controllable window; no media-query simulation was substituted |
| CSV / JSON / PNG browser downloads | PASS | Public Chrome downloads inspected: 1,532 DGS10 observations equal audited source; 64 nulls preserved; source/time/notice verified. PNG visually verified with snapshot/source/terms footer |
| Ctrl+K / four-panel save-reload | PASS | Public Ctrl+K DGS10 result opened workspace; changed panel 2 to CPIAUCSL, saved, refreshed; four-panel configuration/theme/language persisted and exported JSON matches |
| Public four-panel cursor / zoom | PARTIAL | Two visible charts showed linked 2024-01-18 cursor with DGS10 4.14 and explicit monthly CPI gap; complete four-chart/zoom evidence remains the verified local run |
