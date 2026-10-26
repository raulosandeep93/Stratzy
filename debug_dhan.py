#!/usr/bin/env python3
"""
Debug script - directly tests Dhan API endpoints to find what's available.
Run: python3 debug_dhan.py <CLIENT_ID> <ACCESS_TOKEN>
"""
import sys
import json
import requests
from datetime import datetime, timedelta

def test_dhan(client_id, access_token):
    headers = {
        "access-token": access_token.strip(),
        "client-id": client_id.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def call(label, url, method="GET", body=None):
        print(f"\n{'='*60}")
        print(f"[{label}]")
        print(f"URL: {url}")
        try:
            if method == "POST":
                r = requests.post(url, headers=headers, json=body, timeout=15)
            else:
                r = requests.get(url, headers=headers, timeout=15)
            print(f"HTTP Status: {r.status_code}")
            try:
                data = r.json()
                print(json.dumps(data, indent=2)[:1500])
            except Exception:
                print(f"Raw text: {r.text[:500]}")
        except Exception as e:
            print(f"ERROR: {e}")

    # Test each endpoint
    call("1. Fund Limit (auth check)", "https://api.dhan.co/v2/fundlimit")
    call("2. Today Trade Book", "https://api.dhan.co/v2/trades")
    call("3. Positions", "https://api.dhan.co/v2/positions")
    call("4. Orders", "https://api.dhan.co/v2/orders")

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    call(f"5. Trade History (last 30d, page 0)", f"https://api.dhan.co/v2/trades/{from_date}/{to_date}/0")
    call(f"6. Trade History (last 30d, page 1)", f"https://api.dhan.co/v2/trades/{from_date}/{to_date}/1")

    # Try last 7 days
    from_date_7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    call(f"7. Trade History (last 7d)", f"https://api.dhan.co/v2/trades/{from_date_7}/{to_date}/0")

    # Try statements endpoint
    call("8. Ledger (statements)", "https://api.dhan.co/v2/statements/ledger")
    call("9. Trade Book v1", "https://api.dhan.co/trades")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 debug_dhan.py <CLIENT_ID> <ACCESS_TOKEN>")
        sys.exit(1)
    test_dhan(sys.argv[1], sys.argv[2])
