# ABOUTME: HTTP routes for the shop's stock update: current run, next scheduled run, request one.
# ABOUTME: Requests are queued for the background worker; the API never runs an update itself.
from datetime import datetime

from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from app import config
from app.store.stock_updates import StockUpdateStore

router = APIRouter(prefix="/api/v1/stock-update", tags=["stock update"])

SHOP_ID = 1


class StockUpdateRun(BaseModel):
    id: int
    status: str
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    movements_replayed: int | None


class StockUpdateStatus(BaseModel):
    latest: StockUpdateRun | None
    next_run_at: datetime | None
    interval_seconds: int
    server_time: datetime


@router.get("", response_model=StockUpdateStatus)
def stock_update_status(request: Request) -> dict:
    runs = StockUpdateStore()
    with request.app.state.pool.connection() as conn:
        latest = runs.latest(conn, SHOP_ID)
        next_run_at = runs.next_run_at(conn, SHOP_ID)
        server_time = conn.execute("SELECT now() AS now").fetchone()["now"]
    return {
        "latest": latest,
        "next_run_at": next_run_at,
        "interval_seconds": config.STOCK_UPDATE_INTERVAL_SECONDS,
        "server_time": server_time,
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=StockUpdateRun)
def request_stock_update(request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        with conn.transaction():
            return StockUpdateStore().request(conn, SHOP_ID)
