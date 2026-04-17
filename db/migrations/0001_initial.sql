-- Kingswalk SCADA GUI — initial migration
-- PostgreSQL 16 + TimescaleDB 2.x

-- Extensions must be created outside a transaction block.
-- TimescaleDB in particular cannot be initialised inside BEGIN/COMMIT.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

BEGIN;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS assets;
CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS reports;

-- =============================================================
-- CORE
-- =============================================================

CREATE TYPE core.user_role AS ENUM ('admin','operator','viewer');

CREATE TABLE core.users (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           citext UNIQUE NOT NULL,
    full_name       text NOT NULL,
    password_hash   text NOT NULL,
    role            core.user_role NOT NULL DEFAULT 'viewer',
    mfa_secret      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz
);

CREATE TABLE core.audit_log (
    id          bigserial PRIMARY KEY,
    ts          timestamptz NOT NULL DEFAULT now(),
    user_id     uuid REFERENCES core.users(id),
    action      text NOT NULL,
    asset_id    uuid,
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip          inet
);
CREATE INDEX ON core.audit_log (ts DESC);
CREATE INDEX ON core.audit_log (user_id);
CREATE INDEX ON core.audit_log (asset_id);

CREATE TABLE core.config (
    scope       text NOT NULL,
    key         text NOT NULL,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, key)
);

-- =============================================================
-- ASSETS
-- =============================================================

CREATE TABLE assets.main_board (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        text UNIQUE NOT NULL,
    drawing     text NOT NULL,
    vlan_id     integer NOT NULL,
    subnet      cidr NOT NULL,
    gateway_ip  inet NOT NULL,
    location    text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

CREATE TABLE assets.measuring_package (
    code        text PRIMARY KEY,
    description text NOT NULL
);

CREATE TABLE assets.mp_function (
    id          serial PRIMARY KEY,
    mp_code     text NOT NULL REFERENCES assets.measuring_package(code),
    function    text NOT NULL,
    ansi_code   text,
    unit        text,
    db_field    text NOT NULL,
    poll_class  text NOT NULL CHECK (poll_class IN ('state','inst','energy','harmonics','counter'))
);
CREATE INDEX ON assets.mp_function (mp_code);

CREATE TABLE assets.measuring_device (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    main_board_id   uuid NOT NULL REFERENCES assets.main_board(id),
    kind            text NOT NULL CHECK (kind IN ('m4m30','ekip_com','ekip_dl','pdcom')),
    device_ip       inet NOT NULL,
    modbus_unit_id  integer,
    protocol        text NOT NULL CHECK (protocol IN ('modbus_tcp','iec61850','dual')),
    serial          text,
    firmware_version text,
    installed_at    date,
    replaced_at     date,
    replacement_note text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz,
    UNIQUE (device_ip)
);

CREATE TABLE assets.distribution_board (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            text UNIQUE NOT NULL,
    name            text,
    area_m2         numeric(8,2),
    cable_spec      text,
    essential_supply boolean NOT NULL DEFAULT false,
    generator_bank  text CHECK (generator_bank IN ('A','B')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz
);

CREATE TABLE assets.tenant_feed (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        text UNIQUE NOT NULL,
    tenant_name text NOT NULL,
    area_m2     numeric(8,2),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);

CREATE TABLE assets.breaker (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    main_board_id       uuid NOT NULL REFERENCES assets.main_board(id),
    label               text NOT NULL,
    breaker_code        text NOT NULL,
    abb_family          text NOT NULL,
    rating_amp          integer NOT NULL,
    poles               text NOT NULL CHECK (poles IN ('SP','DP','TP','TPN','FP')),
    mp_code             text REFERENCES assets.measuring_package(code),
    feeds_db_id         uuid REFERENCES assets.distribution_board(id),
    feeds_tenant_id     uuid REFERENCES assets.tenant_feed(id),
    essential_supply    boolean NOT NULL DEFAULT false,
    device_ip           inet,
    protocol            text CHECK (protocol IN ('modbus_tcp','iec61850','dual')),
    installed_at        date,
    replaced_at         date,
    replacement_note    text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    deleted_at          timestamptz,
    CHECK (feeds_db_id IS NULL OR feeds_tenant_id IS NULL)
);
CREATE INDEX ON assets.breaker (main_board_id);
CREATE INDEX ON assets.breaker (mp_code);
CREATE INDEX ON assets.breaker (device_ip);

CREATE TABLE assets.lighting_circuit (
    id                      uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    distribution_board_id   uuid NOT NULL REFERENCES assets.distribution_board(id),
    label                   text NOT NULL,
    rating_amp              numeric(6,2),
    burn_hours              numeric(12,2) NOT NULL DEFAULT 0,
    state                   text NOT NULL DEFAULT 'off' CHECK (state IN ('on','off','fault')),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    deleted_at              timestamptz
);

-- =============================================================
-- TELEMETRY (hypertables)
-- =============================================================

CREATE TABLE telemetry.pq_sample (
    ts          timestamptz NOT NULL,
    device_id   uuid NOT NULL REFERENCES assets.measuring_device(id),
    v_l1_n      real, v_l2_n real, v_l3_n real,
    v_l1_l2     real, v_l2_l3 real, v_l3_l1 real,
    i_l1        real, i_l2 real, i_l3 real, i_n real,
    p_total     real, q_total real, s_total real,
    pf_total    real,
    freq_hz     real,
    thd_v       real, thd_i real,
    harmonics   jsonb,
    PRIMARY KEY (device_id, ts)
);
SELECT create_hypertable('telemetry.pq_sample','ts',chunk_time_interval => INTERVAL '1 day');

CREATE TABLE telemetry.energy_register (
    ts          timestamptz NOT NULL,
    device_id   uuid NOT NULL REFERENCES assets.measuring_device(id),
    kwh_imp     double precision,
    kwh_exp     double precision,
    kvarh_imp   double precision,
    kvarh_exp   double precision,
    PRIMARY KEY (device_id, ts)
);
SELECT create_hypertable('telemetry.energy_register','ts',chunk_time_interval => INTERVAL '7 days');

CREATE TABLE telemetry.breaker_state (
    ts              timestamptz NOT NULL,
    breaker_id      uuid NOT NULL REFERENCES assets.breaker(id),
    state           text NOT NULL CHECK (state IN ('open','closed','tripped')),
    trip_cause      text,
    contact_source  text,
    PRIMARY KEY (breaker_id, ts)
);
SELECT create_hypertable('telemetry.breaker_state','ts',chunk_time_interval => INTERVAL '1 day');

CREATE TABLE telemetry.lighting_state (
    ts          timestamptz NOT NULL,
    circuit_id  uuid NOT NULL REFERENCES assets.lighting_circuit(id),
    state       text NOT NULL,
    current_a   real,
    PRIMARY KEY (circuit_id, ts)
);
SELECT create_hypertable('telemetry.lighting_state','ts',chunk_time_interval => INTERVAL '7 days');

-- Retention policies
SELECT add_retention_policy('telemetry.pq_sample',      INTERVAL '90 days');
SELECT add_retention_policy('telemetry.breaker_state',  INTERVAL '5 years');
SELECT add_retention_policy('telemetry.lighting_state', INTERVAL '5 years');

-- =============================================================
-- EVENTS
-- =============================================================

CREATE TYPE events.severity AS ENUM ('info','warning','error','critical');

CREATE TABLE events.event (
    id                  bigserial PRIMARY KEY,
    ts                  timestamptz NOT NULL DEFAULT now(),
    asset_id            uuid,
    severity            events.severity NOT NULL,
    kind                text NOT NULL,
    message             text NOT NULL,
    payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
    acknowledged_by     uuid REFERENCES core.users(id),
    acknowledged_at     timestamptz
);
CREATE INDEX ON events.event (ts DESC);
CREATE INDEX ON events.event (asset_id);
CREATE INDEX ON events.event (severity);
CREATE INDEX events_unacked_idx ON events.event (ts DESC, severity) WHERE acknowledged_at IS NULL;

CREATE TABLE events.threshold (
    id              serial PRIMARY KEY,
    asset_id        uuid,
    asset_class     text,
    metric          text NOT NULL,
    op              text NOT NULL CHECK (op IN ('<','<=','>','>=','==','!=')),
    value           double precision NOT NULL,
    hysteresis      double precision NOT NULL DEFAULT 0,
    severity        events.severity NOT NULL DEFAULT 'warning',
    enabled         boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- =============================================================
-- REPORTS
-- =============================================================

CREATE TABLE reports.template (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        text UNIQUE NOT NULL,
    name        text NOT NULL,
    query       text NOT NULL,
    format      text NOT NULL CHECK (format IN ('pdf','csv','xlsx')),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reports.schedule (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id     uuid NOT NULL REFERENCES reports.template(id),
    cron            text NOT NULL,
    distribution    text[] NOT NULL DEFAULT '{}',
    enabled         boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reports.artefact (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id     uuid NOT NULL REFERENCES reports.template(id),
    generated_at    timestamptz NOT NULL DEFAULT now(),
    path            text NOT NULL,
    sha256          text NOT NULL,
    retain_until    timestamptz
);

-- =============================================================
-- SEED DATA — Measuring Packages
-- =============================================================

INSERT INTO assets.measuring_package (code, description) VALUES
 ('MP1','Full fiscal/tenant metering — V, I, P, Q, S, PF, energy, THD'),
 ('MP2','Standard feeder protection set — V, I, P, Q, S, PF'),
 ('MP3','Lighting circuit set — I, kWh, burn hours'),
 ('MP4','Essential/emergency feed — V, I, PF, event counters'),
 ('MP5','HVAC/chiller set — I, P, Q, PF, running hours'),
 ('MP6','Lift/pump set — starts, I, running hours'),
 ('MP7','Generator/changeover — V, I, frequency, source status');

-- =============================================================
-- SEED DATA — Main Boards (with VLAN/subnet plan)
-- =============================================================

INSERT INTO assets.main_board (code, drawing, vlan_id, subnet, gateway_ip, location) VALUES
 ('MB 1.1','643.E.301',11,'10.10.11.0/24','10.10.11.1','MB 1.1 switchroom'),
 ('MB 2.1','643.E.302',21,'10.10.21.0/24','10.10.21.1','MB 2.1 switchroom'),
 ('MB 2.2','643.E.303',22,'10.10.22.0/24','10.10.22.1','MB 2.2 switchroom'),
 ('MB 2.3','643.E.304',23,'10.10.23.0/24','10.10.23.1','MB 2.3 switchroom'),
 ('MB 3.1','643.E.305',31,'10.10.31.0/24','10.10.31.1','MB 3.1 switchroom'),
 ('MB 4.1','643.E.306',41,'10.10.41.0/24','10.10.41.1','MB 4.1 switchroom'),
 ('MB 5.1','643.E.307',51,'10.10.51.0/24','10.10.51.1','MB 5.1 switchroom'),
 ('MB 5.2','643.E.308',52,'10.10.52.0/24','10.10.52.1','MB 5.2 switchroom'),
 ('MB 5.3','643.E.309',53,'10.10.53.0/24','10.10.53.1','MB 5.3 switchroom');

COMMIT;

-- =============================================================
-- CONTINUOUS AGGREGATES
-- Must be created OUTSIDE a transaction block — TimescaleDB
-- restriction: WITH (timescaledb.continuous) cannot run inside
-- BEGIN/COMMIT.
-- =============================================================

CREATE MATERIALIZED VIEW telemetry.pq_1min
WITH (timescaledb.continuous) AS
SELECT device_id,
       time_bucket('1 minute', ts) AS bucket,
       avg(v_l1_n)   AS v_l1_n,   avg(v_l2_n)  AS v_l2_n,  avg(v_l3_n)  AS v_l3_n,
       avg(i_l1)     AS i_l1,     avg(i_l2)    AS i_l2,    avg(i_l3)    AS i_l3,
       avg(p_total)  AS p_avg,    max(p_total)  AS p_max,
       avg(pf_total) AS pf_avg,
       avg(freq_hz)  AS freq_avg,
       avg(thd_v)    AS thd_v_avg, avg(thd_i)   AS thd_i_avg
FROM telemetry.pq_sample
GROUP BY device_id, bucket;

SELECT add_continuous_aggregate_policy('telemetry.pq_1min',
    start_offset => INTERVAL '3 hours',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
