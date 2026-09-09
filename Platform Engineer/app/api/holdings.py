# ABOUTME: HTTP routes for manually entered investment holdings.
# ABOUTME: Validates request bodies and delegates to HoldingService.
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.holdings import HoldingService, UnknownHousehold, UnknownInstrument

router = APIRouter(prefix="/api/v1/holdings", tags=["holdings"])


class HoldingCreate(BaseModel):
    household_id: int
    symbol: str = Field(min_length=1, max_length=16)
    quantity: Decimal = Field(gt=0)
    cost_basis: Decimal | None = Field(default=None, ge=0)


class HoldingResponse(BaseModel):
    id: int
    household_id: int
    symbol: str
    quantity: Decimal
    cost_basis: Decimal | None
    source: str
    created_at: datetime


@router.post("", status_code=status.HTTP_201_CREATED, response_model=HoldingResponse)
def create_holding(payload: HoldingCreate, request: Request) -> dict:
    service = HoldingService(request.app.state.pool)
    try:
        return service.create(
            payload.household_id, payload.symbol, payload.quantity, payload.cost_basis
        )
    except UnknownHousehold:
        raise HTTPException(status_code=404, detail="household not found")
    except UnknownInstrument:
        raise HTTPException(status_code=404, detail="symbol not found")
