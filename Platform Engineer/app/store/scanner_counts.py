# ABOUTME: Reads the counts reported by the shelf scanners.
# ABOUTME: One count per product per day; the latest count on or before a date is the reference.
from datetime import date

from psycopg import Connection


class ScannerCountStore:
    def count_on(self, conn: Connection, product_id: int, counted_on: date) -> int | None:
        row = conn.execute(
            """
            SELECT quantity FROM scanner_counts
            WHERE product_id = %s AND counted_on <= %s
            ORDER BY counted_on DESC
            LIMIT 1
            """,
            (product_id, counted_on),
        ).fetchone()
        return row["quantity"] if row else None

    def insert_many(self, conn: Connection, counts: list[tuple[int, date, int]]) -> None:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO scanner_counts (product_id, counted_on, quantity) VALUES (%s, %s, %s)",
                counts,
            )
