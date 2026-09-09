# ABOUTME: Looks up instrument closing prices.
# ABOUTME: Prices are stored per instrument per trading day.
from datetime import date
from decimal import Decimal

from psycopg import Connection


class PriceStore:
    def close_on(self, conn: Connection, instrument_id: int, as_of: date) -> Decimal | None:
        row = conn.execute(
            """
            SELECT close FROM prices
            WHERE instrument_id = %s AND as_of <= %s
            ORDER BY as_of DESC
            LIMIT 1
            """,
            (instrument_id, as_of),
        ).fetchone()
        return row["close"] if row else None

    def latest_close(self, conn: Connection, instrument_id: int) -> Decimal | None:
        row = conn.execute(
            """
            SELECT close FROM prices
            WHERE instrument_id = %s
            ORDER BY as_of DESC
            LIMIT 1
            """,
            (instrument_id,),
        ).fetchone()
        return row["close"] if row else None
