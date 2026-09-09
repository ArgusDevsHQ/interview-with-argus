# ABOUTME: HTTP routes for placing customer orders.
# ABOUTME: Validates request bodies and delegates to OrderService.
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.orders import OrderService, OutOfStock, UnknownProduct

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


class OrderCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0, le=20)
    customer: str = Field(default="web", min_length=1, max_length=40)


class OrderResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    customer: str
    on_hand: int
    created_at: datetime


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrderResponse)
def place_order(payload: OrderCreate, request: Request) -> dict:
    service = OrderService(request.app.state.pool)
    try:
        return service.place(payload.product_id, payload.quantity, payload.customer)
    except UnknownProduct:
        raise HTTPException(status_code=404, detail="product not found")
    except OutOfStock:
        raise HTTPException(status_code=409, detail="not enough stock")
