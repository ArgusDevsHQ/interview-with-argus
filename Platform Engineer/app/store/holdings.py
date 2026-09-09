# ABOUTME: Persists manually entered holdings and folds them into the household valuation.
# ABOUTME: A manual holding contributes quantity times latest close to the snapshot total.
from decimal import Decimal

from psycopg import Connection

from app.store.base import Store
from app.store.prices import PriceStore


class HoldingStore(Store):
    def __init__(self) -> None:
        self.prices = PriceStore()

    def insert(
        self,
        conn: Connection,
        household_id: int,
        instrument_id: int,
        quantity: Decimal,
        cost_basis: Decimal | None,
    ) -> dict:
        self._ensure_valuation_authority(conn, household_id)
        holding = conn.execute(
            """
            INSERT INTO holdings (household_id, instrument_id, quantity, cost_basis, source)
            VALUES (%s, %s, %s, %s, 'manual')
            RETURNING id, household_id, instrument_id, quantity, cost_basis, source, created_at
            """,
            (household_id, instrument_id, quantity, cost_basis),
        ).fetchone()
        self._add_to_snapshot(conn, household_id, instrument_id, quantity)
        return holding

    def _add_to_snapshot(
        self, conn: Connection, household_id: int, instrument_id: int, quantity: Decimal
    ) -> None:
        close = self.prices.latest_close(conn, instrument_id) or Decimal(0)
        conn.execute(
            """
            INSERT INTO valuation_snapshots (household_id, total_value, computed_at)
            VALUES (%s, %s, now())
            ON CONFLICT (household_id) DO UPDATE
            SET total_value = valuation_snapshots.total_value + EXCLUDED.total_value,
                computed_at = now()
            """,
            (household_id, quantity * close),
        )
