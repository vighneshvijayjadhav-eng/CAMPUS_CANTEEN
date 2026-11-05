"""Small async load test for a STAGING deployment (never production, never live payments).

    python infra/loadtest/loadtest.py https://canteen-staging.example.edu --users 50 --seconds 60

Simulates students browsing (institutes, canteens, menus, reviews) concurrently and reports
throughput and latency percentiles per endpoint. With --staff-cookie it also exercises the
counter queue poll used by every station screen. Read-only: it creates no orders.
"""

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict

import httpx


class Failed:
    status_code = 0

    def json(self):
        return []


async def timed(client, name, path, timings, errors, **kwargs):
    """GET and record latency; transport errors (e.g. a closed keep-alive) count as errors."""
    started = time.perf_counter()
    try:
        response = await client.get(path, **kwargs)
    except httpx.TransportError:
        errors[name] += 1
        return Failed()
    timings[name].append(time.perf_counter() - started)
    errors[name] += response.status_code != 200
    return response


async def user(client, deadline, timings, errors, staff_cookie):
    institutes = (await client.get("/api/v1/institutes")).json()
    if not institutes:
        raise SystemExit("No approved institutes on this deployment; nothing to browse")
    while time.monotonic() < deadline:
        institute = random.choice(institutes)
        canteens = await timed(
            client, "canteens", f"/api/v1/institutes/{institute['id']}/canteens", timings, errors
        )
        for canteen in canteens.json() if canteens.status_code == 200 else []:
            menu = await timed(
                client, "menu", f"/api/v1/canteens/{canteen['id']}/menu", timings, errors
            )
            items = menu.json() if menu.status_code == 200 else []
            if items:
                item = random.choice(items)["id"]
                await timed(
                    client, "reviews", f"/api/v1/menu-items/{item}/reviews", timings, errors
                )
        if staff_cookie:
            await timed(
                client,
                "staff_queue",
                "/api/v1/staff/orders",
                timings,
                errors,
                cookies={"canteen_access": staff_cookie},
            )
        await asyncio.sleep(random.uniform(0.5, 2.0))  # think time


def pct(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))] * 1000


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--users", type=int, default=25)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--staff-cookie", help="canteen_access cookie of a staging station account")
    args = parser.parse_args()
    if (
        "localhost" not in args.base_url
        and "staging" not in args.base_url
        and "127.0.0.1" not in args.base_url
    ):
        raise SystemExit("Refusing: point this at a local or staging URL only")
    timings, errors = defaultdict(list), defaultdict(int)
    deadline = time.monotonic() + args.seconds
    limits = httpx.Limits(max_connections=args.users)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=15, limits=limits) as client:
        await asyncio.gather(
            *(user(client, deadline, timings, errors, args.staff_cookie) for _ in range(args.users))
        )
    print(f"{args.users} users for {args.seconds}s against {args.base_url}")
    print(
        f"{'endpoint':<12} {'requests':>8} {'errors':>6} {'req/s':>7} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}"
    )
    for name, values in sorted(timings.items()):
        print(
            f"{name:<12} {len(values):>8} {errors[name]:>6} {len(values) / args.seconds:>7.1f} "
            f"{statistics.median(values) * 1000:>8.0f} {pct(values, 0.95):>8.0f} {max(values) * 1000:>8.0f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
