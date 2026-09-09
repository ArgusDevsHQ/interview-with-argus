# ABOUTME: Background worker that runs stock updates for every shop.
# ABOUTME: Runs on a fixed interval and picks up requested runs between passes; --once exits after one pass.
import logging
import sys
import time

from app import config, db
from app.logs import configure_logging
from app.services.stock_update import run_stock_update
from app.store.shops import ShopStore
from app.store.stock_updates import StockUpdateStore

log = logging.getLogger("roasters.worker")


def run_scheduled(pool) -> None:
    runs = StockUpdateStore()
    with pool.connection() as conn:
        shop_ids = ShopStore().list_ids(conn)
    log.info("stock_update_pass_started", extra={"shops": len(shop_ids)})
    for shop_id in shop_ids:
        with pool.connection() as conn:
            with conn.transaction():
                runs.schedule(conn, shop_id, config.STOCK_UPDATE_INTERVAL_SECONDS)
            try:
                run_stock_update(conn, shop_id)
            except Exception:
                log.warning("stock_update_skipped", extra={"shop_id": shop_id})


def run_requested(pool) -> None:
    runs = StockUpdateStore()
    while True:
        with pool.connection() as conn:
            with conn.transaction():
                claimed = runs.claim_requested(conn)
            if claimed is None:
                return
            try:
                run_stock_update(conn, claimed["shop_id"], run_id=claimed["id"])
            except Exception:
                log.warning("stock_update_skipped", extra={"shop_id": claimed["shop_id"]})


def main(argv: list[str]) -> None:
    configure_logging()
    pool = db.create_pool(db.WORKER_CONNECTION_OPTIONS, min_size=1, max_size=2)
    pool.open(wait=True)
    once = "--once" in argv
    next_pass = time.monotonic()
    while True:
        if time.monotonic() >= next_pass:
            run_scheduled(pool)
            next_pass += config.STOCK_UPDATE_INTERVAL_SECONDS
            if once:
                break
        run_requested(pool)
        time.sleep(config.STOCK_UPDATE_POLL_SECONDS)
    pool.close()


if __name__ == "__main__":
    main(sys.argv[1:])
