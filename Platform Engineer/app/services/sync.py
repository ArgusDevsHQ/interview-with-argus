# ABOUTME: Synchronises a household's provider positions and refreshes its valuation.
# ABOUTME: Used by the background worker and by tests that drive a sync directly.
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

from psycopg import Connection

from app.providers.brokerage import BrokerageClient
from app.store.instruments import InstrumentStore
from app.store.positions import PositionStore
from app.store.sync_runs import SyncRunStore
from app.store.valuation import ValuationStore

log = logging.getLogger("finance.sync")


@dataclass(frozen=True)
class SyncResult:
    run_id: int
    positions_synced: int
    total_value: Decimal
    duration_ms: int


def sync_household(
    conn: Connection, household_id: int, provider: BrokerageClient | None = None
) -> SyncResult:
    provider = provider or BrokerageClient()
    runs = SyncRunStore()
    instruments = InstrumentStore()
    positions = PositionStore()
    valuation = ValuationStore()

    with conn.transaction():
        run_id = runs.start(conn, household_id)
    started = time.monotonic()
    log.info("sync_started", extra={"household_id": household_id, "run_id": run_id})

    try:
        with conn.transaction():
            reported = provider.fetch_positions(household_id)
            ids = instruments.ids_by_symbol(conn, [p.symbol for p in reported])
            mapped = [
                (ids[p.symbol], p.quantity, p.as_of) for p in reported if p.symbol in ids
            ]
            positions.replace(conn, household_id, mapped)
            total = valuation.recompute(conn, household_id)
            runs.finish(conn, run_id, "completed", len(mapped))
    except Exception as exc:
        with conn.transaction():
            runs.finish(conn, run_id, "failed", 0)
        log.error(
            "sync_failed",
            extra={
                "household_id": household_id,
                "run_id": run_id,
                "sqlstate": getattr(exc, "sqlstate", None),
            },
        )
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    log.info(
        "sync_completed",
        extra={
            "household_id": household_id,
            "run_id": run_id,
            "positions": len(mapped),
            "total_value": str(total),
            "duration_ms": duration_ms,
        },
    )
    return SyncResult(run_id, len(mapped), total, duration_ms)
