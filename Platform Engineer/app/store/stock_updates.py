# ABOUTME: Records the lifecycle of stock updates and the worker's schedule.
# ABOUTME: A run is requested, then claimed by the worker, then completed or failed.
from datetime import datetime

from psycopg import Connection

RUN_COLUMNS = "id, shop_id, status, requested_at, started_at, finished_at, movements_replayed"


class StockUpdateStore:
    def request(self, conn: Connection, shop_id: int) -> dict:
        return conn.execute(
            f"INSERT INTO stock_updates (shop_id, status) VALUES (%s, 'requested') RETURNING {RUN_COLUMNS}",
            (shop_id,),
        ).fetchone()

    def start(self, conn: Connection, shop_id: int) -> int:
        row = conn.execute(
            "INSERT INTO stock_updates (shop_id, status, started_at) VALUES (%s, 'running', now()) RETURNING id",
            (shop_id,),
        ).fetchone()
        return row["id"]

    def claim_requested(self, conn: Connection) -> dict | None:
        return conn.execute(
            """
            UPDATE stock_updates SET status = 'running', started_at = now()
            WHERE id = (
                SELECT id FROM stock_updates WHERE status = 'requested'
                ORDER BY requested_at, id
                LIMIT 1
                FOR UPDATE
            )
            RETURNING id, shop_id
            """
        ).fetchone()

    def finish(self, conn: Connection, run_id: int, status: str, movements_replayed: int) -> None:
        conn.execute(
            "UPDATE stock_updates SET status = %s, finished_at = clock_timestamp(), movements_replayed = %s WHERE id = %s",
            (status, movements_replayed, run_id),
        )

    def latest(self, conn: Connection, shop_id: int) -> dict | None:
        return conn.execute(
            f"""
            SELECT {RUN_COLUMNS} FROM stock_updates
            WHERE shop_id = %s
            ORDER BY requested_at DESC, id DESC
            LIMIT 1
            """,
            (shop_id,),
        ).fetchone()

    def latest_status(self, conn: Connection, shop_id: int) -> str | None:
        row = self.latest(conn, shop_id)
        return row["status"] if row else None

    def next_run_at(self, conn: Connection, shop_id: int) -> datetime | None:
        row = conn.execute(
            "SELECT next_run_at FROM stock_update_schedule WHERE shop_id = %s", (shop_id,)
        ).fetchone()
        return row["next_run_at"] if row else None

    def schedule(self, conn: Connection, shop_id: int, interval_seconds: int) -> None:
        conn.execute(
            """
            INSERT INTO stock_update_schedule (shop_id, next_run_at)
            VALUES (%s, now() + make_interval(secs => %s))
            ON CONFLICT (shop_id) DO UPDATE SET next_run_at = EXCLUDED.next_run_at
            """,
            (shop_id, interval_seconds),
        )
