# ABOUTME: Pulls today's shelf scanner counts for a shop and rebuilds its stock levels.
# ABOUTME: Used by the background worker and by tests that drive an update directly.
import logging
import time
from dataclasses import dataclass

from psycopg import Connection

from app.providers.scanners import ScannerFeed
from app.store.products import ProductStore
from app.store.scanner_counts import ScannerCountStore
from app.store.stock import StockStore
from app.store.stock_updates import StockUpdateStore

log = logging.getLogger("roasters.stock_update")


@dataclass(frozen=True)
class StockUpdateResult:
    run_id: int
    movements_replayed: int
    duration_ms: int


def run_stock_update(
    conn: Connection, shop_id: int, run_id: int | None = None, feed: ScannerFeed | None = None
) -> StockUpdateResult:
    feed = feed or ScannerFeed()
    runs = StockUpdateStore()
    products = ProductStore()
    scanner_counts = ScannerCountStore()
    stock = StockStore()

    if run_id is None:
        with conn.transaction():
            run_id = runs.start(conn, shop_id)
    started = time.monotonic()
    log.info("stock_update_started", extra={"shop_id": shop_id, "run_id": run_id})

    try:
        with conn.transaction():
            product_ids = products.list_ids(conn, shop_id)
            readings = feed.fetch_today(shop_id, product_ids)
            scanner_counts.insert_many(
                conn, [(r.product_id, r.counted_on, r.quantity) for r in readings]
            )
            replayed = stock.rebuild(conn, shop_id)
            runs.finish(conn, run_id, "completed", replayed)
    except Exception as exc:
        with conn.transaction():
            runs.finish(conn, run_id, "failed", 0)
        log.error(
            "stock_update_failed",
            extra={"shop_id": shop_id, "run_id": run_id, "sqlstate": getattr(exc, "sqlstate", None)},
        )
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "stock_update_completed",
        extra={"shop_id": shop_id, "run_id": run_id, "movements": replayed, "duration_ms": duration_ms},
    )
    return StockUpdateResult(run_id, replayed, duration_ms)
