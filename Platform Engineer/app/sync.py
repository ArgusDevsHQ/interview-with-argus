# ABOUTME: Background worker that syncs provider positions for every household.
# ABOUTME: Runs once at startup and then on a fixed interval; --once exits after one pass.
import logging
import sys
import time

from app import config, db
from app.logs import configure_logging
from app.services.sync import sync_household
from app.store.households import HouseholdStore

log = logging.getLogger("finance.sync")


def run_all(pool) -> None:
    with pool.connection() as conn:
        household_ids = HouseholdStore().list_ids(conn)
    log.info("sync_pass_started", extra={"households": len(household_ids)})
    for household_id in household_ids:
        with pool.connection() as conn:
            try:
                sync_household(conn, household_id)
            except Exception:
                log.warning("sync_skipped", extra={"household_id": household_id})


def main(argv: list[str]) -> None:
    configure_logging()
    pool = db.create_pool(db.SYNC_CONNECTION_OPTIONS, min_size=1, max_size=2)
    pool.open(wait=True)
    once = "--once" in argv
    while True:
        run_all(pool)
        if once:
            break
        time.sleep(config.SYNC_INTERVAL_SECONDS)
    pool.close()


if __name__ == "__main__":
    main(sys.argv[1:])
