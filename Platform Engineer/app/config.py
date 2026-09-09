# ABOUTME: Reads runtime configuration from environment variables.
# ABOUTME: Defaults match the docker compose stack in this directory.
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://roasters:roasters@localhost:5433/roasters"
)
STOCK_UPDATE_INTERVAL_SECONDS = int(os.environ.get("STOCK_UPDATE_INTERVAL_SECONDS", "300"))
PORT = int(os.environ.get("PORT", "8000"))
STOCK_UPDATE_POLL_SECONDS = float(os.environ.get("STOCK_UPDATE_POLL_SECONDS", "2"))
