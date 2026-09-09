# ABOUTME: HTTP routes for the storefront's product listing.
# ABOUTME: Returns featured products with their current stock level.
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.store.products import ProductStore

router = APIRouter(prefix="/api/v1/products", tags=["products"])

SHOP_ID = 1


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    notes: str
    price_cents: int
    on_hand: int


@router.get("", response_model=list[ProductResponse])
def list_products(request: Request) -> list[dict]:
    with request.app.state.pool.connection() as conn:
        return ProductStore().list_featured(conn, SHOP_ID)
