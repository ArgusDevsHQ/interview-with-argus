# Platform Engineer diagnostic

A small household finance API. Manual holdings come in through
`POST /api/v1/holdings`. A background worker syncs positions from the brokerage
provider and republishes each household's valuation.

## The report

From support, verbatim:

> Adding a holding by hand fails a few times an hour with a 503, "Things are
> busy right now. Try again in a moment." It seems to line up with the position
> sync running. Retrying a minute or two later works. Nothing changed on our side.

## Start the stack

Requires Docker with Compose v2.

```sh
docker compose up -d --build
docker compose run --rm api python -m scripts.seed
```

- API: http://localhost:8000 (`/health`, `/docs`).
- Postgres: `localhost:5433`, user, password, and database are all `finance`.
  `docker compose exec db psql -U finance` also works.
- If a port is taken, set `API_PORT` or `DB_PORT` in your environment.
- Logs: `docker compose logs -f api sync`.
- The sync worker runs at startup and every 10 minutes. Trigger one by hand:
  `docker compose run --rm sync python -m app.sync --once`.
- Source is bind-mounted into the containers. After editing:
  `docker compose restart api sync`.

Example request:

```sh
curl -s -X POST localhost:8000/api/v1/holdings \
  -H 'content-type: application/json' \
  -d '{"household_id": 1, "symbol": "VTI", "quantity": "10", "cost_basis": "2500"}'
```

## Run the test

```sh
docker compose run --rm api pytest
```

`tests/test_sync_and_holdings.py` fails. Make it pass without changing the test.

## Deliverables

Put everything in a `FINDINGS.md` next to this file, commit your fix on a
branch, and send us the branch.

1. Proof of what blocked the write, captured during a live reproduction: the
   backend PID that was holding it, the identity of what it held, and the
   measured duration of the critical section.
2. A before/after Mermaid sequence diagram of the write path and the sync.
3. Measured numbers, before and after your fix: how long the write waited, the
   critical-section duration, and write-endpoint p50/p95 while a sync is running.
4. A short write-up: what you tried that turned out to be wrong, and what breaks
   if the sync runs for 10 minutes.

Budget 2 to 4 hours. AI assistance is fine.
