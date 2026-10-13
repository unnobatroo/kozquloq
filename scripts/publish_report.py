#!/usr/bin/env python3
"""Push an exported report.json into Supabase so the dashboard goes live.

Usage:
    uv run kozquloq report --json-out report.json
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... uv run python scripts/publish_report.py report.json

Service key stays server-side — the dashboard only ever uses the anon key.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("set SUPABASE_URL and SUPABASE_SERVICE_KEY")
    path = sys.argv[1] if len(sys.argv) > 1 else "report.json"
    with open(path) as f:
        payload = json.loads(f.read())
    req = urllib.request.Request(
        f"{url}/rest/v1/reports",
        data=json.dumps({"payload": payload}).encode(),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as res:  # noqa: S310 — user-provided URL
        print(f"published {path} -> {res.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
