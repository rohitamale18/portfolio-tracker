-- keep enum if duckdb supports it, fallback to VARCHAR check later in code
CREATE TYPE IF NOT EXISTS transaction_type AS ENUM ('BUY', 'SELL', 'ADJUST');

CREATE TABLE IF NOT EXISTS stock_transaction_event (
    id UUID DEFAULT uuid(),
    event_time TIMESTAMP NOT NULL,
    ticker VARCHAR NOT NULL,
    quantity DOUBLE NOT NULL CHECK (quantity >= 0),
    price_per_share DOUBLE NOT NULL CHECK (price_per_share >= 0),
    event_type VARCHAR NOT NULL CHECK (event_type IN ('BUY', 'SELL', 'ADJUST')),
    manual_avg_override DOUBLE CHECK (manual_avg_override IS NULL OR manual_avg_override >= 0),
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_holdings_snapshot (
    report_date DATE NOT NULL,
    ticker VARCHAR NOT NULL,
    quantity DOUBLE NOT NULL,
    avg_cost DOUBLE NOT NULL,
    close_price DOUBLE,
    market_value DOUBLE,
    cost_basis DOUBLE,
    PRIMARY KEY (report_date, ticker)
);
