-- ABOUTME: Schema for the household finance service.
-- ABOUTME: Applied automatically when the Postgres container initialises an empty data volume.

CREATE TABLE households (
    id          bigserial PRIMARY KEY,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE instruments (
    id           bigserial PRIMARY KEY,
    symbol       text NOT NULL UNIQUE,
    name         text NOT NULL,
    asset_class  text NOT NULL
);

CREATE TABLE prices (
    id             bigserial PRIMARY KEY,
    instrument_id  bigint NOT NULL REFERENCES instruments (id),
    as_of          date NOT NULL,
    close          numeric(18, 4) NOT NULL
);

CREATE TABLE transactions (
    id             bigserial PRIMARY KEY,
    household_id   bigint NOT NULL REFERENCES households (id),
    instrument_id  bigint NOT NULL REFERENCES instruments (id),
    traded_at      date NOT NULL,
    side           text NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity       numeric(18, 6) NOT NULL CHECK (quantity > 0),
    price          numeric(18, 4) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX transactions_household_traded_at_idx ON transactions (household_id, traded_at);

CREATE TABLE holdings (
    id             bigserial PRIMARY KEY,
    household_id   bigint NOT NULL REFERENCES households (id),
    instrument_id  bigint NOT NULL REFERENCES instruments (id),
    quantity       numeric(18, 6) NOT NULL CHECK (quantity > 0),
    cost_basis     numeric(18, 4),
    source         text NOT NULL DEFAULT 'manual',
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX holdings_household_idx ON holdings (household_id);

CREATE TABLE provider_positions (
    household_id   bigint NOT NULL REFERENCES households (id),
    instrument_id  bigint NOT NULL REFERENCES instruments (id),
    quantity       numeric(18, 6) NOT NULL,
    as_of          timestamptz NOT NULL,
    PRIMARY KEY (household_id, instrument_id)
);

CREATE TABLE position_ledger (
    id              bigserial PRIMARY KEY,
    household_id    bigint NOT NULL REFERENCES households (id),
    instrument_id   bigint NOT NULL REFERENCES instruments (id),
    transaction_id  bigint NOT NULL REFERENCES transactions (id),
    as_of           date NOT NULL,
    quantity        numeric(18, 6) NOT NULL,
    market_value    numeric(18, 2) NOT NULL
);

CREATE INDEX position_ledger_household_as_of_idx ON position_ledger (household_id, as_of);

CREATE TABLE valuation_snapshots (
    household_id  bigint PRIMARY KEY REFERENCES households (id),
    total_value   numeric(18, 2) NOT NULL,
    computed_at   timestamptz NOT NULL
);

CREATE TABLE sync_runs (
    id                bigserial PRIMARY KEY,
    household_id      bigint NOT NULL REFERENCES households (id),
    status            text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at        timestamptz NOT NULL DEFAULT now(),
    finished_at       timestamptz,
    positions_synced  integer
);

CREATE INDEX sync_runs_household_started_at_idx ON sync_runs (household_id, started_at DESC);
