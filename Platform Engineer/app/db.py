# ABOUTME: Builds the psycopg connection pools used by the API and the sync worker.
# ABOUTME: Each process identifies itself to Postgres through application_name.
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import config

API_CONNECTION_OPTIONS = "-c application_name=finance-api -c lock_timeout=5s"
SYNC_CONNECTION_OPTIONS = "-c application_name=finance-sync"


def create_pool(options: str, min_size: int = 1, max_size: int = 8) -> ConnectionPool:
    return ConnectionPool(
        config.DATABASE_URL,
        min_size=min_size,
        max_size=max_size,
        kwargs={"options": options, "row_factory": dict_row},
        open=False,
    )
