# BUILD HANDOFF — Kingswalk SCADA Monitoring System

**Date:** 2026-04-11
**For:** The coding session (Claude) that will build this system
**From:** Arno (Watson Mattheus Consulting Electrical Engineers)

This is the "start here" document. Read this first, then read the source documents it references. Everything you need to build the Kingswalk SCADA monitoring system is in this folder.

---

## 1. WHAT YOU ARE BUILDING

A web-based SCADA **monitoring** GUI for a shopping centre electrical installation. The system reads data from ~150 ABB field devices across 9 main switchboards, stores telemetry in the cloud, and presents live state, alarms, and historical trends to operators via a browser.

**MONITORING ONLY.** This system observes, records, and alerts. It never sends control commands to field equipment. Modbus write function codes (FC06/FC16) are explicitly forbidden. All physical switching is done on site by authorised personnel.

**The single most important feature** is the 48V relay bypass detection alarm. When a contractor bypasses the load-shedding relay (so non-essential loads run on the generator during a mains failure), the system must detect this and raise a CRITICAL alarm. This is the core business case — the reason the client is paying for SCADA.

---

## 2. THE DOCUMENTS (read in this order)

| Order | Document | What it tells you |
|---|---|---|
| 1 | **This file** | Context, constraints, what to watch out for |
| 2 | **SPEC.md** (v4.0) | The master specification — every requirement, every table, every protocol, every constraint. This is the single source of truth. |
| 3 | **BUILD_STRATEGY.md** (v3) | How to build it: 6 phases across R1/R2/R3, skill map, coding standards, quality gates, CI/CD, deployment model |
| 4 | **DB_SCHEMA.md** | Database schema reference — 5 schemas, all tables, all columns, design principles |
| 5 | **db/migrations/0001_initial.sql** | Base migration — run this first |
| 6 | **db/migrations/0001a_schema_review_fixes.sql** | Schema review fixes — run after 0001. Adds user lifecycle tables, 6-band thresholds, missing indexes, RLS, triggers |
| 7 | **design/sld_per_mb_extract.json** | The asset truth — 104 breakers, 9 main boards, machine-readable. Every asset reference in your code must trace back to this file. |

**Reference documents (read when relevant):**

| Document | When to read it |
|---|---|
| ARCHITECTURE_REVIEW.md | When implementing edge gateway, VPN, PgBouncer, WebSocket reconnection, cloud hosting |
| PRE_MORTEM_ANALYSIS.md | When making risk-tradeoff decisions — 20 failure modes ranked by likelihood × impact |
| ASSUMPTION_MAP.md | When you hit something that doesn't work as expected — 30 assumptions with fallback plans |
| SCHEMA_REVIEW.md | When modifying the database schema — 25 findings, all addressed in 0001a migration |
| SCHEMA_AUDIT_FINAL.md | Second-pass schema audit — 8 new findings, all fixed in 0001a |
| SECURITY_AUDIT_PREBUILD.md | Pre-build security audit — 22 findings (1 CRITICAL, 5 HIGH, 7 MEDIUM). Remediation roadmap maps findings to build phases. **READ DURING PHASE 1.** |
| SPEC_GAP_ANALYSIS.md | Spec completeness gap analysis — 15 gaps measured, 4 CRITICAL, 5 HIGH. Shows what's fully specified vs what needs decisions or build-time resolution. |
| TECHNOLOGY_ASSESSMENT.md | If you're questioning a tech stack choice — 5-year framework evaluation |
| FRONTEND_FRAMEWORK_DECISION.md | If you're questioning the React choice specifically |
| SKILLS.md | Full catalogue of 50 skills with trigger conditions and steps |
| SPRINT_0_TRACKER.md | Pre-build action items that Arno is working on in parallel |

---

## 3. THE HARD CONSTRAINTS

These are non-negotiable. If you find yourself about to violate one, stop and ask.

### 3.1 Timeline
- **R1 MVP deadline:** ~2026-07-18 (14 weeks from build start)
- **R1 scope:** Live breaker state monitoring + alarm notifications (including bypass detection) + continuous PQ data logging
- **R2 (~4 weeks after R1):** Reports, burn hours, switching cycle counters
- **R3 (~8 weeks after R1):** Floor plan canvas, SLD topology canvas, operator training

### 3.2 Monitoring Only — No Control
- Modbus function codes: FC03 (read holding registers) and FC04 (read input registers) ONLY
- FC06 (write single register) and FC16 (write multiple registers) are FORBIDDEN
- No `is_controllable` flag, no control endpoints, no switching UI, no command-readback logic
- If you see "breaker control" or "lighting control" in any older document, ignore it — it was removed from scope

### 3.3 Data Truth Chain
```
SLD drawings (PDF) → sld_per_mb_extract.json → PostgreSQL seed → API → Browser
```
No asset data is ever hardcoded in frontend or backend code. If the JSON extract doesn't have it, it doesn't exist. If you can't verify a Modbus register address against ABB documentation, use `# TODO: VERIFY_REGISTER` — never guess.

### 3.4 Architecture
- **Frontend:** React 19 + Vite + TypeScript strict + Zustand + Tailwind + Radix UI
- **Backend:** FastAPI + Python 3.12+ + SQLAlchemy 2.0 async + Pydantic v2
- **Database:** PostgreSQL 16 + TimescaleDB 2.x (hypertables for telemetry) + Redis 7 (cache + pub/sub)
- **Edge:** Python async poller (pymodbus) on an on-site device, connects to cloud via WireGuard VPN
- **Hosting:** Vercel (frontend CDN) + Railway/VPS (backend Docker) + managed PG + managed Redis
- **Region:** AWS af-south-1 or Azure South Africa North

### 3.5 Quality Gates (every PR)
1. All tests pass (pytest + Vitest)
2. Type checking clean (mypy strict + tsc strict)
3. Lint clean (ruff + ESLint)
4. Coverage >= 80%
5. No hardcoded secrets
6. RBAC on all protected endpoints
7. Audit logging on all mutations
8. All asset refs validated against sld_per_mb_extract.json

---

## 4. THE ARCHITECTURE AT A GLANCE

```
┌──────────────────────────────────────────┐
│  BROWSER (React SPA on Vercel CDN)       │
│  — role-aware dashboards                 │
│  — floor plan + SLD canvases (R3)        │
│  — WebSocket for live state updates      │
└─────────────────┬────────────────────────┘
                  │ HTTPS / WSS (TLS 1.3)
════════════════════════════════════════════ CLOUD
┌─────────────────┴────────────────────────┐
│  FastAPI backend (Docker container)      │
│  — REST API + WebSocket endpoints        │
│  — RBAC + audit + Pydantic validation    │
│  — Report worker (arq, separate process) │
└────────┬────────────────────┬────────────┘
         │                    │
┌────────┴──────────┐ ┌──────┴──────────┐
│ PostgreSQL 16     │ │ Redis 7         │
│ + TimescaleDB 2.x │ │ — state cache   │
│ + PgBouncer       │ │ — WS pub/sub    │
│ (via managed host)│ │ — session store  │
└────────┬──────────┘ └─────────────────┘
         │
══════════╪══════════════════════════════════ WIREGUARD VPN
         │
┌────────┴─────────────────────────────────┐
│  Edge gateway (on-site, Python)          │
│  — 9 async Modbus TCP polling loops      │
│  — systemd supervised (WatchdogSec=30)   │
│  — SQLite local buffer for VPN outages   │
│  — rate-limited buffer flush on reconnect│
│  — /health endpoint                      │
└────────┬─────────────────────────────────┘
         │ Ethernet (SCADA VLANs 10.10.XX.0/24)
┌────────┴─────────────────────────────────┐
│  9 Main Boards × ABB field devices:      │
│  — Ekip Com gateways (.10)               │
│  — M4M 30 network analysers (.100, .101) │
│  — 104 Tmax XT trip units (.11+)         │
│  — 3 Emax 2 ACBs (TS2 anchor feeders)   │
└──────────────────────────────────────────┘
```

---

## 5. THE BUILD PHASES (R1 only — your first 14 weeks)

### Phase 1: Foundation, Auth & Infrastructure (Weeks 1–3)
**Goal:** Monorepo scaffold, CI/CD green, cloud infra running, full auth lifecycle working, deployed to Vercel preview.

Key outputs:
- Monorepo: `/api`, `/web`, `/edge`, `/db`
- PostgreSQL + TimescaleDB + PgBouncer configured
- FastAPI skeleton with health check, CORS, structured logging, error handling
- React shell with Vite, Tailwind, Radix, React Router
- GitHub Actions CI: lint → type → test → security → build → deploy
- Vercel preview deployments per PR
- Auth: JWT + refresh tokens, argon2id, TOTP MFA, invite flow, password reset, RBAC middleware, session management
- Rate limiting on auth endpoints (5/IP/15min)
- Email service (Resend) for transactional email
- Audit log middleware (every mutation → `core.audit_log`)
- Login + MFA + admin user management UI

**SPEC sections:** B.2, B.3, B.3.2–B.3.6, C.1

### Phase 2: Real-Time Monitoring Core (Weeks 4–8)
**Goal:** Edge gateway polling all 9 VLANs, live breaker state flowing to cloud and browser, bypass detection active, alarms triggering.

Key outputs:
- Asset seed migration from `sld_per_mb_extract.json` (104 breakers, 9 MBs)
- Asset registry CRUD API
- Edge gateway: per-VLAN async Modbus polling with priority scheduler
- Edge gateway: systemd service with watchdog, health endpoint, local SQLite buffer
- VPN: WireGuard with PersistentKeepalive=25, dual-path failover
- Cloud-side watchdog alarm (CRITICAL if no telemetry >30s)
- WebSocket layer: per-MB pub/sub via Redis, JWT auth, exponential backoff reconnection
- Telemetry ingestion endpoint with mTLS
- Breaker state monitoring + state transition logging
- **48V relay bypass detection** (CRITICAL alarm with operator context)
- Communication loss vs equipment fault distinction
- Event system (severity, routing, thresholds with hysteresis)
- Notification service (in-app toast + email + SMS)
- Tiered escalation (15min → operator SMS, 30min → admin SMS)
- Live alarm panel with acknowledge workflow
- Live monitoring dashboard
- Modbus simulator for dev/test

**SPEC sections:** B.3.2, B.4, B.5, B.6, C.2, C.3, C.6

**WARNING:** Bypass detection (Assumption #3) depends on Arno confirming that the 48V relay command state is readable. Check SPRINT_0_TRACKER.md Action 1 before implementing. If the answer is NO, an inference-based approach is needed — see ASSUMPTION_MAP.md §Assumption #3.

### Phase 3: Power Quality & Data Logging (Weeks 9–12)
**Goal:** Full PQ data pipeline, continuous aggregates, historical trend charts.

Key outputs:
- PQ sample ingestion from M4M 30 devices (`telemetry.pq_sample` hypertable)
- Energy register logging (`telemetry.energy_register`)
- Lighting state monitoring with burn hour accumulation
- TimescaleDB continuous aggregates: pq_1min, pq_15min, pq_hourly, pq_daily
- Aggregate refresh after buffer flush (`CALL refresh_continuous_aggregate()`)
- Retention policies: raw 90 days, 15min 5 years, daily indefinite
- Report worker separation (arq, statement_timeout=120s)
- PQ trend charts (Recharts/ECharts) with date range and asset selector
- Device replacement tracking UI

**SPEC sections:** B.4 (telemetry schema), C.3, C.4

### Phase 4: Commissioning Testing & R1 Hardening (Weeks 13–14)
**Goal:** R1 MVP hardened, tested against real ABB hardware (if available), ready for production.

Key outputs:
- Integration testing against first live main board (if commissioned by Profection)
- Load testing (28 users, 150 WS connections, k6)
- Full security audit (OWASP top 10, auth flows, mTLS, CORS)
- POPIA compliance review
- API documentation (OpenAPI auto-generated + narrative)
- Operator quick-start guide
- Production deployment (Vercel + Docker backend + managed PG/Redis)
- Infrastructure monitoring (edge health, VPN state, PG connections, disk)
- Hallucination audit (all asset refs match extract, all queries match schema)
- Dependency audit (all deps current, no known CVEs)

**Commissioning acceptance criteria (all must pass):**
1. All 104 breakers reporting state within <1s latency
2. All M4M 30 PQ readings logging correctly
3. All configured alarms triggering on simulated events
4. Bypass detection correctly identifying simulated bypass
5. Comms loss correctly distinguished from equipment fault
6. Escalation delivering through all channels
7. All user roles functioning correctly
8. Edge gateway retains data during simulated internet outage

**SPEC sections:** D.3, Part E

---

## 6. THE DATABASE (5 schemas)

| Schema | Purpose | Key tables |
|---|---|---|
| `core` | Users, auth, audit, config | users, audit_log, config, invite, password_reset, session, notification_preference |
| `assets` | Physical equipment registry | main_board, breaker, measuring_device, distribution_board, tenant_feed, lighting_circuit, measuring_package, asset_document, canvas, canvas_layer, canvas_hotspot |
| `telemetry` | Time-series data (hypertables) | pq_sample, energy_register, breaker_state, lighting_state |
| `events` | Alarms, trips, transitions | event, threshold, alarm_ack |
| `reports` | Scheduled reports | template, schedule, artefact |

**Critical schema details:**
- Thresholds use a **6-band pattern**: warning_low/high, error_low/high, critical_low/high + hysteresis per band
- All FK columns have explicit indexes
- RLS enabled on security-sensitive tables (audit_log, event, pq_sample, energy_register, breaker_state, lighting_state)
- `updated_at` columns maintained by database triggers
- Telemetry writes use `ON CONFLICT (device_id, ts) DO NOTHING` for idempotency

**Migrations to run in order:**
1. `db/migrations/0001_initial.sql`
2. `db/migrations/0001a_schema_review_fixes.sql`
3. `db/migrations/0002_canvas_layers.sql` (pending — create in Phase 6/R3)
4. `db/migrations/0003_asset_documents.sql` (pending — create in Phase 2)

---

## 7. THE FIELD DEVICES (what you're polling)

**Per main board (9 boards total):**

| Device | IP scheme | Protocol | What it gives you |
|---|---|---|---|
| Ekip Com gateway | .10 | Modbus TCP | Aggregates all trip unit data on this board |
| M4M 30 analyser #1 | .100 | Modbus TCP | V, I, P, Q, S, PF, THD, harmonics, energy registers |
| M4M 30 analyser #2 | .101 | Modbus TCP | Same as above (second analyser on larger boards) |
| Tmax XT trip units | .11+ | Via Ekip Com | Breaker open/closed/tripped state, trip cause, operational counters |
| Emax 2 ACBs (TS2 only) | .11+ | IEC 61850 / Modbus | Anchor feeder breakers — dual protocol on TS2 boards |

**Asset count:** 104 outgoing breakers, 9 main boards, 18 M4M 30 analysers, 9 Ekip Com gateways.

**Polling priorities (per VLAN):**
1. Breaker state: 250ms
2. Instantaneous PQ: 1s
3. THD: 5s
4. Energy registers: 30s
5. Operational counters: 60s

**IP addressing:** `10.10.{VLAN_ID}.{host}` — exact subnets and VLANs per MB are in the `main_board` table seed data and in SPEC.md §B.5.

---

## 8. THINGS THAT WILL BITE YOU

These are the known risks and gotchas extracted from the pre-mortem, architecture review, and assumption map. Read these before you start each phase.

### 8.1 Register Addresses Are Unconfirmed
Every Modbus register address in the codebase should be treated as provisional until Profection provides the actual register map. Use `# TODO: VERIFY_REGISTER — address 0xNNNN assumed from ABB datasheet, confirm with Profection register map` on every register reference. The Modbus simulator should use the same provisional addresses so that when the real map arrives, you only change the address constants in one place.

### 8.2 Bypass Detection Has an Open Question
The bypass detection logic requires two inputs: actual breaker state (Modbus — confirmed possible) and relay command state (source unknown). Check SPRINT_0_TRACKER.md Action 1 before implementing. Build the comparison logic with a pluggable "relay state source" interface so the implementation can be swapped without restructuring.

### 8.3 Profection Is a Single Point of Failure
Profection holds: register maps, VLAN implementation, bench hardware, commissioning schedule, and the 48V relay answer. If they are slow, everything downstream is delayed. Build against the Modbus simulator and design for late integration — all register addresses as config, not code.

### 8.4 No DevOps Person
There is no dedicated DevOps or DBA on this project. The CI/CD pipeline, Docker configuration, database backups, and monitoring must be self-managing and well-documented. Prefer managed services (Supabase, Railway) over self-hosted infrastructure.

### 8.5 Operators Have Zero Training
The 3 operator users are new hires who will not know the building. Every alarm, every dashboard view, every notification must be self-explanatory. Asset location breadcrumbs with plain-language descriptions ("MB 2.1, Row 3, feeds Pick n Pay cold room"), recommended response actions, escalation paths. Design for someone who just walked in the door.

### 8.6 The Edge Gateway Device Doesn't Exist Yet
As of today, no edge gateway hardware has been specified or ordered. Code the edge gateway to run on any Linux box with Python 3.12 and network access. Avoid hardware-specific dependencies. See SPRINT_0_TRACKER.md Action 3.

### 8.7 Internet May Not Be Available at Commissioning
Design the edge gateway to operate in disconnected mode indefinitely — local SQLite buffer with unlimited growth (up to disk capacity), automatic flush when VPN reconnects. The system should degrade gracefully: operators see "Edge Gateway Offline" in the UI, but when connectivity returns, all buffered data flows in and the historical record is complete.

### 8.8 Security Audit Findings Require Phase 1 Attention
The pre-build security audit (SECURITY_AUDIT_PREBUILD.md) found 22 findings. The CRITICAL and HIGH items that must be addressed during Phase 1 auth build:
- **F1:** MFA secrets must be AES-256-GCM encrypted before storage (encryption key in secrets manager, not env vars).
- **F2:** RLS is enabled on 11 tables but has ZERO policies defined. You must create concrete RLS policies during Phase 1 — not defer.
- **F3:** Use HttpOnly/Secure/SameSite=Strict cookies for JWT storage. Implement double-submit CSRF token for non-GET requests.
- **F4:** JWT algorithm must be HS256 with ≥256-bit secret. Validate exp/iss/aud on ALL tokens. Invite tokens are one-time-use.
- **F5:** Password reset endpoint must not enumerate users. Rate limit 3/email/hour.
- **F6:** Edge-to-cloud uses mTLS (decision is made — not "or API key"). Implement in Phase 2.
- **F10:** Recovery codes table (`core.recovery_code`) added to 0001a migration. Implement argon2id hashing.
- **F11:** REVOKE DELETE/UPDATE on `core.audit_log` from the application role. INSERT-only.
- **F13:** Create three database roles: `scada_app`, `scada_writer`, `scada_reader` with least-privilege grants.

All specifications for these have been added to SPEC.md §A.5 and §C.1. Read the full audit for implementation details.

---

## 9. CODING WORKFLOW

```
1. Read the relevant SKILL.md file(s) before writing any code
2. Plan scope, inputs, outputs
3. Implement following the skill and BUILD_STRATEGY coding standards
4. Run unit tests (pytest / vitest)
5. Run integration tests
6. Run full test suite
7. Run code review checklist (BUILD_STRATEGY §4.2)
8. If any gate fails → return to step 3 (max 3 iterations, then flag for Arno)
9. Update documentation
10. Atomic commit with descriptive message
11. Deploy to Vercel preview, smoke test
```

**When uncertain about a register, electrical value, or protocol detail:** insert `# TODO: VERIFY` and flag to Arno. Never guess. Never fabricate.

---

## 10. FILE STRUCTURE (target)

```
kingswalk-scada/
├── api/                          # FastAPI backend
│   ├── app/
│   │   ├── core/                 # Config, auth, logging, errors, email
│   │   ├── routes/               # HTTP route handlers (thin)
│   │   ├── services/             # Business logic (no I/O)
│   │   ├── repos/                # Database access (SQLAlchemy)
│   │   └── ws/                   # WebSocket handlers
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── web/                          # React frontend
│   ├── src/
│   │   ├── core/                 # Models, API client, WS manager (NO React imports)
│   │   ├── stores/               # Zustand stores (NO React imports)
│   │   └── ui/                   # Components, pages, hooks (React-specific)
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── edge/                         # On-site Modbus gateway
│   ├── poller/                   # Per-VLAN async polling loops
│   ├── buffer/                   # SQLite local buffer + flush logic
│   ├── simulator/                # Mock Modbus devices for dev
│   ├── tests/
│   └── pyproject.toml
├── db/
│   ├── migrations/               # Numbered SQL migrations
│   └── seeds/                    # Test data fixtures
├── design/
│   ├── sld_per_mb_extract.json   # Asset truth (104 items)
│   ├── SLD_FIELD_MAP.xlsx        # Master inventory workbook
│   └── sld_overview_extract.json
├── .github/workflows/            # CI/CD
├── docker-compose.yml            # Local dev environment
├── vercel.json                   # Frontend deployment config
└── README.md
```

**Rule:** `/web/src/core/` and `/web/src/stores/` must have zero React imports. These are framework-agnostic. Only `/web/src/ui/` imports React.

---

## 11. USERS

| Role | Count | Capability |
|---|---|---|
| Admin | 5 | Everything: user management, thresholds, asset registry, reports, system config |
| Operator | 3 | View all, acknowledge alarms, run on-demand reports. No control. |
| Viewer | 20 | Read-only: dashboards, trends, floor plan, download reports |

---

## 12. WHAT SUCCESS LOOKS LIKE

At the end of 14 weeks (R1), a control room operator opens a browser and sees:
- All 104 breakers with live open/closed/tripped state, updating within 1 second
- A red pulsing alarm if someone bypasses the load-shedding relay on any essential supply breaker
- A grey "COMMS LOSS" overlay on any device that stops responding
- Power quality readings from all 18 M4M 30 analysers
- Historical trend charts for voltage, current, power factor, THD
- SMS and email alerts escalating through the notification chain
- An audit trail of every alarm, every acknowledgement, every user action

The system works even if the internet drops — data buffers locally and flows in when connectivity returns.

---

**Now read SPEC.md. That's where all the detail lives.**
