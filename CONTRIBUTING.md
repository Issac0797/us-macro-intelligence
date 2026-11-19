# Contributing

Use a feature branch and a pull request into `main`. Describe the trigger, resulting behavior, data/permission impact and validation. Do not add databases, API keys, logs, screenshots of private workspaces, local absolute paths or personal settings.

Run frontend and backend tests, both TypeScript checks and the static release checks described in [LOCAL_DEVELOPMENT](docs/LOCAL_DEVELOPMENT.md). Keep the local backend test suite; a static-only build is not a reason to remove it. PostgreSQL tests create random isolated schemas and must never be pointed at an account without that scope.

Data additions require an original source, per-series permission review, attribution and registry approval **before export**. Unknown rights fail closed. Never generate substitute data, fill gaps silently, label snapshots live, or describe latest revisions as historical vintages. Add focused tests for material calculation or validation changes.

Original contributions are submitted under the project MIT license. You must have the right to contribute the code; retain external notices and keep data licensing separate. Do not include agency seals or other protected marks. Use GitHub's private security advisory channel for vulnerabilities, not public issues.
