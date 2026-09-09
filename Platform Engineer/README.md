# Platform Engineer diagnostic

Larkspur Roasters sells coffee online. Customers place orders through the
storefront. Every five minutes a background worker pulls the shelf scanner
counts and rebuilds the shop's stock levels.

## The report

From support, verbatim:

> Customers get a 503, "Things are busy right now. Try again in a moment." It
> happens a few times an hour and seems to line up with the stock update.
> Trying again a minute later works. Nothing changed on our side.

## Start the stack

Requires Docker with Compose v2.

```sh
docker compose up -d --build
docker compose run --rm api python -m scripts.seed
```

- API at http://localhost:8000, docs at `/docs`.
- Postgres: `localhost:5433`, user, password, and database are all `roasters`.
  `docker compose exec db psql -U roasters` also works.
- If a port is taken, set `API_PORT` or `DB_PORT` in your environment.
- Logs: `docker compose logs -f api worker`.
- The stock update runs at startup and every 5 minutes. Queue one now with
  `curl -X POST localhost:8000/api/v1/stock-update`.
- Source is bind-mounted into the containers. After editing:
  `docker compose restart api worker`.

## Run the test

```sh
docker compose run --rm api pytest
```

`tests/test_stock_update_and_orders.py` fails. Make it pass without changing
the test.

## Run the simulation

```sh
docker compose run --rm api python -m scripts.simulate
```

It places real orders while the shop restocks, then checks the stock counts
against the ledger, and prints what a shop owner would read at the end of the
day. Run it before and after your fix. It takes a couple of minutes.

## Deliverables

Put everything in a `FINDINGS.md` next to this file and commit your fix on a
branch. To send it to us, either push the branch to a fork and open a pull
request there, or email the patch (`git format-patch main`) to
aman@getargus.tech.

1. Evidence of what blocked the order, captured live rather than reasoned
   about, and the measured duration of whatever was blocking it.
2. A before/after Mermaid sequence diagram of the order path and the stock
   update.
3. Measured numbers, before and after your fix: how long the order waited, how
   long the blocking operation held things up, and order-endpoint p50/p95
   while an update is running.
4. A short write-up: what you tried that turned out to be wrong, and what breaks
   if the stock update runs for 10 minutes.

If you run out of time, tell us what you would have done next.

Budget 2 to 4 hours. You may add dependencies; say why.

## On AI assistance

Using AI for the code and the investigation is fine.

`FINDINGS.md` is different. It is the deliverable we read, and it is the only
part of this exercise that tells us how you think. A submission without it is
disqualified. A `FINDINGS.md` that reads as generated will be treated the same
way. Write it yourself: your evidence, your numbers, your wrong turns, in your
own words. We will ask you to walk us through it.
