-- ABOUTME: Schema for the Larkspur Roasters storefront.
-- ABOUTME: Applied automatically when the Postgres container initialises an empty data volume.

CREATE TABLE shops (
    id    bigserial PRIMARY KEY,
    name  text NOT NULL
);

CREATE TABLE products (
    id           bigserial PRIMARY KEY,
    shop_id      bigint NOT NULL REFERENCES shops (id),
    sku          text NOT NULL UNIQUE,
    name         text NOT NULL,
    notes        text NOT NULL DEFAULT '',
    price_cents  integer NOT NULL,
    featured     boolean NOT NULL DEFAULT false
);

CREATE INDEX products_shop_featured_idx ON products (shop_id, featured);

CREATE TABLE scanner_counts (
    id          bigserial PRIMARY KEY,
    product_id  bigint NOT NULL REFERENCES products (id),
    counted_on  date NOT NULL,
    quantity    integer NOT NULL
);

CREATE TABLE stock_movements (
    id               bigserial PRIMARY KEY,
    shop_id          bigint NOT NULL REFERENCES shops (id),
    product_id       bigint NOT NULL REFERENCES products (id),
    moved_at         timestamptz NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('received', 'sold', 'adjusted')),
    quantity         integer NOT NULL,
    unit_cost_cents  integer,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX stock_movements_shop_moved_at_idx ON stock_movements (shop_id, moved_at);

CREATE TABLE stock_levels (
    product_id   bigint PRIMARY KEY REFERENCES products (id),
    on_hand      integer NOT NULL,
    value_cents  bigint NOT NULL,
    computed_at  timestamptz NOT NULL
);

CREATE TABLE cost_layers (
    id                  bigserial PRIMARY KEY,
    product_id          bigint NOT NULL REFERENCES products (id),
    movement_id         bigint NOT NULL REFERENCES stock_movements (id),
    quantity_remaining  integer NOT NULL,
    unit_cost_cents     integer NOT NULL
);

CREATE INDEX cost_layers_product_idx ON cost_layers (product_id);

CREATE TABLE stock_checks (
    id                bigserial PRIMARY KEY,
    shop_id           bigint NOT NULL REFERENCES shops (id),
    movement_id       bigint NOT NULL REFERENCES stock_movements (id),
    product_id        bigint NOT NULL REFERENCES products (id),
    counted_on        date NOT NULL,
    ledger_quantity   integer NOT NULL,
    scanned_quantity  integer
);

CREATE INDEX stock_checks_shop_idx ON stock_checks (shop_id);

CREATE TABLE orders (
    id          bigserial PRIMARY KEY,
    shop_id     bigint NOT NULL REFERENCES shops (id),
    product_id  bigint NOT NULL REFERENCES products (id),
    quantity    integer NOT NULL CHECK (quantity > 0),
    customer    text NOT NULL DEFAULT 'web',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX orders_shop_created_at_idx ON orders (shop_id, created_at);

CREATE TABLE stock_updates (
    id                  bigserial PRIMARY KEY,
    shop_id             bigint NOT NULL REFERENCES shops (id),
    status              text NOT NULL CHECK (status IN ('requested', 'running', 'completed', 'failed')),
    requested_at        timestamptz NOT NULL DEFAULT now(),
    started_at          timestamptz,
    finished_at         timestamptz,
    movements_replayed  integer
);

CREATE INDEX stock_updates_shop_requested_at_idx ON stock_updates (shop_id, requested_at DESC);

CREATE TABLE stock_update_schedule (
    shop_id      bigint PRIMARY KEY REFERENCES shops (id),
    next_run_at  timestamptz NOT NULL
);
