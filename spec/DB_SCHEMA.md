# Kingswalk SCADA — Database Schema Reference

**Engine:** PostgreSQL 16 + TimescaleDB 2.x
**Companion migrations:**
- `db/migrations/0001_initial.sql` — base schema
- `db/migrations/0001a_schema_review_fixes.sql` — schema review + final audit fixes (user lifecycle, recovery codes, threshold multi-band with band-ordering CHECK, asset_type CHECK on events, missing FKs, CONCURRENTLY indexes outside txn, RLS on auth tables, triggers, orphaned column cleanup)
- `db/migrations/0002_canvas_layers.sql` — canvas & spatial mapping (pending)
- `db/migrations/0003_asset_documents.sql` — asset document repository (pending)

## 1. Design principles

- **Asset registry** lives in regular relational tables — low row count, high integrity, heavily referenced.
- **Telemetry** (power quality, meter readings, state samples) lives in **TimescaleDB hypertables** chunked on `ts`.
- **Events and audit** are append-only; never updated, never deleted within the retention window.
- **Soft delete** on registry tables via `deleted_at`; telemetry is never soft-deleted.
- All timestamps are `TIMESTAMPTZ` in UTC; presentation timezone handled in the application.

## 2. Schemas

| Schema | Purpose |
|---|---|
| `core` | Users, roles, audit, config |
| `assets` | Main boards, breakers, measuring devices, DBs, tenants, lighting |
| `telemetry` | PQ samples, energy registers, state samples (hypertables) |
| `events` | Switching events, trips, alarms |
| `reports` | Report templates, scheduled jobs, generated artefacts |

## 3. Core tables

### 3.1 `core.users`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `email` | `citext` UNIQUE | |
| `full_name` | `text` | |
| `password_hash` | `text` | argon2id |
| `role` | `core.user_role` ENUM | `admin`, `operator`, `viewer` |
| `mfa_secret` | `text` NULL | TOTP secret, AES-encrypted |
| `created_at` / `updated_at` / `deleted_at` | `timestamptz` | |

### 3.2 `core.audit_log`
Append-only. Every mutating API action writes one row.

| Column | Type |
|---|---|
| `id` | `bigserial` PK |
| `ts` | `timestamptz` |
| `user_id` | `uuid` FK → `core.users` |
| `action` | `text` |
| `asset_id` | `uuid` NULL |
| `payload` | `jsonb` |
| `ip` | `inet` |

### 3.3 `core.config`
Single-row configuration pattern keyed by `(scope, key)`. Includes `updated_by uuid FK → core.users`.

### 3.4 `core.invite`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `email` | `citext` | |
| `role` | `core.user_role` | Pre-assigned role |
| `token_hash` | `text` | argon2id hash of magic link token |
| `invited_by` | `uuid` FK → `core.users` | |
| `expires_at` | `timestamptz` | 48-hour expiry |
| `accepted_at` | `timestamptz` NULL | |
| `created_at` | `timestamptz` | |

### 3.5 `core.password_reset`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `user_id` | `uuid` FK → `core.users` | |
| `token_hash` | `text` | |
| `expires_at` | `timestamptz` | 1-hour expiry |
| `used_at` | `timestamptz` NULL | |
| `created_at` | `timestamptz` | |

### 3.6 `core.session`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `user_id` | `uuid` FK → `core.users` | |
| `refresh_hash` | `text` | Hash of refresh token |
| `ip` | `inet` | |
| `user_agent` | `text` | |
| `expires_at` | `timestamptz` | 7-day refresh token expiry |
| `revoked_at` | `timestamptz` NULL | |
| `created_at` | `timestamptz` | |

### 3.7 `core.notification_preference`
| Column | Type | Notes |
|---|---|---|
| `id` | `serial` PK | |
| `user_id` | `uuid` FK → `core.users` | |
| `channel` | `text` | `email`, `in_app`, `sms`, `webhook` |
| `severity_min` | `events.severity` | Minimum severity to receive |
| `enabled` | `boolean` DEFAULT true | |
| `config` | `jsonb` | Channel-specific config (email, phone, webhook URL) |
| UNIQUE | `(user_id, channel)` | |

### 3.8 `core.recovery_code`
| Column | Type | Notes |
|---|---|---|
| `id` | `serial` PK | |
| `user_id` | `uuid` FK → `core.users` | |
| `code_hash` | `text` NOT NULL | argon2id hash of recovery code |
| `used_at` | `timestamptz` NULL | Set on single use |
| `created_at` | `timestamptz` DEFAULT now() | |

MFA recovery codes. 10 codes generated during TOTP enrollment, displayed once, never retrievable. New generation invalidates all previous codes. RLS enabled.

## 4. Asset tables

### 4.1 `assets.main_board`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `code` | `text` UNIQUE | e.g. `MB 1.1` |
| `drawing` | `text` | e.g. `643.E.301` |
| `vlan_id` | `int` | SCADA VLAN |
| `subnet` | `cidr` | e.g. `10.10.11.0/24` |
| `gateway_ip` | `inet` | .1 on subnet |
| `ekip_com_ip` | `inet` NULL | .10 on subnet |
| `m4m_1_ip` | `inet` NULL | .100 on subnet |
| `m4m_2_ip` | `inet` NULL | .101 on subnet |
| `switch_ip` | `inet` NULL | .2 on subnet (edge switch) |
| `location` | `text` | |
| `created_at` / `updated_at` / `deleted_at` | `timestamptz` | |

### 4.2 `assets.breaker`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `main_board_id` | `uuid` FK | |
| `label` | `text` | e.g. `DB-24A` |
| `breaker_code` | `text` | `TM3`, `TS2`, `TS1` |
| `abb_family` | `text` | `MCCB-TMAX-XT3`, `ACB-EMAX-E2`, etc. |
| `rating_amp` | `int` | |
| `poles` | `text` | `TP`, `DP`, `SP` |
| `mp_code` | `text` | `MP1`..`MP7` |
| `feeds_asset_id` | `uuid` NULL | → `assets.distribution_board` or `assets.tenant_feed` |
| `essential_supply` | `bool` DEFAULT false | On generator essential supply (48V relay controlled) |
| `device_ip` | `inet` NULL | trip unit IP if addressable |
| `protocol` | `text` | `modbus_tcp`, `iec61850`, `dual` |
| `installed_at` | `date` NULL | Original installation date |
| `replaced_at` | `date` NULL | Last device replacement — resets operational counters |
| `replacement_note` | `text` NULL | Reason for replacement |
| `created_at` / `updated_at` / `deleted_at` | | |

### 4.3 `assets.measuring_device`
Represents M4M 30, Ekip Datalogger, Ekip Com, PDCOM.

| Column | Type |
|---|---|
| `id` | `uuid` PK |
| `main_board_id` | `uuid` FK |
| `kind` | `text` (`m4m30`, `ekip_com`, `ekip_dl`, `pdcom`) |
| `device_ip` | `inet` |
| `modbus_unit_id` | `int` NULL |
| `protocol` | `text` |
| `serial` | `text` NULL |
| `firmware_version` | `text` NULL |
| `installed_at` | `date` NULL |
| `replaced_at` | `date` NULL |
| `replacement_note` | `text` NULL |

### 4.4 `assets.distribution_board`
| Column | Type |
|---|---|
| `id` | `uuid` PK |
| `code` | `text` UNIQUE |
| `name` | `text` |
| `area_m2` | `numeric(8,2)` NULL |
| `cable_spec` | `text` NULL |
| `essential_supply` | `bool` DEFAULT false |
| `generator_bank` | `text` NULL | `'A'` or `'B'` — which generator bank serves this DB |
| `fed_by_breaker_id` | `uuid` FK |

### 4.5 `assets.tenant_feed`
| Column | Type |
|---|---|
| `id` | `uuid` PK |
| `code` | `text` UNIQUE |
| `tenant_name` | `text` |
| `area_m2` | `numeric(8,2)` |
| `fed_by_breaker_id` | `uuid` FK |

### 4.6 `assets.lighting_circuit`
| Column | Type |
|---|---|
| `id` | `uuid` PK |
| `distribution_board_id` | `uuid` FK |
| `label` | `text` |
| `rating_amp` | `numeric(6,2)` |
| `burn_hours` | `numeric(12,2)` DEFAULT 0 |
| `state` | `text` (`on`,`off`,`fault`) |

### 4.7 `assets.measuring_package`
Catalog of MP1..MP7 (reference).

| Column | Type |
|---|---|
| `code` | `text` PK |
| `description` | `text` |

### 4.8 `assets.mp_function`
48 rows — one per function within an MP.

| Column | Type |
|---|---|
| `id` | `serial` PK |
| `mp_code` | `text` FK → `assets.measuring_package` |
| `function` | `text` |
| `ansi_code` | `text` NULL |
| `unit` | `text` NULL |
| `db_field` | `text` — the telemetry column that carries the reading |
| `poll_class` | `text` — `state`, `inst`, `energy`, `harmonics`, `counter` |

## 5. Telemetry (TimescaleDB hypertables)

### 5.1 `telemetry.pq_sample`
```sql
CREATE TABLE telemetry.pq_sample (
  ts            TIMESTAMPTZ NOT NULL,
  device_id     UUID        NOT NULL,
  v_l1_n        REAL, v_l2_n REAL, v_l3_n REAL,
  v_l1_l2       REAL, v_l2_l3 REAL, v_l3_l1 REAL,
  i_l1          REAL, i_l2    REAL, i_l3   REAL, i_n REAL,
  p_total       REAL, q_total REAL, s_total REAL,
  pf_total      REAL,
  freq_hz       REAL,
  thd_v         REAL, thd_i   REAL,
  harmonics     JSONB,
  PRIMARY KEY (device_id, ts)
);
SELECT create_hypertable('telemetry.pq_sample','ts',chunk_time_interval => INTERVAL '1 day');
```

Continuous aggregates:
- `telemetry.pq_1min`
- `telemetry.pq_15min`
- `telemetry.pq_hourly`
- `telemetry.pq_daily`

Retention:
- raw `pq_sample` — 90 days
- `pq_15min` — 5 years
- `pq_daily` — indefinite

### 5.2 `telemetry.energy_register`
| ts | device_id | kwh_imp | kwh_exp | kvarh_imp | kvarh_exp |

Hypertable, chunked `7 days`.

### 5.3 `telemetry.breaker_state`
| ts | breaker_id | state (`open`/`closed`/`tripped`) | trip_cause TEXT NULL | contact_source TEXT |

Hypertable, chunked `1 day`.

### 5.4 `telemetry.lighting_state`
| ts | circuit_id | state | current_a |

## 6. Events

### 6.1 `events.event`
| Column | Type |
|---|---|
| `id` | `bigserial` PK |
| `ts` | `timestamptz` |
| `asset_id` | `uuid` |
| `severity` | ENUM (`info`,`warning`,`error`,`critical`) |
| `kind` | `text` |
| `message` | `text` |
| `payload` | `jsonb` |
| `acknowledged_by` | `uuid` NULL |
| `acknowledged_at` | `timestamptz` NULL |

### 6.2 `events.threshold`
Per-asset or per-class alarm thresholds with 6-band hysteresis pattern.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `asset_id` | `uuid` NULL | NULL = class-wide default |
| `asset_class` | `text` NULL | e.g. `breaker`, `measuring_device` |
| `metric` | `text` | e.g. `v_l1_n`, `pf_total`, `thd_v` |
| `warning_low` | `real` NULL | |
| `warning_high` | `real` NULL | |
| `error_low` | `real` NULL | |
| `error_high` | `real` NULL | |
| `critical_low` | `real` NULL | |
| `critical_high` | `real` NULL | |
| `hysteresis` | `real` DEFAULT 0 | Prevents flapping |
| `enabled` | `boolean` DEFAULT true | |
| `created_at` / `updated_at` | `timestamptz` | |

CHECK constraint `threshold_band_order` enforces: `critical_low <= error_low <= warning_low <= warning_high <= error_high <= critical_high` (NULLs are allowed and skip the check).

## 7. Reporting

- `reports.template` — definition + query + output format.
- `reports.schedule` — cron-like schedule with distribution list.
- `reports.artefact` — generated PDFs/CSVs with hash and retention policy.

## 8. Canvas & Spatial Mapping

The SCADA GUI provides two interactive visual canvases, both driven from database-stored geometry so they can be updated when the mall changes without code deployments.

### 8.1 `assets.canvas`
Top-level container for each visual view. One row per canvas.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `code` | `text` UNIQUE NOT NULL | `'sld_topology'`, `'floor_plan'` |
| `name` | `text` NOT NULL | Human-readable label |
| `description` | `text` NULL | |
| `svg_path` | `text` NOT NULL | Path to the base SVG file (e.g. `canvases/sld_topology.svg`) |
| `width` | `int` NOT NULL | Intrinsic width of the SVG viewBox (px) |
| `height` | `int` NOT NULL | Intrinsic height of the SVG viewBox (px) |
| `default_zoom` | `real` DEFAULT 1.0 | Initial zoom level on load |
| `min_zoom` | `real` DEFAULT 0.2 | Minimum zoom (zoomed out) |
| `max_zoom` | `real` DEFAULT 5.0 | Maximum zoom (zoomed in) |
| `version` | `int` DEFAULT 1 | Incremented when SVG or layout changes |
| `created_at` / `updated_at` | `timestamptz` | |

Seed rows:
- `sld_topology` — derived from 643.E.300 overview SLD
- `floor_plan` — derived from 2239-100-0-Overall Floor Plan-Rev H

### 8.2 `assets.canvas_layer`
Each canvas has multiple toggleable layers. Layers control visibility and z-order of hotspot groups.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `canvas_id` | `uuid` FK → `assets.canvas` NOT NULL | |
| `code` | `text` NOT NULL | e.g. `'main_boards'`, `'breakers'`, `'tenants'`, `'lighting'`, `'cables'`, `'pq_zones'` |
| `name` | `text` NOT NULL | Display label |
| `description` | `text` NULL | |
| `z_order` | `int` NOT NULL DEFAULT 0 | Higher = rendered on top |
| `visible_by_default` | `boolean` DEFAULT true | |
| `min_zoom_visible` | `real` NULL | Layer auto-hides below this zoom (LOD) |
| `max_zoom_visible` | `real` NULL | Layer auto-hides above this zoom |
| `style` | `jsonb` DEFAULT '{}' | Default fill/stroke/opacity for hotspots in this layer |
| `created_at` / `updated_at` | `timestamptz` | |

UNIQUE constraint: `(canvas_id, code)`.

**Typical layers per canvas:**

SLD Topology canvas:
- `transformer` — HV/MV transformer symbol
- `main_boards` — 9 MB nodes
- `breakers` — 104 outgoing + 9 incomer nodes
- `cables` — cable run lines between nodes
- `measuring_devices` — M4M 30 / Ekip Com positions
- `alarms` — overlay for active alarm badges

Floor Plan canvas:
- `building_shell` — walls, corridors, structural outline
- `tenant_zones` — tenant areas (polygons with fill colour by state)
- `main_boards` — MB room locations
- `distribution_boards` — DB physical positions
- `lighting` — lighting circuit zones
- `emergency` — fire, emergency paths, essential supply zones

### 8.3 `assets.canvas_hotspot`
Each hotspot is a clickable/hoverable region on a canvas that links to an asset. This is the bridge between the visual layer and the asset registry.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `layer_id` | `uuid` FK → `assets.canvas_layer` NOT NULL | |
| `asset_id` | `uuid` NULL | FK to the linked asset (breaker, MB, DB, tenant, circuit) |
| `asset_type` | `text` NULL | `'main_board'`, `'breaker'`, `'distribution_board'`, `'tenant_feed'`, `'lighting_circuit'`, `'measuring_device'` |
| `label` | `text` NOT NULL | Display label on hover/tooltip |
| `shape` | `text` NOT NULL | `'rect'`, `'circle'`, `'polygon'`, `'path'`, `'line'` |
| `geometry` | `jsonb` NOT NULL | Shape-specific coordinates (see below) |
| `anchor_x` | `real` NOT NULL | Tooltip/label anchor point X (SVG coords) |
| `anchor_y` | `real` NOT NULL | Tooltip/label anchor point Y (SVG coords) |
| `style_default` | `jsonb` DEFAULT '{}' | Override: fill, stroke, opacity for normal state |
| `style_active` | `jsonb` DEFAULT '{}' | Override: when asset has active alarm |
| `style_selected` | `jsonb` DEFAULT '{}' | Override: when user has selected this hotspot |
| `nav_targets` | `jsonb` DEFAULT '[]' | Array of `{canvas_code, hotspot_id}` — click-through navigation links |
| `tooltip_template` | `text` NULL | Handlebars-style template for tooltip content |
| `sort_order` | `int` DEFAULT 0 | Within the layer |
| `created_at` / `updated_at` | `timestamptz` | |

**Geometry JSONB format by shape:**

```json
// rect
{"x": 120, "y": 340, "width": 80, "height": 40}

// circle
{"cx": 200, "cy": 400, "r": 20}

// polygon (tenant floor area, zone boundary)
{"points": [[x1,y1], [x2,y2], [x3,y3], ...]}

// path (cable run, electrical routing line)
{"d": "M 100 200 L 300 200 L 300 400"}

// line (simple connection)
{"x1": 100, "y1": 200, "x2": 300, "y2": 200}
```

Indexes:
- `(layer_id)` — btree, for layer-based queries
- `(asset_id, asset_type)` — btree, for "find hotspot for this asset" reverse lookup
- `(layer_id, sort_order)` — for ordered rendering

### 8.4 `assets.canvas_nav_route`
Pre-defined navigation routes between canvases. Enables drill-down from the SLD view into the floor plan (and vice versa) centred on the relevant asset.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `from_canvas_id` | `uuid` FK → `assets.canvas` | |
| `from_hotspot_id` | `uuid` FK → `assets.canvas_hotspot` NULL | NULL = canvas-level link |
| `to_canvas_id` | `uuid` FK → `assets.canvas` | |
| `to_hotspot_id` | `uuid` FK → `assets.canvas_hotspot` NULL | NULL = centre on canvas |
| `to_zoom` | `real` NULL | Zoom level to set on navigation |
| `label` | `text` NOT NULL | e.g. "Show on floor plan", "Show SLD" |
| `icon` | `text` NULL | e.g. `'map-pin'`, `'zap'` (Lucide icon name) |
| `created_at` | `timestamptz` | |

This table drives the "Show on Floor Plan" / "Show on SLD" buttons in the asset detail panel.

### 8.5 Canvas Data Flow

```
Source PDFs                  Database                      Frontend
─────────────               ──────────                    ────────
643.E.300 SLD PDF  ──┐
                     ├──►  assets.canvas (2 rows)
Floor Plan PDF     ──┘     assets.canvas_layer (12+ rows)
                           assets.canvas_hotspot (200+ rows)
                           assets.canvas_nav_route (100+ rows)
                                    │
                                    ▼
                           GET /api/canvases/{code}
                           Returns: canvas + layers + hotspots
                                    │
                                    ▼
                           React SVG renderer:
                           ┌─────────────────────────────────┐
                           │ <svg viewBox="0 0 W H">         │
                           │   <image href={base_svg} />     │
                           │   {layers.map(layer =>           │
                           │     <g id={layer.code}           │
                           │        visibility={toggle}>      │
                           │       {hotspots.map(hs =>        │
                           │         <HotspotShape            │
                           │           geometry={hs.geometry}  │
                           │           fill={stateColor(hs)}  │
                           │           onClick={navigate(hs)} │
                           │         />                       │
                           │       )}                         │
                           │     </g>                         │
                           │   )}                             │
                           │ </svg>                           │
                           └─────────────────────────────────┘
                           d3-zoom handles pan/zoom
                           WebSocket updates recolour hotspots
                           by asset state in real-time
```

### 8.6 Canvas Preparation Process

**SLD Topology canvas (from 643.E.300):**
1. Export 643.E.300 PDF to clean SVG (via Inkscape CLI: `inkscape --export-type=svg`)
2. Clean SVG: remove text labels (will be rendered dynamically), keep structural lines
3. Upload cleaned SVG to object storage, register in `assets.canvas`
4. For each MB node: create a `canvas_hotspot` with rect geometry at its position on the SLD
5. For each breaker outgoing: create hotspot positioned along the feeder strip
6. For each cable run: create path hotspot tracing the cable route
7. Create `canvas_nav_route` rows linking each MB hotspot to its corresponding floor plan location

**Floor Plan canvas (from 2239-100-0):**
1. Export floor plan PDF to clean SVG
2. Clean SVG: keep walls/corridors/structure, remove furniture/decoration
3. Upload to object storage, register in `assets.canvas`
4. For each tenant: create polygon hotspot tracing the tenant's lease boundary
5. For each MB room: create rect hotspot at the electrical room location
6. For each DB: create circle hotspot at its physical wall-mounted position
7. Create `canvas_nav_route` rows linking each tenant zone back to its breaker on the SLD

**Re-mapping when mall changes:**
- New tenant → add polygon hotspot to floor plan tenant_zones layer + link to new `assets.tenant_feed`
- Tenant expands → update polygon geometry in `canvas_hotspot`
- New DB installed → add hotspot on both canvases + nav_route link
- Layout renovation → re-export floor plan SVG, update canvas `svg_path` + increment `version`, re-position affected hotspots

## 9. Indexes & Performance

**FK indexes (all btree):**
- `assets.breaker(main_board_id)`, `assets.breaker(mp_code)`, `assets.breaker(device_ip)`
- `assets.measuring_device(main_board_id)`
- `assets.mp_function(mp_code)`
- `assets.distribution_board(fed_by_breaker_id)`
- `assets.tenant_feed(fed_by_breaker_id)`
- `assets.lighting_circuit(distribution_board_id)`
- `assets.canvas_hotspot(layer_id)`, `(asset_id, asset_type)`, `(layer_id, sort_order)`

**Telemetry indexes (critical for performance):**
- `telemetry.breaker_state(breaker_id, ts DESC)` — "last known state" lookup for dashboard
- `events.event(asset_id, ts DESC)` — asset detail panel event history

**Event indexes:**
- `events.event(ts DESC, severity) WHERE acknowledged_at IS NULL` — live alarm pane (partial index)
- `events.event(ts DESC)`, `events.event(asset_id)`, `events.event(severity)`

**Threshold indexes:**
- `events.threshold(asset_id)`, `events.threshold(asset_class) WHERE asset_class IS NOT NULL`

**Audit log indexes:**
- `core.audit_log(ts DESC)`, `core.audit_log(user_id)`, `core.audit_log(asset_id)`

**Continuous aggregates** use `materialized_only = false` so the live dashboard falls through to raw data when aggregates are stale.

## 10. Row-Level Security

RLS is enabled on:
- `core.users` — Contains password hashes and MFA secrets; users see own record, admins see all
- `core.session` — Contains refresh token hashes; users see own sessions, admins see all
- `core.invite` — Contains invite token hashes; admins only
- `core.password_reset` — Contains reset token hashes; users see own, admins see all
- `core.audit_log` — Admins see all, operators see own actions, viewers see own actions
- `events.event` — All authenticated users SELECT; operators and admins can UPDATE (acknowledge)
- `telemetry.pq_sample`, `telemetry.energy_register`, `telemetry.breaker_state`, `telemetry.lighting_state` — All authenticated users SELECT (no INSERT/UPDATE from application; edge gateway writes via service role)

All connections authenticate as a low-privilege role (`scada_app`). The edge gateway telemetry writer uses a dedicated `scada_writer` role that bypasses RLS on telemetry tables. Migration runner elevates to `scada_admin` via `SET ROLE`. RLS policies are created during Phase 1 auth build using `current_setting('app.current_user_id')` set per-request by FastAPI middleware.

## 11. Triggers

`updated_at` trigger (`update_updated_at()` function) applied to: `core.users`, `assets.main_board`, `assets.breaker`, `assets.measuring_device`, `assets.distribution_board`, `assets.tenant_feed`, `assets.lighting_circuit`, `events.threshold`.

## 12. Idempotent Write Pattern

All telemetry inserts from the edge gateway use `INSERT ... ON CONFLICT (device_id, ts) DO NOTHING` (or `(breaker_id, ts)` / `(circuit_id, ts)`) to handle duplicate writes during buffer re-flush after VPN reconnection. This is a critical requirement from the Architecture Review — without it, VPN drops during buffer flush produce duplicate rows that inflate energy calculations and distort aggregates.
