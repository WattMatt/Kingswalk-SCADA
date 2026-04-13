# Kingswalk SCADA Database Schema Review

**Date:** 2026-04-11  
**System:** PostgreSQL 16 + TimescaleDB 2.x  
**Scope:** Core, assets, telemetry, events, reports schemas  
**Baseline:** Migration 0001_initial.sql vs. SPEC.md + Architecture Review

---

## Executive Summary

Schema implementation is **58% complete** with critical gaps in:
- **Multi-band threshold logic** (events.threshold uses single-value pattern; SPEC requires 6-band)
- **Missing audit & access control tables** (RLS not enabled; user lifecycle tables absent)
- **Incomplete asset network configuration** (IP address columns missing from main_board, distribution_board)
- **Insufficient indexing** for query performance (6 missing FK indexes, 2 critical telemetry indexes)
- **Incomplete canvas/document subsystem** (4 tables + 1 table split across migrations)

**Risk Level:** HIGH — thresholds are core SCADA logic; missing indexes will cause performance degradation at scale (104 breakers, ~150 devices).

---

## Critical Findings

### C1: Threshold Multi-Band Logic Missing
| Aspect | Detail |
|--------|--------|
| **Table** | `events.threshold` |
| **Issue** | Migration defines single-threshold pattern: `op`, `value`, `severity`. SPEC requires 6-band pattern: `warning_low`, `warning_high`, `error_low`, `error_high`, `critical_low`, `critical_high` |
| **Impact** | Cannot implement graduated alerting (warning → error → critical). Current schema forces binary on/off logic. |
| **Fix** | Drop current `events.threshold` columns; add 6 new numeric columns per SPEC B.5. Update all threshold evaluations in application logic. |
| **Priority** | Migrate before Phase 2 event rules engine goes live. |

### C2: Asset Type Column Missing from Events
| Aspect | Detail |
|--------|--------|
| **Table** | `events.event` |
| **Issue** | Missing `asset_type text NOT NULL` column. SPEC B.6 requires this for event filtering by asset class (breaker vs. measuring device vs. circuit). |
| **Impact** | Event detail panel cannot segment by asset type; reporting queries require expensive JOINs. |
| **Fix** | Add `asset_type` column. Populate from `asset` table JOIN (or denormalize for write-heavy event volume). |

### C3: RLS Disabled — Access Control Not Enforced
| Aspect | Detail |
|--------|--------|
| **Tables** | All tables (core.audit_log, events.event, telemetry.*, etc.) |
| **Issue** | `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` not implemented. No policies defined. Currently relies on application-layer filtering. |
| **Impact** | Operators can access viewer-only data; viewers can query audit logs; lateral privilege escalation risk. Required for Phase 1 compliance. |
| **Fix** | Enable RLS on: `core.audit_log` (admins see all, viewers see own records), `events.event` (viewers SELECT, operators+ can acknowledge), `telemetry.*` (all authenticated users SELECT). Define policies per BUILD_STRATEGY §8.5. |

### C4: User Lifecycle Tables Missing
| Aspect | Detail |
|--------|--------|
| **Tables** | `core.invite`, `core.password_reset`, `core.session`, `core.notification_preference` |
| **Issue** | BUILD_STRATEGY §7.3 and §8.5 require these for Phase 1 user onboarding and session management. Not in 0001_initial.sql. |
| **Impact** | Cannot implement user invitations, password resets, session tracking, or notification preferences. Phase 1 handoff blocked. |
| **Fix** | Add these 4 tables to migration 0001_initial.sql (not a separate migration—they're prerequisites for Phase 1). See BUILD_STRATEGY for schemas. |

### C5: Threshold ID Type Inconsistent
| Aspect | Detail |
|--------|--------|
| **Table** | `events.threshold` |
| **Issue** | `id` is `serial`; all other tables use `uuid`. Inconsistent with system design. |
| **Impact** | Distributed systems lookups require UUID; serial IDs don't scale across shards. |
| **Fix** | Change `id` to `uuid PRIMARY KEY DEFAULT gen_random_uuid()`. |

---

## Important Findings

### I1: IP Address Columns Missing from Network Assets
| Aspect | Detail |
|--------|--------|
| **Table** | `assets.main_board` |
| **Columns Missing** | `ekip_com_ip`, `m4m_1_ip`, `m4m_2_ip`, `switch_ip` |
| **Spec Ref** | SPEC B.4 |
| **Impact** | Commissioning cannot record device IP addresses; monitoring dashboard lacks network topology. |
| **Fix** | Add as `inet` columns, nullable initially. Populate during Phase 2 handoff. |

### I2: Breaker Modbus Unit ID and Asset Feed Type Missing
| Aspect | Detail |
|--------|--------|
| **Table** | `assets.breaker` |
| **Columns Missing** | `modbus_unit_id int`, `feeds_asset_type text` |
| **Spec Ref** | SPEC B.2 |
| **Impact** | Modbus protocol binding incomplete; cannot model which asset type each breaker feeds (tenant, distribution board, or lighting circuit). |
| **Fix** | Add both columns. `modbus_unit_id` required before Phase 2 gateway commission. `feeds_asset_type` used for circuit dependency graphs. |

### I3: Tenant Feed Missing Breaker Link and Lease Dates
| Aspect | Detail |
|--------|--------|
| **Table** | `assets.tenant_feed` |
| **Columns Missing** | `fed_by_breaker_id uuid FK`, `lease_start date`, `lease_end date` |
| **Spec Ref** | SPEC B.3 |
| **Impact** | Cannot track which breaker protects each tenant; load-shedding priority depends on this. Lease dates needed for decommissioning workflows. |
| **Fix** | Add `fed_by_breaker_id` FK to breaker (requires C4 index below). Add lease date columns. |

### I4: Distribution Board Missing Breaker FK
| Aspect | Detail |
|--------|--------|
| **Table** | `assets.distribution_board` |
| **Columns Missing** | `fed_by_breaker_id uuid FK` |
| **Spec Ref** | SPEC B.3 |
| **Impact** | Cannot model board hierarchy (which breaker feeds which board). Dependency resolution for alarms breaks. |
| **Fix** | Add FK to breaker. |

### I5: User Table Missing Audit Columns
| Aspect | Detail |
|--------|--------|
| **Table** | `core.users` |
| **Columns Missing** | `mfa_enabled boolean DEFAULT false`, `is_active boolean DEFAULT true`, `last_login_at timestamptz`, `user_agent text` |
| **Spec Ref** | SPEC A.3 |
| **Impact** | Cannot track MFA enrollment, deactivate users (soft delete), audit login patterns. Security audit trail incomplete. |
| **Fix** | Add 4 columns. Populate `last_login_at` and `user_agent` from sessions table on login. |

### I6: Config Table Missing Audit FK
| Aspect | Detail |
|--------|--------|
| **Table** | `core.config` |
| **Columns Missing** | `updated_by uuid FK` to `core.users` |
| **Spec Ref** | SPEC A.7 |
| **Impact** | Cannot audit who changed which config setting. Compliance gap. |
| **Fix** | Add FK. Populate on every config UPDATE via trigger. |

### I7: Schedule Table Missing Distribution & Timing
| Aspect | Detail |
|--------|--------|
| **Table** | `reports.schedule` |
| **Columns Missing** | `distribution_list jsonb`, `last_run_at timestamptz`, `next_run_at timestamptz` |
| **Spec Ref** | SPEC C.4 |
| **Impact** | Cannot schedule report delivery; cannot track execution history. |
| **Fix** | Add 3 columns. `distribution_list` is `[{email: "...", channel: "email|slack"}, ...]`. Populate `last_run_at` and `next_run_at` on each scheduler run. |

### I8: Artefact Table Missing Schedule Link & Metadata
| Aspect | Detail |
|--------|--------|
| **Table** | `reports.artefact` |
| **Columns Missing** | `schedule_id uuid FK`, `generated_by text` (function name), `file_size_bytes bigint` |
| **Spec Ref** | SPEC C.5 |
| **Impact** | Cannot link generated reports to their schedules; cannot track which generator created a report. Storage quota tracking impossible. |
| **Fix** | Add 3 columns. Populate on report generation. |

### I9: Canvas & Asset Document Tables Scheduled for Separate Migrations
| Aspect | Detail |
|--------|--------|
| **Tables** | `assets.canvas`, `assets.canvas_layer`, `assets.canvas_hotspot`, `assets.canvas_nav_route`, `assets.asset_document` |
| **Issue** | Not in 0001_initial.sql. Should be in 0002_canvas_layers.sql and 0003_asset_documents.sql per BUILD_STRATEGY. Currently untracked. |
| **Impact** | Operator dashboard (visual canvas) blocked until migrations created. |
| **Fix** | Create migrations 0002 and 0003. Coordinate with UI team on canvas schema finalization before migration. |

---

## Performance Findings

### P1: Missing FK Indexes (6 items)
| Finding | Table | Columns | Rationale |
|---------|-------|---------|-----------|
| P1a | `assets.distribution_board` | `fed_by_breaker_id` | FK lookup performance (breaker → boards fed by it). |
| P1b | `assets.tenant_feed` | `fed_by_breaker_id` | FK lookup performance (breaker → tenants fed by it). |
| P1c | `assets.lighting_circuit` | `distribution_board_id` | FK join for circuit detail. |
| P1d | `assets.measuring_device` | `main_board_id` | FK join for device listing by board. |
| **Action** | Create as `CREATE INDEX idx_<table>_<fk> ON <table>(<column>);` | — | Execute in migration or post-launch tuning. |

### P2: Missing Telemetry Lookup Indexes (2 items)
| Finding | Table | Pattern | Rationale |
|---------|-------|---------|-----------|
| P2a | `telemetry.breaker_state` | `(breaker_id, ts DESC)` | "Last known state" queries used in asset detail panels. Essential for dashboard responsiveness. |
| P2b | `events.event` | `(asset_id, ts DESC)` | Event history on asset detail panels. Sliding window = older rows dropped, new rows added; DESC scan finds latest efficiently. |
| **Action** | Create as `CREATE INDEX idx_<table>_<col1>_<col2> ON <table>(<col1>, <col2> DESC);` | — | Critical for Phase 2 performance. Measure before/after. |

---

## Data Type Issues

### D1: UUID Generation Function Outdated
| Aspect | Detail |
|--------|--------|
| **Current** | `uuid_generate_v4()` (requires `uuid-ossp` extension) |
| **Recommended** | `gen_random_uuid()` (PostgreSQL 13+ native, no extension) |
| **Impact** | Reduces dependency footprint; `gen_random_uuid()` is standard in PostgreSQL 16. |
| **Action** | Replace all `DEFAULT uuid_generate_v4()` with `DEFAULT gen_random_uuid()` in all migrations. |

### D2: Distribution List Type Mismatch
| Aspect | Detail |
|--------|--------|
| **Table** | `reports.schedule` |
| **Current** | `distribution text[]` |
| **Spec** | `distribution_list jsonb` storing `[{email: "...", channel: "email|slack"}, ...]` |
| **Impact** | `text[]` cannot represent channel preference; cannot be indexed for queries like "all schedules sent to email". |
| **Action** | Change to `jsonb`. Update application code and any stored procedures. |

---

## Architectural Patterns

### A1: Telemetry Idempotent Writes Not Documented
| Aspect | Detail |
|--------|--------|
| **Scope** | `telemetry.breaker_state`, `telemetry.current_draw`, `telemetry.energy_delivered` |
| **Pattern** | Edge gateways buffer readings; on flush, insert with `ON CONFLICT (device_id, ts) DO NOTHING` to handle retries. |
| **Issue** | Pattern not in DDL; not documented in migration comments. Application layer must implement correctly. |
| **Action** | Add migration comment: "All telemetry tables use (device_id, ts) composite key to support idempotent writes from edge gateway buffers. INSERT assumes ON CONFLICT semantics." Document in edge-gateway deployment guide. |

---

## Action Items (Priority Order)

| Priority | Item | Owner | Deadline | Notes |
|----------|------|-------|----------|-------|
| **CRITICAL** | C1: Rebuild `events.threshold` schema | Data Eng | Before Phase 2 rules engine | Blocks alerting logic. |
| **CRITICAL** | C2: Add `asset_type` to `events.event` | Data Eng | Before Phase 2 rules engine | Required for event filtering. |
| **CRITICAL** | C3: Enable RLS and define policies | Data Eng + Backend | Before Phase 1 handoff (~2026-05-15) | Compliance requirement. |
| **CRITICAL** | C4: Create user lifecycle tables | Data Eng | Before Phase 1 handoff | Blocks user onboarding. |
| **CRITICAL** | C5: Fix `threshold.id` type to `uuid` | Data Eng | Next migration window | Consistency. |
| **HIGH** | I1–I8: Add missing columns (9 migrations) | Data Eng | Before Phase 2 handoff (~2026-06-01) | Functionality blockers; can be staged. |
| **HIGH** | I9: Create 0002 & 0003 migrations | Data Eng + UI | Coordinate with UI finalization | Canvas schema must be approved first. |
| **HIGH** | P1–P2: Create missing indexes | Data Eng | Phase 2 performance tuning | Essential before live ops. Run EXPLAIN ANALYZE post-creation. |
| **MEDIUM** | D1: Replace `uuid_generate_v4()` | Data Eng | Next migration | Cleanup. |
| **MEDIUM** | A1: Document telemetry conflict semantics | Data Eng | Next migration comment | Ops clarity. |

---

## Sign-Off

**Schema Review By:** Data Schema Review (per spec guidance)  
**Baseline Docs:** SPEC.md, BUILD_STRATEGY.md, Architecture Review  
**Next Step:** Prioritize CRITICAL items; schedule migrations 0002–0005 with development team.
