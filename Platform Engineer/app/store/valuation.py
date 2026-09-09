# ABOUTME: Rebuilds a household's position ledger from its transaction history and
# ABOUTME: publishes the resulting total as the household's valuation snapshot.
from collections import defaultdict
from decimal import Decimal

from psycopg import Connection

from app.store.base import Store
from app.store.positions import PositionStore
from app.store.prices import PriceStore


class ValuationStore(Store):
    def __init__(self) -> None:
        self.prices = PriceStore()
        self.positions = PositionStore()

    def recompute(self, conn: Connection, household_id: int) -> Decimal:
        self._ensure_valuation_authority(conn, household_id)
        conn.execute("DELETE FROM position_ledger WHERE household_id = %s", (household_id,))
        transactions = conn.execute(
            """
            SELECT id, instrument_id, traded_at, side, quantity
            FROM transactions
            WHERE household_id = %s
            ORDER BY traded_at, id
            """,
            (household_id,),
        ).fetchall()

        quantities: dict[int, Decimal] = defaultdict(Decimal)
        for tx in transactions:
            delta = tx["quantity"] if tx["side"] == "buy" else -tx["quantity"]
            quantities[tx["instrument_id"]] += delta
            close = self.prices.close_on(conn, tx["instrument_id"], tx["traded_at"]) or Decimal(0)
            conn.execute(
                """
                INSERT INTO position_ledger
                    (household_id, instrument_id, transaction_id, as_of, quantity, market_value)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    household_id,
                    tx["instrument_id"],
                    tx["id"],
                    tx["traded_at"],
                    quantities[tx["instrument_id"]],
                    quantities[tx["instrument_id"]] * close,
                ),
            )

        total = self._current_total(conn, household_id, quantities)
        conn.execute(
            """
            INSERT INTO valuation_snapshots (household_id, total_value, computed_at)
            VALUES (%s, %s, now())
            ON CONFLICT (household_id) DO UPDATE
            SET total_value = EXCLUDED.total_value, computed_at = EXCLUDED.computed_at
            """,
            (household_id, total),
        )
        return total

    def _current_total(
        self, conn: Connection, household_id: int, ledger_quantities: dict[int, Decimal]
    ) -> Decimal:
        total = Decimal(0)
        for instrument_id, quantity in ledger_quantities.items():
            if quantity:
                total += quantity * (self.prices.latest_close(conn, instrument_id) or Decimal(0))
        for position in self.positions.list_for_household(conn, household_id):
            close = self.prices.latest_close(conn, position["instrument_id"]) or Decimal(0)
            total += position["quantity"] * close
        holdings = conn.execute(
            "SELECT instrument_id, quantity FROM holdings WHERE household_id = %s",
            (household_id,),
        ).fetchall()
        for holding in holdings:
            close = self.prices.latest_close(conn, holding["instrument_id"]) or Decimal(0)
            total += holding["quantity"] * close
        return total.quantize(Decimal("0.01"))
