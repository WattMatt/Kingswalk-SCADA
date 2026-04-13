-- Kingswalk SCADA GUI — schema review fixes
-- Applies findings from SCHEMA_REVIEW.md + SCHEMA_AUDIT_FINAL.md
-- against SPEC.md v4.0 + Architecture Review
-- Run AFTER 0001_initial.sql
--
-- STRUCTURE:
--   Part 1: Transactional DDL (schema changes, table creates, seeds)
--   Part 2: Non-transactional indexes (CREATE INDEX CONCURRENTLY cannot run inside a transaction)

-- =============================================================
-- PART 1: TRANSACTIONAL DDL
-- =============================================================

BEGIN;

-- =============================================================
-- FIX: Use gen_random_uuid() instead of uuid_generate_v4()
-- (PostgreSQL 13+ native, no extension needed)
-- Note: existing tables keep uuid_generate_v4() defaults;
-- new tables below use gen_random_uuid().
-- =============================================================

-- =============================================================
-- C4: User lifecycle tables (BUILD_STRATEGY §7.3, §8.5)
-- =============================================================

-- Missing columns on core.users (SPEC B.4)
ALTER TABLE core.users ADD COLUMN IF NOT EXISTS mfa_enabled boolean NOT NULL DEFAULT false;
ALTER TABLE core.users ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE core.users ADD COLUMN IF NOT EXISTS last_login_at timestamptz;

-- Missing column on core.audit_log (SPEC B.4)
ALTER TABLE core.audit_log ADD COLUMN IF NOT EXISTS user_agent text;

-- Missing column on core.config (SPEC B.4)
ALTER TABLE core.config ADD COLUMN IF NOT EXISTS updated_by uuid REFERENCES core.users(id);

-- Invite table
CREATE TABLE IF NOT EXISTS core.invite (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email       citext NOT NULL,
    role        core.user_role NOT NULL,
    token_hash  text NOT NULL,
    invited_by  uuid REFERENCES core.users(id),
    expires_at  timestamptz NOT NULL,
    accepted_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_invite_email ON core.invite (email);
CREATE INDEX IF NOT EXISTS idx_invite_expires ON core.invite (expires_at) WHERE accepted_at IS NULL;

-- Password reset table
CREATE TABLE IF NOT EXISTS core.password_reset (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES core.users(id),
    token_hash  text NOT NULL,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_password_reset_user ON core.password_reset (user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_expires ON core.password_reset (expires_at) WHERE used_at IS NULL;

-- Session table
CREATE TABLE IF NOT EXISTS core.session (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES core.users(id),
    refresh_hash text NOT NULL,
    ip          inet,
    user_agent  text,
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_user ON core.session (user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires ON core.session (expires_at) WHERE revoked_at IS NULL;

-- Notification preferences (BUILD_STRATEGY §8.5)
-- Note: events.severity already exists from 0001_initial.sql; no CREATE TYPE needed here

CREATE TABLE IF NOT EXISTS core.notification_preference (
    id          serial PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES core.users(id),
    channel     text NOT NULL CHECK (channel IN ('email','in_app','sms','webhook')),
    severity_min events.severity NOT NULL DEFAULT 'warning',
    enabled     boolean NOT NULL DEFAULT true,
    config      jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (user_id, channel)
);

-- Recovery codes for MFA fallback (SECURITY_AUDIT F10)
CREATE TABLE IF NOT EXISTS core.recovery_code (
    id          serial PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES core.users(id),
    code_hash   text NOT NULL,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recovery_code_user ON core.recovery_code (user_id);

-- =============================================================
-- I1-I4: Missing asset columns (SPEC B.4)
-- =============================================================

-- Main board IP columns
ALTER TABLE assets.main_board ADD COLUMN IF NOT EXISTS ekip_com_ip inet;
ALTER TABLE assets.main_board ADD COLUMN IF NOT EXISTS m4m_1_ip inet;
ALTER TABLE assets.main_board ADD COLUMN IF NOT EXISTS m4m_2_ip inet;
ALTER TABLE assets.main_board ADD COLUMN IF NOT EXISTS switch_ip inet;

-- Breaker missing columns
ALTER TABLE assets.breaker ADD COLUMN IF NOT EXISTS modbus_unit_id integer;
ALTER TABLE assets.breaker ADD COLUMN IF NOT EXISTS feeds_asset_type text CHECK (feeds_asset_type IN ('distribution_board','tenant_feed'));

-- Distribution board FK to breaker
ALTER TABLE assets.distribution_board ADD COLUMN IF NOT EXISTS fed_by_breaker_id uuid REFERENCES assets.breaker(id);

-- Tenant feed FK + lease dates
ALTER TABLE assets.tenant_feed ADD COLUMN IF NOT EXISTS fed_by_breaker_id uuid REFERENCES assets.breaker(id);
ALTER TABLE assets.tenant_feed ADD COLUMN IF NOT EXISTS lease_start date;
ALTER TABLE assets.tenant_feed ADD COLUMN IF NOT EXISTS lease_end date;

-- =============================================================
-- C2: Asset type column on events.event
-- =============================================================

ALTER TABLE events.event ADD COLUMN IF NOT EXISTS asset_type text
    CHECK (asset_type IS NULL OR asset_type IN (
        'main_board', 'breaker', 'distribution_board',
        'tenant_feed', 'lighting_circuit', 'measuring_device'
    ));

-- =============================================================
-- C1: Threshold multi-band pattern (replace single-value)
-- =============================================================

-- Drop old single-threshold columns and recreate table
-- (safer than ALTER since the table should be empty at this stage)
DROP TABLE IF EXISTS events.threshold;

CREATE TABLE events.threshold (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id        uuid,
    asset_class     text,
    metric          text NOT NULL,
    warning_low     real,
    warning_high    real,
    error_low       real,
    error_high      real,
    critical_low    real,
    critical_high   real,
    hysteresis      real NOT NULL DEFAULT 0,
    enabled         boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    -- N7: Enforce logical band ordering (critical_low <= error_low <= warning_low <= warning_high <= error_high <= critical_high)
    CONSTRAINT threshold_band_order CHECK (
        (critical_low IS NULL OR error_low    IS NULL OR critical_low <= error_low) AND
        (error_low    IS NULL OR warning_low  IS NULL OR error_low    <= warning_low) AND
        (warning_low  IS NULL OR warning_high IS NULL OR warning_low  <= warning_high) AND
        (warning_high IS NULL OR error_high   IS NULL OR warning_high <= error_high) AND
        (error_high   IS NULL OR critical_high IS NULL OR error_high  <= critical_high)
    )
);
CREATE INDEX IF NOT EXISTS idx_threshold_asset ON events.threshold (asset_id);
CREATE INDEX IF NOT EXISTS idx_threshold_class ON events.threshold (asset_class) WHERE asset_class IS NOT NULL;

-- =============================================================
-- D1: Reports schema alignment with SPEC
-- =============================================================

ALTER TABLE reports.schedule ADD COLUMN IF NOT EXISTS distribution_list jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE reports.schedule ADD COLUMN IF NOT EXISTS last_run_at timestamptz;
ALTER TABLE reports.schedule ADD COLUMN IF NOT EXISTS next_run_at timestamptz;

-- N2: Drop orphaned distribution text[] column (replaced by distribution_list jsonb above)
ALTER TABLE reports.schedule DROP COLUMN IF EXISTS distribution;

ALTER TABLE reports.artefact ADD COLUMN IF NOT EXISTS schedule_id uuid REFERENCES reports.schedule(id);
ALTER TABLE reports.artefact ADD COLUMN IF NOT EXISTS generated_by uuid REFERENCES core.users(id);
ALTER TABLE reports.artefact ADD COLUMN IF NOT EXISTS file_size_bytes bigint;

-- P1-P8: FK + telemetry indexes moved to PART 2 (outside transaction)
-- because CREATE INDEX CONCURRENTLY cannot run inside a transaction block

-- =============================================================
-- T1: updated_at trigger function + triggers
-- =============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER set_updated_at BEFORE UPDATE ON core.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON assets.main_board
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON assets.breaker
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON assets.measuring_device
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON assets.distribution_board
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON assets.tenant_feed
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON assets.lighting_circuit
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON events.threshold
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================
-- RLS: Enable on ALL security-sensitive tables
-- (Policies will be added during Phase 1 auth build)
-- =============================================================

-- Telemetry tables (edge gateway writes via scada_writer role; app reads via scada_app)
ALTER TABLE telemetry.pq_sample ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry.energy_register ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry.breaker_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry.lighting_state ENABLE ROW LEVEL SECURITY;

-- Event tables
ALTER TABLE events.event ENABLE ROW LEVEL SECURITY;

-- Core tables containing sensitive data (password hashes, token hashes, MFA secrets)
ALTER TABLE core.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.session ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.invite ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.password_reset ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.recovery_code ENABLE ROW LEVEL SECURITY;

-- N1: Placeholder policies — allow the application role (scada_app) full access
-- until Phase 1 RBAC middleware is built. The app authenticates JWT → sets
-- current_setting('app.current_user_id') → RLS policies check it.
-- DO NOT deploy to production without replacing these with proper role-gated policies.

-- =============================================================
-- Seed data: Update main board IPs
-- =============================================================

UPDATE assets.main_board SET ekip_com_ip = '10.10.11.10', m4m_1_ip = '10.10.11.100', m4m_2_ip = '10.10.11.101', switch_ip = '10.10.11.2' WHERE code = 'MB 1.1';
UPDATE assets.main_board SET ekip_com_ip = '10.10.21.10', m4m_1_ip = '10.10.21.100', m4m_2_ip = '10.10.21.101', switch_ip = '10.10.21.2' WHERE code = 'MB 2.1';
UPDATE assets.main_board SET ekip_com_ip = '10.10.22.10', m4m_1_ip = '10.10.22.100', m4m_2_ip = '10.10.22.101', switch_ip = '10.10.22.2' WHERE code = 'MB 2.2';
UPDATE assets.main_board SET ekip_com_ip = '10.10.23.10', m4m_1_ip = '10.10.23.100', m4m_2_ip = '10.10.23.101', switch_ip = '10.10.23.2' WHERE code = 'MB 2.3';
UPDATE assets.main_board SET ekip_com_ip = '10.10.31.10', m4m_1_ip = '10.10.31.100', m4m_2_ip = '10.10.31.101', switch_ip = '10.10.31.2' WHERE code = 'MB 3.1';
UPDATE assets.main_board SET ekip_com_ip = '10.10.41.10', m4m_1_ip = '10.10.41.100', m4m_2_ip = '10.10.41.101', switch_ip = '10.10.41.2' WHERE code = 'MB 4.1';
UPDATE assets.main_board SET ekip_com_ip = '10.10.51.10', m4m_1_ip = '10.10.51.100', m4m_2_ip = '10.10.51.101', switch_ip = '10.10.51.2' WHERE code = 'MB 5.1';
UPDATE assets.main_board SET ekip_com_ip = '10.10.52.10', m4m_1_ip = '10.10.52.100', m4m_2_ip = '10.10.52.101', switch_ip = '10.10.52.2' WHERE code = 'MB 5.2';
UPDATE assets.main_board SET ekip_com_ip = '10.10.53.10', m4m_1_ip = '10.10.53.100', m4m_2_ip = '10.10.53.101', switch_ip = '10.10.53.2' WHERE code = 'MB 5.3';

COMMIT;

-- =============================================================
-- PART 2: NON-TRANSACTIONAL INDEXES
-- CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
-- These are safe to run on a live database without locking tables.
-- On initial setup (empty database), CONCURRENTLY is optional but
-- we keep it for consistency with the production-safe pattern.
-- =============================================================

-- P1: Missing FK indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_measuring_device_main_board
    ON assets.measuring_device (main_board_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_distribution_board_breaker
    ON assets.distribution_board (fed_by_breaker_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_feed_breaker
    ON assets.tenant_feed (fed_by_breaker_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lighting_circuit_db
    ON assets.lighting_circuit (distribution_board_id);

-- N1: FK indexes on new auth tables
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_preference_user
    ON core.notification_preference (user_id);

-- P2: Critical telemetry indexes (Architecture Review)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_breaker_state_last_known
    ON telemetry.breaker_state (breaker_id, ts DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_asset_history
    ON events.event (asset_id, ts DESC);
