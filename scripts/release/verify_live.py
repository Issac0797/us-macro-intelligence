"""Read-only HTTPS checks of the deployed public Pages production hostname.

Run separately from builds; no database, private environment or API key is used.
The fixed target prevents workflow dispatch from probing arbitrary resources.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://us-macro-intelligence.pages.dev"
ROUTES = ["/", "/inflation/", "/labor/", "/yield-curve/", "/workspace/",
          "/analytics/", "/business-cycle/", "/fed/", "/sources/", "/about/"]


def check(path):
    expected_status = 404 if path == "/release-check-unknown-route/" else 200
    request = urllib.request.Request(BASE + path, headers={
        "User-Agent": "US-Macro-Intelligence-Live-Verification"})
    last_error = None
    for attempt in range(3):
        try:
            try:
                response = urllib.request.urlopen(request, timeout=20)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                raw = response.read()
                status = response.code
                headers = {k.lower(): v for k, v in response.headers.items()}
            assert status == expected_status, "Unexpected HTTP status"
            assert headers.get("x-content-type-options") == "nosniff", "Missing nosniff"
            assert "connect-src 'self'" in headers.get("content-security-policy", ""), "Missing same-origin CSP"
            if path == "/data/snapshot.json":
                assert raw == (ROOT / "data/snapshot.json").read_bytes(), "Snapshot differs from reviewed source"
                assert json.loads(raw)["is_live"] is False, "Snapshot is incorrectly live"
            if path in ROUTES:
                assert b"US Macro Intelligence" in raw, "Missing site document"
            return {"path": path, "status": "PASS", "http_status": status,
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        except Exception as error:
            last_error = type(error).__name__
            if attempt < 2:
                time.sleep(1)
    return {"path": path, "status": "FAIL", "error_type": last_error}


if __name__ == "__main__":
    paths = ROUTES + ["/data/snapshot.json", "/release-check-unknown-route/"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, paths))
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "base_url": BASE, "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
              "results": results}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
