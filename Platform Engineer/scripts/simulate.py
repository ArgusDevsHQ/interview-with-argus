# ABOUTME: Places real orders while the shop restocks and reports what was lost.
# ABOUTME: Run it before and after a fix; the verdict is what a shop owner would read.
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from queue import Queue

API_URL = os.environ.get("API_URL", "http://localhost:8000")
ORDER_EVERY_SECONDS = 1.0
CONTROL_ORDERS = 3
MAX_WAIT_SECONDS = 15 * 60
REQUEST_DEADLINE_SECONDS = 60
NAMES = ["Ines", "Tom", "Aiko", "Dev", "Lena", "Marcus", "Sofia", "Jun", "Priya", "Owen", "Hana", "Luis"]


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict, float]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        API_URL + path, method=method, data=data, headers={"content-type": "application/json"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, None, REQUEST_DEADLINE_SECONDS) as response:
            return response.status, json.load(response), time.perf_counter() - started
    except urllib.error.HTTPError as error:
        return error.code, json.load(error), time.perf_counter() - started


def latest_run() -> dict | None:
    return call("GET", "/api/v1/stock-update")[1]["latest"]


def place_order(products: list[dict]) -> tuple[int, float]:
    product = random.choice(products)
    status, _, took = call(
        "POST", "/api/v1/orders",
        {"product_id": product["id"], "quantity": 1, "customer": random.choice(NAMES)},
    )
    return status, took


PROGRESS_EVERY_SECONDS = 15
_last_progress = 0.0


def line(label: str, text: str, end: str = "\n") -> None:
    global _last_progress
    if end == "":
        if sys.stdout.isatty():
            print(f"\r  {label:<24}{text:<60}", end="", flush=True)
        elif time.time() - _last_progress >= PROGRESS_EVERY_SECONDS:
            _last_progress = time.time()
            print(f"  {label:<24}{text}", flush=True)
        return
    _last_progress = 0.0
    print(f"\r  {label:<24}{text:<60}", flush=True)


def percentile(values: list[float], fraction: float) -> str:
    if not values:
        return "–"
    ordered = sorted(values)
    return f"{ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]:.2f} s"


def seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def wait_until(predicate, label: str, text: str) -> float:
    started = time.time()
    while not predicate():
        elapsed = time.time() - started
        line(label, f"{text} ({elapsed:.0f} s)", end="")
        if elapsed > MAX_WAIT_SECONDS:
            print()
            sys.exit(f"gave up after {MAX_WAIT_SECONDS} s: {text}. Is the worker running?")
        time.sleep(1)
    return time.time() - started


def main() -> int:
    print("\nLarkspur Roasters · restocking simulation\n")
    products = call("GET", "/api/v1/products")[1]

    def quiet() -> bool:
        run = latest_run()
        return run is None or run["status"] in ("completed", "failed")

    wait_until(quiet, "shop", "a restock is already running, waiting")
    line("shop", "quiet")

    before = [place_order(products) for _ in range(CONTROL_ORDERS)]
    line("control orders", f"{len(before)} placed, {sum(s == 201 for s, _ in before)} confirmed")

    queued = call("POST", "/api/v1/stock-update")[1]
    run_id = queued["id"]

    def running() -> bool:
        run = latest_run()
        return run is not None and run["id"] == run_id and run["status"] != "requested"

    wait_until(running, "restocking", "queued")
    started = time.time()
    results: Queue = Queue()
    threads: list[threading.Thread] = []
    while True:
        run = latest_run()
        if run["id"] == run_id and run["status"] != "running":
            break
        line("restocking", f"running ({time.time() - started:.0f} s), {len(threads)} orders placed", end="")
        thread = threading.Thread(target=lambda: results.put(place_order(products)), daemon=True)
        thread.start()
        threads.append(thread)
        time.sleep(ORDER_EVERY_SECONDS)
    for thread in threads:
        thread.join()
    during = [results.get() for _ in threads]
    restock_seconds = seconds_between(run["started_at"], run["finished_at"])
    line("restocking", f"{run['status']} in {restock_seconds:.0f} s, {run['movements_replayed'] or 0:,} movements replayed")

    lost = sum(status != 201 for status, _ in during)
    tooks = [took for _, took in during]
    line(
        "orders during restock",
        f"{len(during)} placed, {lost} lost   p50 {percentile(tooks, 0.5)}   p95 {percentile(tooks, 0.95)}",
    )

    after = [place_order(products) for _ in range(CONTROL_ORDERS)]
    line("control orders after", f"{len(after)} placed, {sum(s == 201 for s, _ in after)} confirmed")

    check = call("GET", "/api/v1/stock-check")[1]
    mismatches = check["mismatches"]
    off_by = sum(abs(m["on_hand"] - m["ledger"]) for m in mismatches)
    line(
        "stock check",
        f"{check['products_checked']} products, "
        + ("counts match the ledger" if not mismatches else f"{len(mismatches)} counts off by {off_by} bags"),
    )

    print()
    if run["status"] != "completed":
        print("VERDICT  Restocking failed. Check the worker log.")
        return 1
    if lost:
        print(f"VERDICT  We lost {lost} of {len(during)} orders placed while restocking. Oh no.")
        print('         Every one of them got "Things are busy right now. Try again in a moment."')
        return 1
    if mismatches:
        print(f"VERDICT  No orders lost, but {len(mismatches)} stock counts are off by {off_by} bags in total.")
        print("         Sales placed during restocking vanished from the stock counts.")
        return 1
    if not during:
        print("VERDICT  Restocking finished before a single order could be placed during it. Stock counts match the ledger.")
        return 0
    print("VERDICT  No orders lost. Stock counts match the ledger.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
