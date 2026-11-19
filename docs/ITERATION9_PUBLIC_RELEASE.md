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
| Remaining browser exports/search/persistence checks | PARTIAL | Code and unit/build checks passed; manual browser run was interrupted |
| Independent Git history/source scan | PASS before first push | New repository has no inherited history or tags; 258 staged files and all new Git blobs scanned against active/historical credentials; no match |
| Public repository | NOT TESTED | Target: https://github.com/Issac0797/us-macro-intelligence ; creation/push pending |
| Hosted GitHub Actions | NOT TESTED | Read-only pull_request workflow; disposable PostgreSQL only; no private keys or local database access |
| Cloudflare Pages build / production URL | NOT TESTED | Git Integration required; production branch main; npm run build:showcase; output showcase/out |
| PR Preview / public HTTPS routes / rollback | NOT TESTED | Must be verified after successful GitHub CI and authorized Cloudflare connection |
| Public release tag | NOT TESTED | v0.1.0 Public Preview planned after deployment verification |

Code is MIT; agency data, source extracts and dependency licenses remain separate. Unknown data permissions fail closed. The website is a frozen snapshot, not a live research backend. See SECURITY_AUDIT.md, ACCEPTANCE.md, DATA_LICENSES.md and DEPLOYMENT.md for scope and procedures.
