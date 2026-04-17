-- 0003_raw_sample.sql
-- Phase 2b staging table: raw telemetry from edge gateway (no FK to asset tables).
-- device_id is the edge string like "MB_1_1_breaker_0"; register_address is the raw
-- Modbus address. Phase 3 will map these to typed asset UUIDs.

CREATE TABLE IF NOT EXISTS telemetry.raw_sample (
    ts               TIMESTAMPTZ  NOT NULL DEFAULT now(),
    device_id        TEXT         NOT NULL,
    register_address INTEGER      NOT NULL,
    raw_value        INTEGER      NOT NULL,
    PRIMARY KEY (device_id, register_address, ts)
);

SELECT create_hypertable(
    'telemetry.raw_sample', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Fast latest-per-device lookup for WebSocket full-state sync
CREATE INDEX IF NOT EXISTS raw_sample_device_ts_idx
    ON telemetry.raw_sample (device_id, ts DESC);
