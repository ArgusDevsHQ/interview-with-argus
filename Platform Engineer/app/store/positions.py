# ABOUTME: Persists the positions reported by the external brokerage provider.
# ABOUTME: Each sync replaces the household's provider positions wholesale.
from datetime import datetime
from decimal import Decimal

from psycopg import Connection


class PositionStore:
    def replace(
        self,
        conn: Connection,
        household_id: int,
        positions: list[tuple[int, Decimal, datetime]],
    ) -> None:
        conn.execute("DELETE FROM provider_positions WHERE household_id = %s", (household_id,))
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO provider_positions (household_id, instrument_id, quantity, as_of)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (household_id, instrument_id, quantity, as_of)
                    for instrument_id, quantity, as_of in positions
                ],
            )

    def list_for_household(self, conn: Connection, household_id: int) -> list[dict]:
        return conn.execute(
            "SELECT instrument_id, quantity FROM provider_positions WHERE household_id = %s",
            (household_id,),
        ).fetchall()
