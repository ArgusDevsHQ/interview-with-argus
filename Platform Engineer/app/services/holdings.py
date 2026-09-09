# ABOUTME: Creates manually entered holdings for a household.
# ABOUTME: Resolves the request's symbol and household before writing through the store.
from decimal import Decimal

from psycopg_pool import ConnectionPool

from app.store.holdings import HoldingStore
from app.store.households import HouseholdStore
from app.store.instruments import InstrumentStore


class UnknownHousehold(Exception):
    pass


class UnknownInstrument(Exception):
    pass


class HoldingService:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool
        self.households = HouseholdStore()
        self.instruments = InstrumentStore()
        self.holdings = HoldingStore()

    def create(
        self, household_id: int, symbol: str, quantity: Decimal, cost_basis: Decimal | None
    ) -> dict:
        with self.pool.connection() as conn:
            with conn.transaction():
                if self.households.get(conn, household_id) is None:
                    raise UnknownHousehold(household_id)
                instrument = self.instruments.get_by_symbol(conn, symbol)
                if instrument is None:
                    raise UnknownInstrument(symbol)
                holding = self.holdings.insert(
                    conn, household_id, instrument["id"], quantity, cost_basis
                )
                return {**holding, "symbol": instrument["symbol"]}
