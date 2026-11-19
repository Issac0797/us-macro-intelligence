# Security policy

This is an unpublished release candidate. Security support initially covers the latest `main` revision only; there is no promised response SLA.

After the repository is created, use **Security → Advisories → Report a vulnerability** if private reporting is enabled. Before that channel exists, contact the project owner through an existing private channel. No public contact address is invented here. Do not disclose credentials or private evidence in an issue or PR.

Provide a minimal reproduction, affected revision and impact. Redact API keys, connection strings, browser storage, paths and personal research. Avoid testing against anyone else's deployment.

If a credential enters Git, stop release, revoke/rotate it at the issuer, assess usage and exposure, and remove it from every affected branch, tag, PR artifact and cache. Deleting a line or adding `.gitignore` does not revoke a secret. Prefer preparing a new sanitized repository over reusing contaminated Git objects. See [SECURITY_AUDIT](docs/SECURITY_AUDIT.md).

The static site accepts no credentials. The local full terminal should stay on loopback/private trusted infrastructure; it has no production authentication boundary. Keep `.env`, databases, logs, installed runtimes and user workspaces private.
