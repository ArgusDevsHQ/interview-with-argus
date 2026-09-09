# ABOUTME: Populates the database with one household, an instrument universe, daily price
# ABOUTME: history, and the household's transaction history. Re-running replaces the data.
import logging
import random
import string
from datetime import date, timedelta
from decimal import Decimal

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app import config
from app.logs import configure_logging

log = logging.getLogger("finance.seed")

HOUSEHOLD_NAME = "Okafor household"
NAMED_INSTRUMENTS = [
    ("VTI", "Total Stock Market ETF", "equity"),
    ("VXUS", "Total International Stock ETF", "equity"),
    ("BND", "Total Bond Market ETF", "fixed_income"),
    ("QQQ", "Nasdaq 100 ETF", "equity"),
    ("AAPL", "Apple Inc.", "equity"),
    ("MSFT", "Microsoft Corporation", "equity"),
]
INSTRUMENT_COUNT = 800
HISTORY_START = date(2016, 1, 4)
HISTORY_END = date(2025, 12, 31)
TRANSACTION_COUNT = 1200
TRADED_INSTRUMENTS = 40
MANUAL_HOLDINGS = [("VTI", Decimal("25"), Decimal("4100.00")), ("BND", Decimal("40"), Decimal("2900.00"))]
SEED = 20240901


def trading_days(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def instrument_rows(rng: random.Random) -> list[tuple[str, str, str]]:
    rows = list(NAMED_INSTRUMENTS)
    seen = {symbol for symbol, _, _ in rows}
    while len(rows) < INSTRUMENT_COUNT:
        symbol = "".join(rng.choices(string.ascii_uppercase, k=4))
        if symbol in seen:
            continue
        seen.add(symbol)
        asset_class = rng.choice(["equity", "equity", "fixed_income", "commodity"])
        rows.append((symbol, f"{symbol} Fund", asset_class))
    return rows


def price_walk(rng: random.Random, days: list[date]) -> list[Decimal]:
    level = rng.uniform(15, 400)
    closes = []
    for _ in days:
        level *= 1 + rng.gauss(0.0003, 0.012)
        level = max(level, 0.5)
        closes.append(Decimal(f"{level:.4f}"))
    return closes


def run(conn: Connection) -> dict:
    rng = random.Random(SEED)
    days = trading_days(HISTORY_START, HISTORY_END)

    conn.execute(
        """
        TRUNCATE sync_runs, valuation_snapshots, position_ledger, provider_positions,
                 holdings, transactions, prices, instruments, households
        RESTART IDENTITY CASCADE
        """
    )
    household_id = conn.execute(
        "INSERT INTO households (name) VALUES (%s) RETURNING id", (HOUSEHOLD_NAME,)
    ).fetchone()["id"]

    instrument_ids: dict[str, int] = {}
    with conn.cursor() as cur:
        for symbol, name, asset_class in instrument_rows(rng):
            cur.execute(
                "INSERT INTO instruments (symbol, name, asset_class) VALUES (%s, %s, %s) RETURNING id",
                (symbol, name, asset_class),
            )
            instrument_ids[symbol] = cur.fetchone()["id"]

    closes_by_symbol: dict[str, list[Decimal]] = {}
    with conn.cursor() as cur:
        with cur.copy("COPY prices (instrument_id, as_of, close) FROM STDIN") as copy:
            for symbol, instrument_id in instrument_ids.items():
                closes = price_walk(rng, days)
                closes_by_symbol[symbol] = closes
                for day, close in zip(days, closes):
                    copy.write_row((instrument_id, day, close))
    price_count = len(instrument_ids) * len(days)

    traded_symbols = list(instrument_ids)[:TRADED_INSTRUMENTS]
    with conn.cursor() as cur:
        for _ in range(TRANSACTION_COUNT):
            symbol = rng.choice(traded_symbols)
            day_index = rng.randrange(len(days))
            side = "buy" if rng.random() < 0.7 else "sell"
            quantity = Decimal(rng.randint(1, 50))
            cur.execute(
                """
                INSERT INTO transactions (household_id, instrument_id, traded_at, side, quantity, price)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    household_id,
                    instrument_ids[symbol],
                    days[day_index],
                    side,
                    quantity,
                    closes_by_symbol[symbol][day_index],
                ),
            )
        for symbol, quantity, cost_basis in MANUAL_HOLDINGS:
            cur.execute(
                """
                INSERT INTO holdings (household_id, instrument_id, quantity, cost_basis, source)
                VALUES (%s, %s, %s, %s, 'manual')
                """,
                (household_id, instrument_ids[symbol], quantity, cost_basis),
            )

    return {
        "household_id": household_id,
        "instruments": len(instrument_ids),
        "prices": price_count,
        "transactions": TRANSACTION_COUNT,
        "holdings": len(MANUAL_HOLDINGS),
    }


def main() -> None:
    configure_logging()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        summary = run(conn)
        conn.commit()
    log.info("seed_completed", extra=summary)


if __name__ == "__main__":
    main()
