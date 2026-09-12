# Platform Engineer diagnostic

Larkspur Roasters sells coffee online. Every delivery, sale, and inventory
correction is recorded in a movement ledger. This history is the source of
truth for the shop's recorded inventory. Orders check a saved stock count and
reduce it immediately when a sale succeeds.

Every five minutes a background worker rebuilds those saved counts from the
ledger, repairing any drift, and recalculates the cost of the remaining stock
using the oldest deliveries first. It also pulls shelf scanner readings and
records comparisons with the ledger. Scanner readings are evidence for
investigating discrepancies; they do not overwrite inventory automatically.
An approved correction would be another ledger entry.

The rebuild must preserve the ledger and include sales made while it runs.
Customers should be able to keep ordering during an update.

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
the tests. It coordinates an order with an active rebuild rather than assuming
the rebuild is still running after a fixed delay. The rebuild is free to
continue as soon as the order proceeds or reaches a conflicting database lock.

`tests/test_stock_reconciliation.py` also checks that a rebuild repairs an
incorrect saved count and inventory cost using the ledger, without changing
the movement history or treating a scanner discrepancy as a stock correction.

Choose an approach you can support with evidence. Query optimizations,
changes to how concurrent operations coordinate, or a combination are all
valid approaches if they satisfy the behavior above. Explain their limits.

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
aman@getargus.tech. DO NOT OPEN A PR HERE!

1. Evidence of what blocked the order, captured live rather than reasoned
   about, and the measured duration of whatever was blocking it.
2. A before/after Mermaid sequence diagram of the order path and the stock
   update.
3. Measured numbers, before and after your fix: how long the order waited, how
   long the blocking operation held things up, and order-endpoint p50/p95
   while an update is running.
4. A short write-up: what you tried that turned out to be wrong, and what breaks
   if the stock update runs for 10 minutes.

Write up any further problems you discover and how you would address them.
If you have time or curiosity to explore further, you're welcome to implement
those improvements too. This is optional. Include what you changed and how you
checked that it worked in `FINDINGS.md`.

If you run out of time, tell us what you would have done next.

Budget 2 to 4 hours. You may add dependencies; say why.

## On AI assistance

AI assistance is welcome for the code and investigation. We're interested in
the evidence behind your diagnosis, how you verify your changes, and your
understanding of their limitations. Briefly disclose what assistance you used
and what you personally checked.

Write `FINDINGS.md` yourself: your evidence, your numbers, your wrong turns,
in your own words. Do not delegate its authorship to an AI tool. A submission
without it is incomplete. Be prepared to explain the reasoning and verify
the claims in everything you submit.
