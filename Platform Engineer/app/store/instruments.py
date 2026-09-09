# ABOUTME: Reads instrument rows and resolves ticker symbols to instrument ids.
# ABOUTME: Symbols are the identifier clients and the provider use.
from psycopg import Connection


class InstrumentStore:
    def get_by_symbol(self, conn: Connection, symbol: str) -> dict | None:
        return conn.execute(
            "SELECT id, symbol, name, asset_class FROM instruments WHERE symbol = %s",
            (symbol.upper(),),
        ).fetchone()

    def ids_by_symbol(self, conn: Connection, symbols: list[str]) -> dict[str, int]:
        rows = conn.execute(
            "SELECT id, symbol FROM instruments WHERE symbol = ANY(%s)", (symbols,)
        ).fetchall()
        return {row["symbol"]: row["id"] for row in rows}
