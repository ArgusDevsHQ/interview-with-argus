# ABOUTME: Records the lifecycle of provider sync runs.
# ABOUTME: One row per household per run, with its outcome and position count.
from psycopg import Connection


class SyncRunStore:
    def start(self, conn: Connection, household_id: int) -> int:
        row = conn.execute(
            "INSERT INTO sync_runs (household_id, status) VALUES (%s, 'running') RETURNING id",
            (household_id,),
        ).fetchone()
        return row["id"]

    def finish(self, conn: Connection, run_id: int, status: str, positions_synced: int) -> None:
        conn.execute(
            """
            UPDATE sync_runs
            SET status = %s, finished_at = now(), positions_synced = %s
            WHERE id = %s
            """,
            (status, positions_synced, run_id),
        )

    def latest_status(self, conn: Connection, household_id: int) -> str | None:
        row = conn.execute(
            """
            SELECT status FROM sync_runs
            WHERE household_id = %s
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """,
            (household_id,),
        ).fetchone()
        return row["status"] if row else None
