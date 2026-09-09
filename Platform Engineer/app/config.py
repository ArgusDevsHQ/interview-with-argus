# ABOUTME: Reads runtime configuration from environment variables.
# ABOUTME: Defaults match the docker compose stack in this directory.
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://finance:finance@localhost:5433/finance"
)
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "600"))
PORT = int(os.environ.get("PORT", "8000"))
