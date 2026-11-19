# Open-source security audit — 2026-11-18

Updated 2026-11-19 for the authorized independent source release. The original development repository remains private/local and is never reused for publication. Cloudflare execution is reported separately.

| Audit area | Result | Evidence / disposition |
| --- | --- | --- |
| Existing Git scope | PASS | Local parent repository has no reachable commits, no commit objects, no reflog entries and no configured remote. At the initial audit no nested repository was found; the independent candidate repository was created later. A private GitHub backup cannot be verified from this checkout. |
| Residual Git objects | BLOCKED for reusing old repository | Inspected all 853 objects: 717 blobs, 136 trees. Local database password occurs in old README/example blobs. Absence of commits does not make residual objects safe to publish. |
| Local FRED credential | PASS for exclusion | A nonempty key is present in private `.env`; exact-value search found no copy in audited source/history objects. It is never copied/exported or needed by the static build. |
| Local database credential | PASS — rotation verified | The local role now uses a new generated 384-bit password and role-scoped SCRAM authentication. New authentication succeeded; the old, random and empty passwords were rejected. Private environment settings were updated, backend/Worker restarted, and raw observation count stayed 228,913. No secret or verifier is included here. |
| Token/private-key scan | PASS within scope | Pattern scan found no confirmed SSH/private key or access token in export scope. A `monitoring-risk-...` website path was a token-pattern false positive; the scanner now uses token boundaries. |
| Paths / internal endpoints | PASS for candidate | Local build/test logs and installed PostgreSQL metadata contain personal paths and are excluded. Loopback instructions and full-terminal proxy defaults are intentional source-only configuration; exported browser assets contain no terminal API path. |
| Private artifacts | PASS for exclusion | `.env`, `.local`, database storage/backups, logs, research settings, historical reports/screenshots, installed dependencies and old Git metadata are absent from the source candidate. |
| Public snapshot | PASS | Original-agency permission whitelist, JSON Schema, attribution, coverage, dates, null handling and provenance checks. No database export, unreviewed series or personal research is included. |
| Software dependencies | PASS within locked scope | npm and Python metadata/lock review; copyleft and attribution obligations retained separately. No known vulnerabilities reported by the local registry audits. See DEPENDENCIES.md. |
| Cloud project / unseen remotes | PARTIAL | New public repository, required branch checks, enabled GitHub secret scanning/push protection/private reporting, Pages Git Integration and public output were verified. Other account resources, inaccessible branches and remote backups remain outside this audit. |

## Scope and method

The working-source/configuration/document/log text and every Git blob (including unreachable ones) were checked for exact locally configured credential values and patterns for private keys, access tokens, credential-bearing database URLs, personal absolute paths and private IPv4 addresses. Installed dependencies were reviewed through their locks, metadata, license texts and vulnerability databases. Generated old Next builds, executable/runtime dependencies, database binary pages and binary documents were not exhaustively secret-scanned; they are categorically excluded from the release. Historical local screenshots/research evidence are also excluded rather than presumed safe.

The public source is copied by explicit file/directory allowlists into an independent candidate with a new Git object database. Source/compiled-output scans, physical routes and schema checks run again there. Exact private credential values were also checked against every manifest file and every new Git blob; no match was found. The local candidate commits use a reserved example.invalid preparation identity so no personal Git identity is released. No hidden `.git`, `.env`, private folder, old history or local research configuration is transferred. Scans report paths/categories and do not print credential values. Pattern checks cannot prove the absence of every possible secret format; the allowlist and isolation are independent safeguards.

## Credential response and release gate

**Do not publish or mirror the original Git object database.** The old repository remains BLOCKED for direct release until the exposed database credential is rotated and every intended publication ref/artifact is re-audited. A new clean candidate avoids transferring those objects, but does not itself revoke a password.

Recommended rotation, performed privately by the database owner:

1. Keep the current development backup private. Inventory any remote/backup/artifact outside this checkout and determine whether the same password reached it or was reused elsewhere.
2. Stop local monitoring/API services using their normal local controls. Open an authenticated local `psql` session, use interactive `\password macro`, and choose a new unique secret. Do not put the password in shell history, SQL files, logs or Git.
3. Update private `.env` and URL-encode the new password in its `DATABASE_URL`; update any private Compose secret/configuration that refers to it. Restart and verify health/sync. Keep public `.env.example` as a placeholder only.
4. If there is any evidence of FRED Key exposure beyond private `.env`, revoke/regenerate it in the provider account and update `.env`. No FRED key exposure was confirmed by this local audit.
5. If prior remote commits or published secrets are discovered, mark the affected release BLOCKED, revoke first, then coordinate history/artifact cleanup. Never rely on deleting a line or adding `.gitignore` as credential remediation.

Rotation was completed on 2026-11-18 UTC. The portable role previously had no password and accepted trust authentication; updating the environment alone would not have revoked access. Role-scoped local and replication authentication was therefore changed to SCRAM. Only the private environment file stores the new plaintext credential, with owner/system/administrator access. PostgreSQL retains a SCRAM verifier. No raw password/verifier was written to terminal output, Git or this report. The original Git object database remains private regardless of revocation.
