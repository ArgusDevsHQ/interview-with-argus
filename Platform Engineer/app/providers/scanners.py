# ABOUTME: Client for the shelf scanner service that reports today's counted quantities.
# ABOUTME: This build ships a deterministic in-process stand-in for the remote service.
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ScannerReading:
    product_id: int
    counted_on: date
    quantity: int


class ScannerFeed:
    def fetch_today(self, shop_id: int, product_ids: list[int]) -> list[ScannerReading]:
        today = date.today()
        return [
            ScannerReading(product_id, today, (shop_id * 7 + product_id * 13 + today.toordinal()) % 40 + 5)
            for product_id in product_ids
        ]
