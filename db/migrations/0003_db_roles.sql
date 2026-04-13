-- Kingswalk SCADA — Database Roles with Least-Privilege Grants
-- Run AFTER 0001_initial.sql and 0001a_schema_review_fixes.sql
--
-- Per SPEC.md §A.5 ("Database roles (principle of least privilege)"):
--   - scada_app: FastAPI. SELECT/INSERT/UPDATE on all tables. No DELETE on core.audit_log.
--   - scada_writer: Edge gateway. INSERT-only on telemetry.*. SELECT on assets.*. No access to core/events/reports.
--   - scada_reader: Report worker. SELECT-only on all except core.password_reset and core.session.
--   - All three: non-superuser, non-createdb, non-createrole.

-- =============================================================
-- PART 1: CREATE ROLES
-- =============================================================

BEGIN;

-- Application role (FastAPI backend)
DO $$ BEGIN
  CREATE ROLE scada_app WITH NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
COMMENT ON ROLE scada_app IS 'FastAPI application role: SELECT/INSERT/UPDATE all tables, no DELETE on audit_log';

-- Edge gateway role (Modbus poller + telemetry ingestion)
DO $$ BEGIN
  CREATE ROLE scada_writer WITH NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
COMMENT ON ROLE scada_writer IS 'Edge gateway role: INSERT-only on telemetry, SELECT on assets, no access to core/events/reports';

-- Report worker role (read-only analytics)
DO $$ BEGIN
  CREATE ROLE scada_reader WITH NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
COMMENT ON ROLE scada_reader IS 'Report worker role: SELECT-only on all tables except password_reset and session';

-- =============================================================
-- PART 2: SCADA_APP GRANTS (API backend)
-- =============================================================

-- Default schema permissions
GRANT USAGE ON SCHEMA core, assets, telemetry, events, reports TO scada_app;

-- CORE schema: full CUD except audit_log DELETE
GRANT SELECT, INSERT, UPDATE ON core.users TO scada_app;
GRANT SELECT, INSERT, UPDATE ON core.session TO scada_app;
GRANT SELECT, INSERT ON core.audit_log TO scada_app;  -- NO DELETE, NO UPDATE
GRANT SELECT, INSERT, UPDATE ON core.config TO scada_app;
GRANT SELECT, INSERT, UPDATE ON core.invite TO scada_app;
GRANT SELECT, INSERT, UPDATE ON core.password_reset TO scada_app;
GRANT SELECT, INSERT, UPDATE ON core.recovery_code TO scada_app;
GRANT SELECT, INSERT, UPDATE ON core.notification_preference TO scada_app;

-- ASSETS schema: full CUD
GRANT SELECT, INSERT, UPDATE ON assets.main_board TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.measuring_package TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.mp_function TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.measuring_device TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.distribution_board TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.tenant_feed TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.breaker TO scada_app;
GRANT SELECT, INSERT, UPDATE ON assets.lighting_circuit TO scada_app;
-- canvas/nav_route/asset_document tables not yet migrated; add grants when 0002_canvas_layers.sql is extended

-- TELEMETRY schema: full CUD (live data ingestion)
GRANT SELECT, INSERT, UPDATE ON telemetry.pq_sample TO scada_app;
GRANT SELECT, INSERT, UPDATE ON telemetry.energy_register TO scada_app;
GRANT SELECT, INSERT, UPDATE ON telemetry.breaker_state TO scada_app;
GRANT SELECT, INSERT, UPDATE ON telemetry.lighting_state TO scada_app;

-- EVENTS schema: full CUD
GRANT SELECT, INSERT, UPDATE ON events.threshold TO scada_app;
GRANT SELECT, INSERT, UPDATE ON events.event TO scada_app;

-- REPORTS schema: full CUD
GRANT SELECT, INSERT, UPDATE ON reports.schedule TO scada_app;
GRANT SELECT, INSERT, UPDATE ON reports.artefact TO scada_app;
GRANT SELECT, INSERT, UPDATE ON reports.template TO scada_app;
-- continuous_aggregate_refresh_log not yet created; add grant when hypertable migration is applied

-- Sequence grants for SERIAL/BIGSERIAL columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core, assets, telemetry, events, reports TO scada_app;

-- =============================================================
-- PART 3: SCADA_WRITER GRANTS (Edge gateway)
-- =============================================================

-- Default schema permissions
GRANT USAGE ON SCHEMA assets, telemetry TO scada_writer;

-- TELEMETRY schema: INSERT-only (append-only time-series data)
GRANT INSERT ON telemetry.pq_sample TO scada_writer;
GRANT INSERT ON telemetry.energy_register TO scada_writer;
GRANT INSERT ON telemetry.breaker_state TO scada_writer;
GRANT INSERT ON telemetry.lighting_state TO scada_writer;

-- ASSETS schema: SELECT-only (read asset metadata for context)
GRANT SELECT ON assets.main_board TO scada_writer;
GRANT SELECT ON assets.measuring_device TO scada_writer;
GRANT SELECT ON assets.breaker TO scada_writer;
GRANT SELECT ON assets.distribution_board TO scada_writer;
GRANT SELECT ON assets.tenant_feed TO scada_writer;
GRANT SELECT ON assets.lighting_circuit TO scada_writer;

-- Sequence grants for telemetry tables (no SERIAL columns, but for safety)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA telemetry TO scada_writer;

-- =============================================================
-- PART 4: SCADA_READER GRANTS (Report worker)
-- =============================================================

-- Default schema permissions
GRANT USAGE ON SCHEMA core, assets, telemetry, events, reports TO scada_reader;

-- All SELECT for analytics — except password_reset and session (contain secrets)
-- CORE: selective (no password_reset, no session)
GRANT SELECT ON core.users TO scada_reader;
GRANT SELECT ON core.audit_log TO scada_reader;
GRANT SELECT ON core.config TO scada_reader;
GRANT SELECT ON core.invite TO scada_reader;
GRANT SELECT ON core.recovery_code TO scada_reader;
GRANT SELECT ON core.notification_preference TO scada_reader;
-- SKIP: core.session, core.password_reset (contain sensitive tokens/hashes)

-- ASSETS: full SELECT (for asset context in reports)
GRANT SELECT ON assets.main_board TO scada_reader;
GRANT SELECT ON assets.measuring_package TO scada_reader;
GRANT SELECT ON assets.mp_function TO scada_reader;
GRANT SELECT ON assets.measuring_device TO scada_reader;
GRANT SELECT ON assets.distribution_board TO scada_reader;
GRANT SELECT ON assets.tenant_feed TO scada_reader;
GRANT SELECT ON assets.breaker TO scada_reader;
GRANT SELECT ON assets.lighting_circuit TO scada_reader;
-- canvas/nav_route/asset_document tables not yet migrated; add grants when extended

-- TELEMETRY: full SELECT (time-series data for analysis)
GRANT SELECT ON telemetry.pq_sample TO scada_reader;
GRANT SELECT ON telemetry.energy_register TO scada_reader;
GRANT SELECT ON telemetry.breaker_state TO scada_reader;
GRANT SELECT ON telemetry.lighting_state TO scada_reader;

-- EVENTS: full SELECT (thresholds and events for analysis)
GRANT SELECT ON events.threshold TO scada_reader;
GRANT SELECT ON events.event TO scada_reader;

-- REPORTS: full SELECT
GRANT SELECT ON reports.schedule TO scada_reader;
GRANT SELECT ON reports.artefact TO scada_reader;
GRANT SELECT ON reports.template TO scada_reader;
-- continuous_aggregate_refresh_log not yet created; add grant when hypertable migration is applied

-- =============================================================
-- PART 5: AUDIT LOG INTEGRITY — REVOKE INSERT/UPDATE/DELETE for scada_app
-- =============================================================

-- Per SPEC.md §A.5 "Audit log integrity":
-- "REVOKE DELETE, UPDATE ON core.audit_log FROM scada_app;"
-- Only DBA role (not used by application) can modify audit records.

REVOKE DELETE, UPDATE ON core.audit_log FROM scada_app;

-- =============================================================
-- PART 6: REVOKE DEFAULT PUBLIC PERMISSIONS
-- =============================================================

-- Remove PUBLIC access to prevent anonymous connections
REVOKE CREATE ON SCHEMA core FROM PUBLIC;
REVOKE CREATE ON SCHEMA assets FROM PUBLIC;
REVOKE CREATE ON SCHEMA telemetry FROM PUBLIC;
REVOKE CREATE ON SCHEMA events FROM PUBLIC;
REVOKE CREATE ON SCHEMA reports FROM PUBLIC;

REVOKE ALL ON ALL TABLES IN SCHEMA core FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA assets FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA telemetry FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA events FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA reports FROM PUBLIC;

COMMIT;
