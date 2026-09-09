# ABOUTME: HTTP route that compares every product's stock count with its movement ledger.
# ABOUTME: A product whose count disagrees with the sum of its movements is reported as a mismatch.
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.store.products import ProductStore

router = APIRouter(prefix="/api/v1/stock-check", tags=["stock check"])

SHOP_ID = 1


class Mismatch(BaseModel):
    product_id: int
    name: str
    on_hand: int
    ledger: int


class StockCheck(BaseModel):
    products_checked: int
    mismatches: list[Mismatch]


@router.get("", response_model=StockCheck)
def stock_check(request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        checked, mismatches = ProductStore().ledger_mismatches(conn, SHOP_ID)
    return {"products_checked": checked, "mismatches": mismatches}
