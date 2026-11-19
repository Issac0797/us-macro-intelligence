# Software license and dependency review

Status: **PASS for this source/static release**, subject to preserving the listed upstream terms. Original project code is offered under MIT; dependency and agency rights remain separate. This is not a claim that all dependencies are MIT.

The locked manifests are inventoried in [dependency-licenses.json](dependency-licenses.json). [THIRD_PARTY_NOTICES.txt](../THIRD_PARTY_NOTICES.txt) retains installed upstream license and NOTICE texts, and is also linked from the static Sources page. The source release contains no `node_modules`, Python environment or native dependency binaries.

| Component | License / treatment |
| --- | --- |
| React, Next.js, Lucide and most UI dependencies | MIT; preserve upstream copyright and permission text |
| ECharts, zrender | Apache-2.0; retain LICENSE/NOTICE and attribution; not relicensed MIT |
| FastAPI, SQLAlchemy, Alembic and other Python components | MIT or BSD/ISC/Apache-family terms as individually inventoried |
| psycopg / psycopg-binary | LGPL-3.0-only, dynamically imported unmodified dependency; not vendored, statically linked or shipped in the website |
| Sharp/libvips platform packages | Apache/LGPL as individually inventoried; dependency tooling only in this static release, no native library distributed in output |
| lightningcss / certifi | MPL-2.0; unmodified package-managed tools/data; no MPL files are incorporated into MIT source |
| caniuse-lite | CC-BY-4.0 database; build-time compatibility data; upstream notice retained |
| Test/dev tools | Retain their original terms; locked entries remain inventoried even when platform-optional packages are not installed |

MIT code may depend on these separately licensed components while respecting their own terms. Distributing modified MPL files, a frozen backend executable, containers/native libraries or a combined LGPL binary would require a new obligation review (including relevant source, modification/relinking and notice obligations). This release does not ship those artifacts.

The review covers the package locks and installed metadata/licenses, not an authorship attestation of every historical code line. The project owner must confirm the right to license original code at final release approval. No previously existing project license was found to conflict with the proposed MIT grant.

Local `npm audit` for both projects and `pip-audit` against the pinned Python lock reported no known vulnerabilities on 2026-11-18. This result is time-sensitive and does not guarantee absence of vulnerabilities. CI reruns those checks. Do not silently replace the lockfiles to bypass a failing audit.
