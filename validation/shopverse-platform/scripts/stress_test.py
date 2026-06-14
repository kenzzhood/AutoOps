#!/usr/bin/env python3
"""Generate traffic and stress-test ShopVerse for AutoOps validation."""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
import time

import httpx

GATEWAY = "http://localhost:8080"


def one_checkout(client: httpx.Client, user_id: int) -> int:
    try:
        client.post(f"{GATEWAY}/api/checkout/cart/add", params={"user_id": user_id, "product_id": 1})
        r = client.post(f"{GATEWAY}/api/checkout", json={"user_id": user_id}, timeout=60.0)
        return r.status_code
    except httpx.HTTPError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    start = time.perf_counter()
    statuses: list[int] = []
    with httpx.Client(timeout=60.0) as client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(one_checkout, client, (i % 50) + 1) for i in range(args.requests)]
            for f in concurrent.futures.as_completed(futures):
                statuses.append(f.result())
    elapsed = time.perf_counter() - start
    ok = sum(1 for s in statuses if 200 <= s < 300)
    print(f"requests={args.requests} ok={ok} elapsed={elapsed:.1f}s rps={args.requests/elapsed:.1f}")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
