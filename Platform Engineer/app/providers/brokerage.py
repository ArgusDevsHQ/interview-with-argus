# ABOUTME: Client for the external brokerage that reports a household's current positions.
# ABOUTME: This build ships a deterministic in-process stand-in for the remote service.
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class ProviderPosition:
    symbol: str
    quantity: Decimal
    as_of: datetime


class BrokerageClient:
    SYMBOLS = ("VTI", "VXUS", "BND", "QQQ", "AAPL", "MSFT")

    def fetch_positions(self, household_id: int) -> list[ProviderPosition]:
        now = datetime.now(timezone.utc)
        day = now.toordinal()
        return [
            ProviderPosition(
                symbol=symbol,
                quantity=Decimal(100 + (household_id * 31 + index * 17 + day) % 40),
                as_of=now,
            )
            for index, symbol in enumerate(self.SYMBOLS)
        ]
