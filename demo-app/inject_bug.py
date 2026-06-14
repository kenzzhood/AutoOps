#!/usr/bin/env python3
"""Generate checkout traffic and optionally enable the N+1 bug."""

from __future__ import annotations

import argparse
import random
import sys
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject traffic and toggle N+1 bug")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--enable-bug", action="store_true")
    parser.add_argument("--disable-bug", action="store_true")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=30.0)

    if args.enable_bug:
        r = client.post("/admin/toggle-bug", params={"enabled": True})
        print("Bug enabled:", r.json())
    elif args.disable_bug:
        r = client.post("/admin/toggle-bug", params={"enabled": False})
        print("Bug disabled:", r.json())

    email = f"demo_{random.randint(1000, 9999)}@autoops.test"
    reg = client.post("/auth/register", json={"email": email, "password": "demo123"})
    if reg.status_code == 400:
        login = client.post("/auth/login", json={"email": email, "password": "demo123"})
        user_id = login.json()["user_id"]
    else:
        user_id = reg.json()["user_id"]

    client.get("/products")
    errors = 0
    latencies: list[float] = []

    for i in range(args.requests):
        start = time.perf_counter()
        try:
            resp = client.post("/checkout", json={"user_id": user_id})
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            if resp.status_code >= 400:
                errors += 1
                print(f"  [{i+1}] ERROR {resp.status_code} {elapsed:.0f}ms")
            else:
                data = resp.json()
                print(f"  [{i+1}] OK {data.get('duration_ms', elapsed):.0f}ms total=${data.get('total', 0):.2f}")
        except httpx.HTTPError as exc:
            errors += 1
            print(f"  [{i+1}] FAIL {exc}")
        time.sleep(0.1)

    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"\nSummary: {args.requests} requests, {errors} errors ({errors/args.requests*100:.1f}%), avg {avg:.0f}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
