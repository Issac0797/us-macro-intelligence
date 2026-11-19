# Iteration 9 Public Release

Updated: 2026-11-19 (Asia/Shanghai). Owner authorization: publish the independent GitHub repository first, then deploy the static site. Original private history is never published.

| Item | Status | Actual result |
| --- | --- | --- |
| Old database credential revoked | PASS | New SCRAM password accepted; old/random/empty rejected. Private .env updated and backend/monitor Worker restarted. Observation count unchanged during rotation |
| Data permission review | PASS | Same 13 approved original-agency series, 17,192 records and five historical Fed decisions; snapshot bytes match audited baseline 15109b6 |
| Tests | PASS | Backend 237 + original frontend 63 + static frontend 13 + schema/security 12 = 325 |
| Static build and routes | PASS locally | Node 24.22.3, ten public routes, real 404; no backend/DB/key needed; artifact scan retained |
| Four-chart cursor and zoom | PASS locally | Actual Chrome test; mixed daily/monthly dates preserved and missing dates explicit; equal stable event counts |
| OS System theme switching | NOT TESTED | Native Windows Settings was unresponsive; no simulated media preference passed off as OS evidence |
| Public browser exports/search/persistence | PASS | Actual public Chrome session: Ctrl+K DGS10 to workspace, EN/ZH, light/current System and dark, custom four-panel save/reload; CSV/JSON 1,532 observations including 64 nulls equal audited data; PNG visually verified with source/time/terms footer |
| Independent Git history/source scan | PASS before first push | New repository has no inherited history or tags; 258 staged files and all new Git blobs scanned against active/historical credentials; no match |
| Public repository | PASS | https://github.com/Issac0797/us-macro-intelligence ; new root commit 15eaed4c7589edd24557610d79cdafb4b9989187; no inherited private history |
| Hosted GitHub Actions | PASS | Initial run and [PR #1 quality](https://github.com/Issac0797/us-macro-intelligence/actions/runs/44480806804) passed all checks and 325 tests; Ubuntu, disposable PostgreSQL only, no production secrets |
| main protection | PASS | Strict quality check and PR required; force push/deletion forbidden; applies to admins |
| Internet public clone build | PASS | Actual public HTTPS clone on Node 24.22.3, no .env/DB/FRED key; ten routes, 94 output files, 360 links |
| Cloudflare Pages build / production URL | PASS | https://us-macro-intelligence.pages.dev/ ; Git Integration, main; successful initial production deployment 23907fdc-9656-49cb-a5b8-4cd6b51b5d19 |
| Public HTTPS, routes, snapshot and headers | PASS | Ten routes, actual unknown-route 404, four data/notice files byte-identical to audited build; CSP and security headers verified; see PUBLIC_DEPLOYMENT.json |
| PR Preview | PASS | PR #1 deployed https://d1beb7df.us-macro-intelligence.pages.dev/ ; all ten HTTPS routes, 404, headers, snapshot and notices passed |
| Rollback / failed production-build retention | PASS | Actual production rollback and restore verified by immutable deployment HTML hashes; controlled production build failure retained successful HTML/workspace/snapshot; normal command restored. See RECOVERY_RESULTS.json |
| Public release tag | NOT TESTED | v0.1.0 Public Preview planned after deployment verification |

Code is MIT; agency data, source extracts and dependency licenses remain separate. Unknown data permissions fail closed. The website is a frozen snapshot, not a live research backend. See SECURITY_AUDIT.md, ACCEPTANCE.md, DATA_LICENSES.md and DEPLOYMENT.md for scope and procedures.
