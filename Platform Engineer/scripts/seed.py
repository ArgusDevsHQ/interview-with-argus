# ABOUTME: Populates the database with one shop, its product catalogue, daily shelf scanner
# ABOUTME: counts, and the shop's stock movement history. Re-running replaces the data.
import logging
import random
import string
from datetime import date, datetime, time, timedelta, timezone

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app import config
from app.logs import configure_logging

log = logging.getLogger("roasters.seed")

SHOP_NAME = "Larkspur Roasters, Northgate"
FEATURED = [
    ("HOLLOW-CREEK", "Hollow Creek", "Washed Ethiopia · jasmine, peach", 1650),
    ("NIGHT-FREIGHT", "Night Freight", "Espresso blend · cocoa, fig", 1500),
    ("SUNDAY-PAPER", "Sunday Paper", "Colombia · caramel, red apple", 1400),
    ("LOW-TIDE", "Low Tide", "Decaf Brazil · hazelnut, honey", 1400),
    ("COPPER-KETTLE", "Copper Kettle", "Guatemala · toffee, orange", 1550),
    ("FOG-LINE", "Fog Line", "Kenya · blackcurrant, lime", 1700),
    ("BACKROAD", "Backroad", "Peru · milk chocolate, plum", 1350),
    ("LATE-HARVEST", "Late Harvest", "Natural Ethiopia · strawberry, cream", 1800),
]
PRODUCT_COUNT = 800
COUNT_HISTORY_START = date(2016, 1, 4)
COUNT_HISTORY_END = date(2025, 12, 31)
MOVEMENT_COUNT = 1240
MOVEMENT_HISTORY_DAYS = 365
SEED = 20240901


def trading_days(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def catalogue(rng: random.Random) -> list[tuple[str, str, str, int, bool]]:
    rows = [(sku, name, notes, price, True) for sku, name, notes, price in FEATURED]
    seen = {sku for sku, *_ in rows}
    kinds = ["green lot", "wholesale 1 kg", "filter papers", "mug", "gift box", "cold brew"]
    while len(rows) < PRODUCT_COUNT:
        sku = "".join(rng.choices(string.ascii_uppercase, k=3)) + "-" + str(rng.randint(100, 999))
        if sku in seen:
            continue
        seen.add(sku)
        rows.append((sku, f"{rng.choice(kinds).title()} {sku}", "", rng.randint(400, 6000), False))
    return rows


def count_walk(rng: random.Random, days: list[date]) -> list[int]:
    level = rng.randint(5, 60)
    counts = []
    for _ in days:
        level = max(0, level + rng.randint(-3, 3))
        counts.append(level)
    return counts


def run(conn: Connection) -> dict:
    rng = random.Random(SEED)
    days = trading_days(COUNT_HISTORY_START, COUNT_HISTORY_END)

    conn.execute(
        """
        TRUNCATE stock_update_schedule, stock_updates, orders, stock_checks, cost_layers,
                 stock_levels, stock_movements, scanner_counts, products, shops
        RESTART IDENTITY CASCADE
        """
    )
    shop_id = conn.execute("INSERT INTO shops (name) VALUES (%s) RETURNING id", (SHOP_NAME,)).fetchone()["id"]

    product_ids: list[int] = []
    with conn.cursor() as cur:
        for sku, name, notes, price, featured in catalogue(rng):
            cur.execute(
                "INSERT INTO products (shop_id, sku, name, notes, price_cents, featured) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (shop_id, sku, name, notes, price, featured),
            )
            product_ids.append(cur.fetchone()["id"])

    with conn.cursor() as cur:
        with cur.copy("COPY scanner_counts (product_id, counted_on, quantity) FROM STDIN") as copy:
            for product_id in product_ids:
                for day, count in zip(days, count_walk(rng, days)):
                    copy.write_row((product_id, day, count))
    count_rows = len(product_ids) * len(days)

    moved_products = product_ids[:40]
    on_hand = {product_id: 0 for product_id in moved_products}
    end = datetime.combine(COUNT_HISTORY_END, time(18, 0), tzinfo=timezone.utc)
    stamps = sorted(
        end - timedelta(seconds=rng.randint(0, MOVEMENT_HISTORY_DAYS * 86400)) for _ in range(MOVEMENT_COUNT)
    )
    with conn.cursor() as cur:
        for moved_at in stamps:
            product_id = rng.choice(moved_products)
            if on_hand[product_id] < 8 or rng.random() < 0.12:
                kind, quantity, unit_cost = "received", rng.randint(12, 36), rng.randint(500, 1400)
            else:
                kind, quantity, unit_cost = "sold", -rng.randint(1, min(6, on_hand[product_id])), None
            on_hand[product_id] += quantity
            cur.execute(
                "INSERT INTO stock_movements (shop_id, product_id, moved_at, kind, quantity, unit_cost_cents) VALUES (%s, %s, %s, %s, %s, %s)",
                (shop_id, product_id, moved_at, kind, quantity, unit_cost),
            )
        cur.executemany(
            "INSERT INTO stock_levels (product_id, on_hand, value_cents, computed_at) VALUES (%s, %s, 0, now())",
            [(product_id, quantity) for product_id, quantity in on_hand.items()],
        )

    return {
        "shop_id": shop_id,
        "products": len(product_ids),
        "scanner_counts": count_rows,
        "movements": MOVEMENT_COUNT,
    }


def main() -> None:
    configure_logging()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        summary = run(conn)
        conn.commit()
    log.info("seed_completed", extra=summary)


if __name__ == "__main__":
    main()
