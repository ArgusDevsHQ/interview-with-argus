# ABOUTME: FastAPI application for the household finance API.
# ABOUTME: Wires routers, the connection pool, correlation ids, and error responses.
import logging
import uuid
from contextlib import asynccontextmanager

import psycopg
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import config, db
from app.api import holdings, households
from app.logs import configure_logging, correlation_id

log = logging.getLogger("finance.api")

BUSY_MESSAGE = "Things are busy right now. Try again in a moment."


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = db.create_pool(db.API_CONNECTION_OPTIONS, min_size=2, max_size=8)
    app.state.pool.open(wait=True)
    try:
        yield
    finally:
        app.state.pool.close()


app = FastAPI(title="Household Finance API", lifespan=lifespan)
app.include_router(holdings.router)
app.include_router(households.router)


@app.middleware("http")
async def attach_correlation_id(request: Request, call_next):
    current = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
    token = correlation_id.set(current)
    try:
        response = await call_next(request)
    finally:
        correlation_id.reset(token)
    response.headers["X-Correlation-ID"] = current
    return response


@app.exception_handler(psycopg.OperationalError)
async def database_unavailable(request: Request, exc: psycopg.OperationalError):
    log.error(
        "request_failed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": 503,
            "sqlstate": exc.sqlstate,
        },
    )
    return JSONResponse(
        status_code=503,
        content={"detail": BUSY_MESSAGE, "correlation_id": correlation_id.get()},
    )


@app.get("/health")
def health(request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


def main() -> None:
    configure_logging()
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, log_config=None)


if __name__ == "__main__":
    main()
