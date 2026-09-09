# ABOUTME: HTTP routes for reading household-level derived data.
# ABOUTME: Exposes the most recently published valuation snapshot.
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/households", tags=["households"])


class ValuationResponse(BaseModel):
    household_id: int
    total_value: Decimal
    computed_at: datetime


@router.get("/{household_id}/valuation", response_model=ValuationResponse)
def get_valuation(household_id: int, request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        row = conn.execute(
            """
            SELECT household_id, total_value, computed_at
            FROM valuation_snapshots
            WHERE household_id = %s
            """,
            (household_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="no valuation published for household")
    return row
