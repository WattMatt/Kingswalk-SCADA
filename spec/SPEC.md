# Kingswalk Mall SCADA GUI — Master Specification & Orchestration Document

**Document owner:** Watson Mattheus Consulting Electrical Engineers
**Site:** Kingswalk Shopping Centre, Savannah, South Africa
**Version:** 5.0 (2026-04-13)
**Change log (v5.0):** Consolidated findings from architecture review, pre-mortem, security audit, schema audits, gap analysis, and assumption map. Resolved all "or" decisions. Added viewer access scope, edge hardware spec, structured logging, harmonics format, continuous aggregate refresh, and POPIA data register. All companion documents now referenced in Part G.
**Purpose:** Single authoritative source from which an AI coding session or implementation team builds, tests, deploys, and maintains the SCADA web interface. Every skill trigger, every test loop, every database structure, every tech stack choice is documented explicitly. Nothing is assumed complete unless fully tested repeatedly and confirmed.
**System scope:** MONITORING ONLY — this system observes, records, and alerts. All physical switching is performed on site by authorised personnel. Remote control of breakers and lighting is permanently out of scope.

**Project folder:** `009. SCADA/KINGSWALK SCADA GUI/`

**Companion documents (see Part G for full list):**
| Document | Purpose |
|---|---|
| `BUILD_HANDOFF.md` | **START HERE** — single onboarding document for the coding session |
| `BUILD_STRATEGY.md` | 5-phase R1/R2/R3 build timeline with skill assignments |
| `DB_SCHEMA.md` | Database schema reference (5 schemas, 40+ tables) |
| `SPRINT_0_TRACKER.md` | Pre-build action items with owners and deadlines |
| `SECURITY_AUDIT_PREBUILD.md` | 22-finding OWASP security audit with remediation roadmap |
| `SPEC_GAP_ANALYSIS.md` | Spec completeness analysis (15 gaps measured) |
| `ARCHITECTURE_REVIEW.md` | 12 findings across 3 tiers, scalability, security surface |
| `PRE_MORTEM_ANALYSIS.md` | 20 failure modes, top 5 detailed, action list |
| `ASSUMPTION_MAP.md` | 30 assumptions with fallback plans (5 CRITICAL) |
| `SCHEMA_REVIEW.md` + `SCHEMA_AUDIT_FINAL.md` | 25 + 8 schema findings, all resolved in 0001a |
| `TECHNOLOGY_ASSESSMENT.md` | 5-year framework evaluation and TCO comparison |
| `FRONTEND_FRAMEWORK_DECISION.md` | React 19 selection rationale |
| `SKILLS.md` | Detailed catalogue of all 50 skills with steps and usage context |
| `design/SLD_FIELD_MAP.xlsx` | Master asset inventory (8 sheets, 104 items) |
| `design/sld_per_mb_extract.json` | Machine-readable asset truth (104 items) |

**Source documents (sibling folders within `009. SCADA/`):**
| Folder | Contents |
|---|---|
| `DRAWINGS/SCHEMATIC OVERVIEW/` | 10 source SLD PDFs (643.E.300–309, REV. 0) |
| `DRAWINGS/FLOOR PLAN/` | Mall floor plan PDF (Rev H) |
| `EQUIPMENT SPECIFICATIONS/` | ABB datasheets: M4M 30, Ekip Datalogger, PDCOM, Tmax XT, SWICOM |

---

## PART A — AUTOMATION PROTOCOL

This part defines HOW every task is executed. No code is written without following this protocol.

### A.1 Build-Test-Verify Loop

Every coding task follows this mandatory cycle:

```
┌─────────────────────────────────────────────────┐
│  1. READ SKILL    → Load relevant SKILL.md(s)   │
│  2. PLAN          → Define scope, inputs, outputs│
│  3. IMPLEMENT     → Write code following skill   │
│  4. UNIT TEST     → Test in isolation            │
│  5. INTEGRATE     → Test with dependencies       │
│  6. VERIFY        → Run full test suite          │
│  7. REVIEW        → Code review checklist        │
│  8. LOOP BACK     → If any gate fails, return    │
│                     to step 3                    │
│  9. DOCUMENT      → Update docs, ADRs            │
│ 10. COMMIT        → Atomic commit with message   │
│ 11. DEPLOY        → Preview deploy, smoke test   │
└─────────────────────────────────────────────────┘
```

**Gate rules:**
- Steps 4–6 must ALL pass before proceeding to step 7
- Any failure at steps 4–8 sends execution back to step 3
- Step 11 requires all previous steps to pass
- Maximum 3 loop iterations before escalating to human review

### A.2 Skill Trigger Conditions

When a coding session encounters a task, it MUST identify and load the relevant skill(s) BEFORE writing any code. Skills are stored in `/skills/<name>/SKILL.md`. The complete catalogue is in `SKILLS.md`.

**Trigger table (50 skills across 11 categories):**

| Category | Skills | Trigger |
|---|---|---|
| API & Backend | api-endpoint-generator, auth-system-builder, middleware-creator, data-validation-layer, rate-limiter, error-handler, health-check-endpoint, webhook-handler | Any FastAPI route, auth, middleware, or validation task |
| Data & Database | data-schema-designer, data-migration-script, database-query-optimizer, data-pipeline-builder, data-quality-monitor, caching-strategy, mock-data-generator, search-implementer | Any PostgreSQL/TimescaleDB/Redis operation |
| Frontend & UI | web-artifacts-builder, react-component-optimizer, performance-optimizer | Any React component, SVG, chart, or UI task |
| Real-time & Events | dashboard-backend, event-system-designer, state-machine-builder, notification-system-builder | WebSocket, events, state machines, alerts |
| Infrastructure | cicd-pipeline-writer, configuration-system, logging-system, monitoring-alert-system, cron-job-builder, release-management-automation, feature-flag-system | CI/CD, config, logging, monitoring, scheduled tasks |
| Security | security-audit, compliance-checking-ai, code-review-ai | Security review, POPIA/GDPR, automated PR review |
| Testing | unit-test-writer, integration-test-writer, load-testing-script | Any test writing task |
| Reporting | report-generator, report-generation-automator, pdf, xlsx, docx, email-automation-sequence | Reports, exports, document generation |
| Code Quality | code-review, write-documentation, file-upload-handler | Reviews, docs, file uploads |
| Architecture | architecture-review, queue-system-builder | Architecture decisions, background jobs |
| Custom | sld-extraction | PDF drawing extraction, asset registry updates |

### A.3 Hallucination Prevention Protocol

This is a SAFETY-CRITICAL industrial monitoring system. False data can mislead operational decisions. Every implementation must pass these 8 checks:

1. **Data Truth Chain** — Every displayed value must trace back to a physical source: Field device → Modbus/IEC61850 register → Edge gateway → PostgreSQL/TimescaleDB → API response → Browser render. If any link is broken, display "COMMS LOSS" — never show stale data as current.

2. **Register Map Verification** — Every Modbus register address must be verified against the ABB Ekip/M4M 30 documentation. Never assume a register address — always confirm.

3. **Unit Consistency** — Voltages in V (not kV), currents in A, power in kW/kVAR/kVA, energy in kWh, frequency in Hz, THD in %. Every value displayed must include its unit.

4. **Timestamp Integrity** — All timestamps are UTC in the database. Display timezone conversion happens ONLY in the presentation layer. Never store local time.

5. **State Verification** — Breaker states (open/closed/tripped) must reflect the latest polled register value. If a state change is detected, the system logs the transition with timestamp. Never display stale state — if the last poll is older than 2× the poll interval, display "STALE" warning.

6. **Asset Count Validation** — The system has exactly 104 outgoing breakers across 9 Main Boards. If a query returns a different count, flag it as an error. Per-MB counts from SLD: MB 1.1=10, MB 2.1=16, MB 2.2=11, MB 2.3=8, MB 3.1=12, MB 4.1=18, MB 5.1=13, MB 5.2=10, MB 5.3=6.

7. **Measuring Package Fidelity** — All 104 outgoings are MP2 (8 functions). MB 5.3 incomer is MP4 (6 functions). Do not generate data for MP functions that are not assigned to an asset.

8. **Network Address Integrity** — IP addresses follow the scheme 10.10.{VLAN}.{host}. Trip units start at .11 and increment. Never generate or accept an IP outside the assigned subnet for a MB.

### A.4 Code Review Checklist (15 points)

Every PR must pass this checklist before merge:

**Tier 1 — Automated CI (blocks merge):**
1. All unit tests pass (pytest for Python, Vitest for TS)
2. All integration tests pass
3. Linting clean (ruff for Python, eslint for TS)
4. Type checking clean (mypy for Python, tsc for TS)
5. Test coverage ≥80% on changed files

**Tier 2 — AI Code Review (blocks merge):**
6. No hardcoded secrets, credentials, or API keys
7. No SQL injection vectors (all queries parameterised)
8. No XSS vectors (all user input sanitised)
9. RBAC decorators present on all protected endpoints
10. Error handling covers all failure modes

**Tier 3 — Architecture Review (advisory):**
11. Changes align with the framework-agnostic core architecture (70% core / 30% React)
12. New database queries have EXPLAIN ANALYZE results
13. WebSocket broadcasts are throttled appropriately

**Tier 4 — Security Audit (blocks merge for auth changes):**
14. Authentication and RBAC changes reviewed for privilege escalation

**Tier 5 — Domain Review by Arno (blocks merge for schema/protocol changes):**
15. Asset model changes match physical SLD drawings

### A.5 Coding Standards

**Python (FastAPI backend):**
- Python 3.12+, type hints on ALL functions
- async/await for all I/O operations
- SQLAlchemy 2.0 async with Repository pattern
- Pydantic v2 for all request/response models
- ruff for linting + formatting (line length 100)
- mypy strict mode
- pytest with async fixtures
- Docstrings on all public functions (Google style)

**TypeScript (React frontend):**
- TypeScript strict mode, no `any` types
- React 19 functional components only (no class components)
- Zustand for state management (no Redux, no Context for global state)
- Tailwind CSS 4 for styling (no CSS modules, no styled-components)
- Radix UI for accessible primitives
- Zod for runtime validation
- ESLint + Prettier
- Vitest + Testing Library + Playwright
- **Framework-agnostic core:** Business logic (alarm evaluation, threshold comparison, data transforms, WebSocket message parsing) lives in `src/core/` as plain TypeScript modules with zero React imports. React components in `src/ui/` import from `src/core/`. Target: 60–70% of frontend code is framework-agnostic. This enables future migration to Vue/Svelte/Solid if React becomes untenable (see TECHNOLOGY_ASSESSMENT.md exit strategy).

**SQL (PostgreSQL + TimescaleDB):**
- All DDL in versioned migrations under `db/migrations/`
- Never use `CASCADE` on production deletes
- All timestamps TIMESTAMPTZ in UTC
- All foreign keys have explicit ON DELETE behavior
- Indexes on all FK columns
- RLS enabled on security-sensitive tables

**Deployment (cloud-hosted with site edge gateway):**
- Frontend: Vercel (Edge CDN, preview deploys per PR)
- Backend: Railway with Docker (migrate to AWS af-south-1 if latency exceeds 50ms)
- Database: Managed PostgreSQL 16 + TimescaleDB extension (cloud)
- Redis: Managed Redis 7 (cloud)
- Edge gateway: On-site device running Python Modbus poller, connects to cloud via secure VPN/tunnel
- Site-to-cloud link: VPN or WireGuard tunnel from SCADA VLAN to cloud backend
- Latency budget: site-to-cloud round trip must stay within <1s target for state changes
- Secrets: environment variables via Doppler, never in code. Doppler injects secrets into Railway, edge gateway, and CI/CD. Rotate quarterly. Doppler free tier covers this project.
- CORS: Explicitly set origins to the Vercel deployment domain only. Reject all others.
- Edge-to-cloud auth: Mutual TLS (mTLS) on the telemetry ingestion endpoint as defence-in-depth (VPN alone is a single layer). Edge gateway client certificate signed by project-specific CA, stored at `/etc/scada/certs/` with `600` permissions, rotated annually. API key authentication is NOT acceptable for this endpoint.
- Login rate limiting: 5 attempts per IP per 15 minutes (IP-based, in addition to per-account lockout in C.1).
- Password reset rate limiting: 3 reset requests per email per hour. 10 reset requests per IP per hour.

**Security headers (FastAPI middleware):**
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' wss://{domain}; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

**Token storage & CSRF:**
- Access token: `HttpOnly`, `Secure`, `SameSite=Strict` cookie. NOT in localStorage.
- Refresh token: `HttpOnly`, `Secure`, `SameSite=Strict` cookie on `/api/auth/refresh` path only.
- CSRF: `SameSite=Strict` provides primary protection. Double-submit cookie pattern as defence-in-depth for non-GET requests.
- Edge gateway endpoints use mTLS (not cookies) — exempt from CSRF.

**JWT standards (all JWTs — access, refresh, invite):**
- Algorithm: `HS256` with ≥256-bit secret from secrets manager. Reject `alg: none`.
- Validate: `exp`, `iss` (must be `kingswalk-scada`), `aud` (must match token type).
- Access token `aud`: `access`. Refresh token `aud`: `refresh`. Invite token `aud`: `invite`.
- Invite tokens: one-time use — mark invite record as accepted on first use. Reject reuse.
- Library: PyJWT with explicit algorithm whitelist. NEVER decode without verification.

**MFA secret encryption:**
- TOTP secrets encrypted with AES-256-GCM before storage in `core.users.mfa_secret`.
- Encryption key in secrets manager (NOT in env vars, NOT in code, NOT in database).
- Stored format: `base64(nonce || ciphertext || tag)` with `key_version` prefix.
- Key rotation: background job re-encrypts all secrets. Store key_version alongside ciphertext.
- Decrypted TOTP secret NEVER logged, returned in API responses, or cached in Redis.

**Database roles (principle of least privilege):**
- `scada_app` — used by FastAPI. SELECT/INSERT/UPDATE on all tables. No DELETE on `core.audit_log`.
- `scada_writer` — used by edge gateway. INSERT-only on `telemetry.*`. SELECT on `assets.*`. No access to `core.*`, `events.*`, or `reports.*`.
- `scada_reader` — used by report worker. SELECT-only on all tables except `core.password_reset` and `core.session`.
- All three roles: non-superuser, non-createdb, non-createrole.

**Audit log integrity:**
- `REVOKE DELETE, UPDATE ON core.audit_log FROM scada_app;`
- Only DBA role (not used by application) can modify audit records.

**CI security gates:**
- `pip-audit --require-hashes` (Python dependencies)
- `npm audit --audit-level=high` (Node dependencies)
- Lock files (`poetry.lock`, `package-lock.json`) MUST be committed.
- Renovate or Dependabot for automated dependency updates.

**Modbus write prevention (SCADA safety):**
- The pymodbus client wrapper MUST only expose `read_holding_registers()` and `read_input_registers()`.
- Write methods (`write_register`, `write_registers`, `write_coil`, `write_coils`) MUST NOT be imported or callable.
- Implementation: `ReadOnlyModbusClient` wrapper class that delegates only FC03/FC04.
- Unit test: calling any write method raises `RuntimeError`.
- CI gate: ruff rule or grep check that FC06/FC16/write_register never appears in `edge/` code.

---

## PART B — TECHNICAL REQUIREMENTS

### B.1 Actors

| Role | Count | Who | Capability |
|---|---|---|---|
| **Admin** | 5 | Watson Mattheus engineers | User management, threshold config, asset registry edits, report schedules, system config, forensic PQ analysis |
| **Operator** | 3 | Control room staff (new role, to be appointed before go-live) | View everything, acknowledge alarms, run on-demand reports, daily monitoring. **No remote control — all switching on site.** |
| **Viewer** | 20 | Property owners, centre managers | Read-only dashboard, historical trends, floor-plan visualisation, download reports. **Full building visibility** — viewers see all assets, not tenant-scoped. |

**Design for untrained operators:** The Operator role is new — these are hires who will not know the building. Every alarm view must be self-explanatory: asset location breadcrumbs with plain-language descriptions ("MB 2.1, Row 3, feeds Pick n Pay cold room"), recommended response actions, and escalation paths. The system compensates for zero institutional knowledge.

All actions are written to an immutable audit log (`core.audit_log`).

### B.2 Locked Technology Stack

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| Frontend framework | React | 19 | Best WebSocket + SVG + SA talent pool. See TECHNOLOGY_ASSESSMENT.md |
| Bundler | Vite | 6 | Fast HMR, ESM-native |
| Language (FE) | TypeScript | 5.x | Type safety, strict mode |
| State management | Zustand | 5.x | Lightweight, middleware-friendly for WebSocket |
| Styling | Tailwind CSS | 4 | Utility-first, no runtime overhead |
| Component library | Radix UI | latest | Headless, WCAG 2.1 AA accessible |
| Charting | Recharts | latest | React-native charting for PQ trends. Lighter bundle than ECharts; sufficient for R1. |
| SVG floor plan | Custom React SVG + d3-zoom | — | Interactive floor plan with live state overlay |
| Forms | React Hook Form + Zod | latest | Performant forms with runtime validation |
| Routing | React Router | 7 | SPA routing |
| Backend framework | FastAPI | 0.115+ | Async Python, auto OpenAPI docs |
| Language (BE) | Python | 3.12+ | Type hints, async/await |
| ORM | SQLAlchemy | 2.0 async | Repository pattern, Alembic migrations |
| Database | PostgreSQL | 16 | ACID, RLS, JSON, full-text search |
| Time-series | TimescaleDB | 2.x | Hypertables, continuous aggregates, retention |
| Cache / Pub-Sub | Redis | 7 | State cache, WebSocket fan-out bus |
| Auth hashing | argon2id | — | OWASP-recommended password hashing |
| MFA | TOTP | RFC 6238 | Time-based one-time password |
| Email | Resend | — | Transactional email (alerts, reports) |
| SMS | BulkSMS | — | South African SMS gateway |
| Testing (BE) | pytest + httpx | — | Async test client |
| Testing (FE) | Vitest + Testing Library + Playwright | — | Unit + component + E2E |
| CI/CD | GitHub Actions | — | Lint → test → build → deploy |
| Frontend hosting | Vercel | — | Edge CDN, preview deploys |
| Backend hosting | Railway | — | Docker container deployment, South Africa latency via Cloudflare. Migrate to AWS af-south-1 if latency exceeds 50ms. |
| Reverse proxy | Caddy | 2.x | Automatic HTTPS/TLS, simpler config than nginx. Sufficient for this traffic volume. |
| Secrets manager | Doppler | — | Environment variable injection for all services. Free tier covers project scope. |
| Structured logging | structlog | — | JSON-formatted structured logs, shipped to Grafana Loki |

### B.3 System Architecture

```
                    ┌─────────────────────────────────────┐
                    │  React SPA (Vite + TypeScript)      │
                    │  — role-aware dashboards            │
                    │  — floor-plan overlay (SVG + d3)    │
                    │  — live WS state updates (Zustand)  │
                    │  — Vercel Edge CDN                  │
                    └───────────────┬─────────────────────┘
                                    │ HTTPS/WSS (TLS 1.3)
     ═══════════════════════════════╪═══════════════════════  CLOUD
                    ┌───────────────┴─────────────────────┐
                    │  FastAPI backend (Python 3.12)      │
                    │  — REST + WebSocket endpoints       │
                    │  — RBAC middleware + audit logging   │
                    │  — Pydantic v2 validation           │
                    │  — Report generation engine         │
                    │  — Cloud-hosted Docker container    │
                    └───────┬─────────────────┬───────────┘
                            │                 │
        ┌───────────────────┴──┐   ┌──────────┴──────────┐
        │  PostgreSQL 16 +     │   │  Redis 7             │
        │  TimescaleDB 2.x     │   │  — state cache       │
        │  — core schema       │   │  — WS pub/sub bus    │
        │  — assets schema     │   │  — session store     │
        │  — telemetry hyper   │   └──────────────────────┘
        │  — events schema     │
        │  — reports schema    │
        └──────────┬───────────┘
                   │
     ═══════════════╪═══════════════════════════════════════  VPN / TUNNEL
                   │
                ┌──┴─────────────────────────────────────┐
                │  Edge gateway (on-site, Python)         │
                │  — Modbus TCP poller (pymodbus)        │
                │  — IEC 61850 MMS client (for TS2)     │
                │  — pushes telemetry → cloud PG + Redis │
                │  — per-MB VLAN isolation               │
                │  — local buffer for connectivity loss  │
                └────────────────────────┬───────────────┘
                                         │ Ethernet (SCADA VLANs)
        ┌────────────────────────────────┴──────────────────────────┐
        │  ABB field devices per Main Board:                        │
        │  — Ekip Com IP gateway (.10) — aggregates trip units     │
        │  — M4M 30 network analysers (.100, .101)                 │
        │  — Tmax XT trip units (.11+) — 104 outgoing breakers     │
        │  — Emax 2 ACB trip units — 3 anchor feeders (TS2)       │
        └───────────────────────────────────────────────────────────┘
```

**Edge gateway resilience:** The on-site edge gateway includes a local SQLite buffer so that if the VPN tunnel to cloud drops, telemetry is queued locally and synced when connectivity resumes. No data is lost during internet outages. Buffer grows to disk capacity (≥64 GB SSD per §B.3.8). Recovery on restart: edge gateway reads last-flushed timestamp from SQLite, resumes polling, flushes buffered rows on next successful cloud connection.

### B.3.2 Edge Gateway Architecture Requirements (from Architecture Review)

The edge gateway is the sole bridge between ~150 field devices and the cloud. The following are mandatory R1 requirements:

1. **Process supervision:** Run under `systemd` with `Restart=always` and `WatchdogSec=30`. The poller must send a periodic heartbeat via `sd_notify`. If the process crashes, it auto-restarts within seconds.
2. **Health endpoint:** Expose `/health` on localhost reporting: last successful poll timestamp per MB, VPN tunnel status, local buffer depth.
3. **Cloud-side watchdog:** If no telemetry arrives for >30 seconds, the backend raises a CRITICAL alarm ("Edge gateway unresponsive — all monitoring offline").
4. **Per-VLAN async polling:** Each of the 9 VLANs runs its own independent `asyncio` polling loop using `pymodbus.client.AsyncModbusTcpClient`. A stalled device on one VLAN does not block polling on any other VLAN. Modbus TCP socket timeout: 500ms per request. After 3 consecutive timeouts, mark the device as "COMMS LOSS" and skip to the next device.
5. **Polling priority scheduler:** Within each VLAN, prioritise breaker state (250ms) over instantaneous PQ (1s) over THD (5s) over energy (30s) over counters (60s).
6. **Idempotent telemetry writes:** All telemetry inserts use `INSERT ... ON CONFLICT (device_id, ts) DO NOTHING` to handle duplicate writes during buffer re-flush after VPN reconnection.
7. **Rate-limited buffer flush:** After VPN reconnection, flush local buffer in batches (500 rows per batch, 100ms delay between batches) to prevent connection stampede on the cloud database.

### B.3.3 VPN Tunnel Requirements (from Architecture Review)

1. **WireGuard with keepalive:** `PersistentKeepalive=25` to prevent NAT traversal failures.
2. **Dual-path failover:** Primary fibre + secondary 4G/LTE dongle on the edge gateway. If the primary path drops for >60 seconds, the edge gateway switches to the secondary. Budget: ~10GB/month 4G SIM as backup (telemetry volume ~2–5 GB/month).
3. **Tunnel state logging:** The edge gateway logs tunnel state transitions and pushes them as events when connectivity resumes.

### B.3.4 Database Connection Pooling (from Architecture Review)

1. **PgBouncer in transaction mode** between FastAPI backend and PostgreSQL.
2. **Separate pools:** 20 connections for API reads, 10 for edge gateway writes, maximum 50 total to PostgreSQL.
3. **SQLAlchemy configuration:** `pool_size=15, max_overflow=5, pool_timeout=10, pool_recycle=3600`.
4. **Write/read isolation:** API reads must never be starved by bulk telemetry writes from edge gateway buffer flush.

### B.3.5 WebSocket Reconnection Protocol (from Architecture Review)

1. **Exponential backoff + jitter:** Initial delay 1s, max delay 30s, jitter ±50%.
2. **Full state sync on reconnect:** Client sends `sync_request`, backend responds with complete state snapshot (all 104 breaker states, active alarms). Client replaces Zustand store — no merge.
3. **"Reconnecting..." banner:** Displayed in UI during backoff period so operators know the system is recovering.
4. **Broadcast throttling:** Maximum 10 WebSocket messages per second per client. If state changes exceed this rate (e.g., during buffer flush), batch updates into a single message per interval. Individual breaker state changes are immediate; bulk PQ updates are batched.

### B.3.6 Cloud Region & Hosting (from Architecture Review)

1. **Region:** Railway deployment with Cloudflare CDN. If measured VPN latency exceeds 50ms, migrate to AWS `af-south-1` (Cape Town). Target: <20ms VPN round-trip.
2. **Estimated cost:** R4,000–R5,500/month (managed PG + Redis + backend container).
3. **Redis AOF:** Enable `appendfsync=everysec` for session persistence. Sessions survive Redis restart with ≤1 second data loss.
4. **Report worker separation:** Report generation runs in a dedicated `arq` worker process, not the API process. Report queries target continuous aggregates (pq_15min, pq_daily), not raw pq_sample. Statement timeout: 120s on report worker connections.
5. **TimescaleDB aggregate refresh after buffer flush:** After every buffer flush, the backend explicitly calls `CALL refresh_continuous_aggregate('telemetry.pq_1min', start, end)` for the affected time range. Set `materialized_only = false` on aggregate views used by the API.

### B.3.7 Structured Logging (from Architecture Review)

All services (FastAPI backend, edge gateway, report worker) use `structlog` with JSON output:

1. **Format:** JSON lines, one event per line. Fields: `timestamp` (ISO 8601 UTC), `level` (debug/info/warning/error/critical), `event` (human-readable message), `service` (backend/edge/worker), `request_id` (UUID, propagated through middleware), `user_id` (if authenticated), `asset_id` (if relevant), `duration_ms` (for timed operations).
2. **Transport:** Ship logs to Grafana Loki via Promtail sidecar (Docker) or direct HTTP push (edge gateway).
3. **Retention:** 30 days hot (Loki), 90 days cold (S3-compatible object store).
4. **Log levels:** `DEBUG` in dev only, `INFO` in production. `WARNING` for recoverable issues (timeout retries, connection pool exhaustion). `ERROR` for unrecoverable failures. `CRITICAL` for system-down events (edge gateway crash, DB connection failure).
5. **Sensitive data:** NEVER log password hashes, JWT tokens, MFA secrets, or full request bodies containing credentials. Log user_id (UUID) not email.
6. **Metrics:** Export Prometheus metrics from FastAPI (`prometheus-fastapi-instrumentator`) and edge gateway (custom gauges: polls/sec, buffer depth, VPN state). Scrape interval: 15s.
7. **Grafana dashboards:** Minimum 3 dashboards for R1: (a) Edge gateway health (poll rate, COMMS LOSS count, buffer depth, VPN uptime), (b) API performance (request rate, p95 latency, error rate, WebSocket connections), (c) Telemetry pipeline (rows/sec ingested, aggregate refresh lag, disk usage).

### B.3.8 Edge Gateway Hardware Specification

| Attribute | Requirement |
|---|---|
| Form factor | Industrial mini-PC, fanless, DIN-rail mountable |
| Reference model | Advantech UNO-2271G or equivalent |
| CPU | Intel Atom / Celeron, ≥2 cores |
| RAM | ≥4 GB |
| Storage | ≥64 GB SSD (no SD cards — reliability concern) |
| Network | Dual NIC (1× SCADA VLAN, 1× management/WAN) + USB for 4G dongle |
| OS | Ubuntu 22.04 LTS Server |
| Budget | R15,000–R25,000 |
| Procurement | Must be ordered before build Week 1; ~2 week lead time (see SPRINT_0_TRACKER Action 3) |

Software dependencies: Python 3.12, pymodbus, structlog, WireGuard, SQLite3, systemd. No GUI. SSH access only.

### B.3.1 Generator Infrastructure

The site has two generator banks serving the centre on a 60/40 load split:

| Bank | Capacity | Coverage |
|---|---|---|
| Bank A | 2 × 350 kVA (option for 3rd) | ~60% of centre |
| Bank B | 2 × 350 kVA (option for 3rd) | ~40% of centre |

Each bank serves approximately 40 tenants via essential supply breakers. During mains failure, only essential loads should be on generator. When contractors bypass the 48V relay load-shedding system, non-essential load is added to the generator essential supply, risking overload across the entire bank. This is the highest-priority alarm scenario — see C.6.1.

### B.4 Complete Database Schema

Write out ALL tables across ALL 5 schemas with EVERY column, type, and constraint. This is the authoritative reference.

**Schema: `core`**

Table: `core.users`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK, DEFAULT gen_random_uuid() | |
| email | citext | UNIQUE, NOT NULL | |
| full_name | text | NOT NULL | |
| password_hash | text | NOT NULL | argon2id |
| role | core.user_role | NOT NULL | ENUM: admin, operator, viewer |
| mfa_secret | text | NULL | TOTP secret, AES-256 encrypted at rest |
| mfa_enabled | boolean | DEFAULT false | |
| is_active | boolean | DEFAULT true | Soft disable without delete |
| last_login_at | timestamptz | NULL | |
| created_at | timestamptz | DEFAULT now() | |
| updated_at | timestamptz | DEFAULT now() | Trigger-maintained |
| deleted_at | timestamptz | NULL | Soft delete |

Table: `core.audit_log`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | bigserial | PK | |
| ts | timestamptz | NOT NULL, DEFAULT now() | |
| user_id | uuid | FK → core.users, NULL | NULL for system-generated events |
| action | text | NOT NULL | e.g. 'breaker.open', 'user.login', 'report.generate' |
| asset_id | uuid | NULL | FK to relevant asset if applicable |
| payload | jsonb | DEFAULT '{}' | Action-specific details |
| ip | inet | NULL | Client IP address |
| user_agent | text | NULL | Browser/client identifier |

Append-only — no UPDATE or DELETE permitted. 7-year retention.

Table: `core.config`
| Column | Type | Constraints |
|---|---|---|
| scope | text | PK (composite) |
| key | text | PK (composite) |
| value | jsonb | NOT NULL |
| updated_at | timestamptz | DEFAULT now() |
| updated_by | uuid | FK → core.users |

**Schema: `assets`**

Table: `assets.main_board`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | |
| code | text | UNIQUE, NOT NULL | e.g. 'MB 1.1' |
| drawing | text | NOT NULL | e.g. '643.E.301' |
| vlan_id | int | NOT NULL | SCADA VLAN number |
| subnet | cidr | NOT NULL | e.g. '10.10.11.0/24' |
| gateway_ip | inet | NOT NULL | .1 on subnet |
| ekip_com_ip | inet | NULL | .10 on subnet |
| m4m_1_ip | inet | NULL | .100 on subnet |
| m4m_2_ip | inet | NULL | .101 on subnet |
| switch_ip | inet | NULL | .2 on subnet (edge switch) |
| location | text | NULL | Physical location description |
| created_at | timestamptz | DEFAULT now() | |
| updated_at | timestamptz | DEFAULT now() | |
| deleted_at | timestamptz | NULL | |

Table: `assets.breaker`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | |
| main_board_id | uuid | FK → assets.main_board, NOT NULL | |
| label | text | NOT NULL | e.g. 'DB-24A' |
| breaker_code | text | NOT NULL | TM1, TM2, TM3, TM4, TS1, TS2, TS3 |
| abb_family | text | NOT NULL | e.g. 'MCCB-TMAX-XT3', 'ACB-EMAX-E2' |
| rating_amp | int | NOT NULL | |
| poles | text | NOT NULL | 'TP', 'DP', 'SP' |
| mp_code | text | FK → assets.measuring_package, NOT NULL | |
| feeds_asset_type | text | NULL | 'distribution_board' or 'tenant_feed' |
| feeds_asset_id | uuid | NULL | Polymorphic FK |
| essential_supply | boolean | DEFAULT false | On generator essential supply (48V relay controlled) |
| device_ip | inet | NULL | Trip unit IP if addressable |
| modbus_unit_id | int | NULL | Modbus slave address |
| protocol | text | DEFAULT 'modbus_tcp' | 'modbus_tcp', 'iec61850', 'dual' |
| installed_at | date | NULL | Original installation date |
| replaced_at | date | NULL | Last device replacement date — resets operational counters |
| replacement_note | text | NULL | Reason for replacement |
| created_at | timestamptz | | |
| updated_at | timestamptz | | |
| deleted_at | timestamptz | NULL | |

Table: `assets.measuring_device`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| main_board_id | uuid | FK → assets.main_board |
| kind | text | NOT NULL — 'm4m30', 'ekip_com', 'ekip_dl', 'pdcom' |
| device_ip | inet | NOT NULL |
| modbus_unit_id | int | NULL |
| protocol | text | NOT NULL |
| serial | text | NULL |
| firmware_version | text | NULL |
| installed_at | date | NULL |
| replaced_at | date | NULL |
| replacement_note | text | NULL |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| deleted_at | timestamptz | NULL |

Table: `assets.distribution_board`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| code | text | UNIQUE, NOT NULL |
| name | text | NOT NULL |
| area_m2 | numeric(8,2) | NULL |
| cable_spec | text | NULL |
| essential_supply | boolean | DEFAULT false |
| generator_bank | text | NULL | 'A' or 'B' — which generator bank serves this DB |
| fed_by_breaker_id | uuid | FK → assets.breaker |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| deleted_at | timestamptz | NULL |

Table: `assets.tenant_feed`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| code | text | UNIQUE, NOT NULL |
| tenant_name | text | NOT NULL |
| area_m2 | numeric(8,2) | NOT NULL |
| fed_by_breaker_id | uuid | FK → assets.breaker |
| lease_start | date | NULL |
| lease_end | date | NULL |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| deleted_at | timestamptz | NULL |

Table: `assets.lighting_circuit`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| distribution_board_id | uuid | FK → assets.distribution_board |
| label | text | NOT NULL |
| rating_amp | numeric(6,2) | |
| burn_hours | numeric(12,2) | DEFAULT 0 |
| state | text | 'on', 'off', 'fault' |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| deleted_at | timestamptz | NULL |

**Canvas & Spatial Mapping Tables (full definitions in DB_SCHEMA.md §8):**

Table: `assets.canvas` — 2 rows: `sld_topology` (from 643.E.300) and `floor_plan` (from 2239-100-0)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| code | text | UNIQUE — `'sld_topology'`, `'floor_plan'` |
| name | text | Display label |
| svg_path | text | Path to base SVG in object storage |
| width / height | int | SVG viewBox dimensions |
| default_zoom / min_zoom / max_zoom | real | Zoom constraints |
| version | int | Incremented on layout changes |

Table: `assets.canvas_layer` — ~12 rows (6 per canvas)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| canvas_id | uuid | FK → assets.canvas |
| code | text | e.g. `'main_boards'`, `'tenant_zones'`, `'alarms'` |
| z_order | int | Higher = rendered on top |
| visible_by_default | boolean | |
| min_zoom_visible / max_zoom_visible | real | LOD auto-show/hide thresholds |
| style | jsonb | Default fill/stroke/opacity for hotspots |

Table: `assets.canvas_hotspot` — ~200+ rows (every clickable asset on both canvases)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| layer_id | uuid | FK → assets.canvas_layer |
| asset_id | uuid | FK to linked asset (breaker, MB, DB, tenant, etc.) |
| asset_type | text | `'main_board'`, `'breaker'`, `'distribution_board'`, `'tenant_feed'`, etc. |
| shape | text | `'rect'`, `'circle'`, `'polygon'`, `'path'`, `'line'` |
| geometry | jsonb | Shape coordinates in SVG viewBox units |
| anchor_x / anchor_y | real | Tooltip anchor point |
| style_default / style_active / style_selected | jsonb | State-dependent styling |
| nav_targets | jsonb | Cross-canvas navigation targets |

Table: `assets.canvas_nav_route` — ~100+ rows (drill-through between SLD and floor plan)
| Column | Type | Notes |
|---|---|---|
| from_canvas_id / from_hotspot_id | uuid | Source canvas + hotspot |
| to_canvas_id / to_hotspot_id | uuid | Target canvas + hotspot |
| to_zoom | real | Zoom level on arrival |
| label | text | e.g. "Show on Floor Plan" |

Migration: `db/migrations/0002_canvas_layers.sql`

Table: `assets.measuring_package` (reference)
| Column | Type |
|---|---|
| code | text PK |
| description | text |
| function_count | int |

Table: `assets.mp_function` (48 rows)
| Column | Type |
|---|---|
| id | serial PK |
| mp_code | text FK → assets.measuring_package |
| function | text |
| ansi_code | text NULL |
| unit | text NULL |
| db_field | text — the telemetry column name |
| poll_class | text — 'state', 'inst', 'energy', 'harmonics', 'counter' |

Table: `assets.asset_document`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| asset_id | uuid | NOT NULL |
| asset_type | text | NOT NULL |
| filename | text | NOT NULL |
| mime_type | text | NOT NULL |
| storage_path | text | NOT NULL |
| uploaded_by | uuid | FK → core.users |
| uploaded_at | timestamptz | DEFAULT now() |

**Schema: `telemetry` (TimescaleDB hypertables)**

Table: `telemetry.pq_sample`
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
  harmonics     JSONB,          -- see format below
  PRIMARY KEY (device_id, ts)
);
-- Hypertable: chunk_time_interval 1 day
-- Continuous aggregates: pq_1min, pq_15min, pq_hourly, pq_daily
-- Retention: raw 90 days, 15min 5 years, daily indefinite
```

**Harmonics JSONB format:** Individual harmonic magnitudes as percentage of fundamental, keyed by order number. Voltage and current harmonics stored separately:
```json
{
  "v": {"2": 0.3, "3": 2.1, "5": 4.5, "7": 3.2, "9": 1.1, "11": 2.0, "13": 1.5, "15": 0.8},
  "i": {"2": 0.5, "3": 8.2, "5": 6.1, "7": 4.0, "9": 2.3, "11": 1.8, "13": 1.2, "15": 0.6}
}
```
Values in %. Orders 2–15 per ABB M4M 30 measurement capability. Missing orders = not measured (omit key, don't store null). The `thd_v` and `thd_i` columns store the total harmonic distortion as calculated by the device.

Table: `telemetry.energy_register`
| ts | device_id | kwh_imp | kwh_exp | kvarh_imp | kvarh_exp |
Hypertable, chunk 7 days.

Table: `telemetry.breaker_state`
| ts | breaker_id | state (open/closed/tripped) | trip_cause TEXT NULL | contact_source TEXT |
Hypertable, chunk 1 day.

Table: `telemetry.lighting_state`
| ts | circuit_id | state | current_a |
Hypertable, chunk 1 day.

**Schema: `events`**

Table: `events.event`
| Column | Type |
|---|---|
| id | bigserial PK |
| ts | timestamptz NOT NULL |
| asset_id | uuid NOT NULL |
| asset_type | text NOT NULL |
| severity | ENUM: info, warning, error, critical |
| kind | text NOT NULL |
| message | text NOT NULL |
| payload | jsonb DEFAULT '{}' |
| acknowledged_by | uuid NULL FK → core.users |
| acknowledged_at | timestamptz NULL |

Partial index: `(ts DESC, severity) WHERE acknowledged_at IS NULL` — drives live alarm pane.
Index: `(asset_id, ts DESC)` — drives asset detail panel event history queries.

**Required indexes on telemetry tables (from Architecture Review):**
- `telemetry.breaker_state`: index on `(breaker_id, ts DESC)` — required for "last known state" lookups. Without this, every dashboard load scans the full hypertable.

Table: `events.threshold`
| Column | Type |
|---|---|
| id | uuid PK |
| asset_id | uuid NULL — NULL means class-wide |
| asset_class | text NULL |
| metric | text NOT NULL |
| warning_low | real NULL |
| warning_high | real NULL |
| error_low | real NULL |
| error_high | real NULL |
| critical_low | real NULL |
| critical_high | real NULL |
| hysteresis | real DEFAULT 0 |
| enabled | boolean DEFAULT true |

**Schema: `reports`**

Table: `reports.template`
| Column | Type |
|---|---|
| id | uuid PK |
| name | text NOT NULL |
| description | text |
| query_definition | jsonb NOT NULL |
| output_format | text — 'pdf', 'csv', 'xlsx' |
| created_by | uuid FK → core.users |

Table: `reports.schedule`
| Column | Type |
|---|---|
| id | uuid PK |
| template_id | uuid FK → reports.template |
| cron_expression | text NOT NULL |
| distribution_list | jsonb — array of {email, channel} |
| enabled | boolean DEFAULT true |
| last_run_at | timestamptz NULL |
| next_run_at | timestamptz NULL |

Table: `reports.artefact`
| Column | Type |
|---|---|
| id | uuid PK |
| template_id | uuid FK |
| schedule_id | uuid FK NULL |
| generated_at | timestamptz |
| generated_by | uuid FK → core.users NULL |
| file_path | text |
| file_hash | text |
| file_size_bytes | bigint |
| retention_until | date |

### B.5 Network & Protocol Addressing Plan

| MB | Drawing | VLAN | Subnet | Gateway | Edge Switch | Ekip Com | M4M #1 | M4M #2 | Trip units start |
|----|---|---|---|---|---|---|---|---|---|
| MB 1.1 | 643.E.301 | 11 | 10.10.11.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 2.1 | 643.E.302 | 21 | 10.10.21.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 2.2 | 643.E.303 | 22 | 10.10.22.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 2.3 | 643.E.304 | 23 | 10.10.23.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 3.1 | 643.E.305 | 31 | 10.10.31.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 4.1 | 643.E.306 | 41 | 10.10.41.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 5.1 | 643.E.307 | 51 | 10.10.51.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 5.2 | 643.E.308 | 52 | 10.10.52.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |
| MB 5.3 | 643.E.309 | 53 | 10.10.53.0/24 | .1 | .2 | .10 | .100 | .101 | .11 |

Protocols: Modbus TCP (port 502) baseline for all devices. IEC 61850 MMS (port 102) additionally on TS2 anchor feeders (dual-stack). Inter-VLAN routing through hardened core firewall — only SCADA backend subnet reaches ports 502/102.

### B.6 Polling Cadence

| Data class | Poll interval |
|---|---|
| Breaker state, trip flags | 250 ms |
| Instantaneous V/I/P | 1 s |
| Energy registers | 30 s |
| THD / harmonics | 5 s |
| Running hours / burn hours | 60 s |

---

## PART C — FUNCTIONAL REQUIREMENTS

### C.1 User Management Lifecycle

**Invite → Onboard → Login → MFA → Password Reset → Profile → Sessions → Disable**

1. **Invite:** Admin sends magic-link email (Resend). Link contains signed JWT (`aud: invite`) with role pre-assignment. Expires in 48 hours. One-time use — mark `core.invite.accepted_at` on first use, reject reuse.
2. **Onboard:** User sets password (argon2id, `m=65536, t=3, p=4`) + enrolls TOTP MFA (mandatory for Admin and Operator, optional for Viewer). Generates recovery codes (10, single-use, hashed with argon2id, stored in `core.recovery_code`). Codes displayed once during enrollment, never retrievable again. Format: 8 groups of 4 alphanumeric characters, ≥128 bits entropy. New code generation invalidates all previous codes.
3. **Login:** Email + password → short-lived JWT access token (15 min, `aud: access`) + refresh token (7 days, `aud: refresh`, rotated on use — old `refresh_hash` overwritten atomically, no grace period). New session record created on every login (session fixation prevention). Failed login lockout: 5 attempts → 15 min lock → audit log entry → email notification to user ("multiple failed login attempts detected").
4. **MFA:** TOTP challenge on every login for Admin/Operator. Recovery code fallback. MFA bypass only via Admin reset + audit log.
5. **Password Reset:** Self-service via email link (Resend). Link expires 1 hour. Token: `secrets.token_urlsafe(32)`, SHA-256 hashed before storage. Response: always "If that email exists, a reset link has been sent" (no user enumeration). New request invalidates all previous unused tokens for that user. Rate limit: 3 per email per hour, 10 per IP per hour. Old sessions invalidated on password change.
6. **Profile:** User can update full_name. Only Admin can change role or disable account.
7. **Sessions:** Active session list visible to user. "Logout all devices" available. Admin can force-logout any user. Role change: all sessions for the affected user invalidated immediately. JWT re-issued (not just refreshed) after role change.
8. **Disable:** Admin sets is_active=false. All sessions invalidated immediately. Account retained for audit trail integrity — never hard-deleted.

**WebSocket authentication:**
- JWT passed via cookie (not query parameter — query params appear in access logs).
- JWT validated during WebSocket upgrade handshake.
- Server-side periodic check (every 60s): verify session still valid. If revoked, close with code 4001.
- On forced logout (admin action): server closes WebSocket immediately with code 4003.

### C.2 Asset Management

- Registry CRUD for all asset types (§B.4): main boards, breakers, measuring devices, distribution boards, tenant feeds, lighting circuits.
- Per-asset document repository — manuals, test certificates, commissioning photos, stored in object storage with metadata in `assets.asset_document`.
- Version-controlled asset documentation (git-backed LFS under `/docs/assets/<asset_id>/`).
- SLD extraction pipeline for ongoing updates — see `skills/sld-extraction/SKILL.md`.

### C.2.1 Canvas Mapping & Visual Navigation

The SCADA GUI provides **two interactive visual canvases** that serve as the primary navigation interface for operators and viewers. Both are database-driven (see DB_SCHEMA.md §8) so the layout updates when the mall changes — no code deployment required.

**Canvas 1 — SLD Topology View (derived from 643.E.300):**
- Shows the electrical distribution hierarchy: transformer → main boards → breakers → distribution boards
- Each node is a clickable hotspot linked to its `assets.*` record
- Cable runs displayed as path hotspots connecting nodes
- Live state overlay: breaker open/closed/tripped colour-coded, alarm badges on affected nodes
- Click any MB node → zooms into that board's outgoing breakers
- Click any breaker → opens asset detail panel with live PQ readings
- "Show on Floor Plan" button navigates to the corresponding physical location

**Canvas 2 — Floor Plan View (derived from 2239-100-0-Overall Floor Plan):**
- Shows the physical mall layout with walls, corridors, and tenant boundaries
- Tenant zones are polygon hotspots, colour-coded by live state (normal=green, alarm=red, comms loss=grey)
- MB rooms, DB positions, and lighting zones overlaid as separate toggleable layers
- Click any tenant zone → opens tenant detail with breaker info, PQ summary, energy usage
- "Show on SLD" button navigates to the electrical routing view for that asset

**Layer system:**
- Each canvas has multiple layers (e.g. main_boards, breakers, tenants, cables, lighting, alarms)
- Users can toggle layer visibility via a layer panel
- Level-of-detail (LOD): layers auto-show/hide based on zoom level (e.g. individual breaker labels only visible when zoomed in past 2x)
- Layer z-order controls rendering priority (alarms always on top)

**Cross-canvas navigation:**
- `assets.canvas_nav_route` table defines drill-through links between the two canvases
- Clicking "Show on Floor Plan" on an SLD breaker node centres the floor plan on that breaker's physical location at appropriate zoom
- Clicking "Show on SLD" on a floor plan tenant zone centres the SLD on that tenant's feeding breaker

**Real-time state overlay via WebSocket:**
- When `telemetry.breaker_state` updates, the frontend receives a JSON patch via WebSocket
- The canvas renderer looks up the hotspot for that breaker's `asset_id` and updates its fill colour
- State-to-colour mapping: `closed` → green, `open` → amber, `tripped` → red, `comms_loss` → grey
- Active alarms add a pulsing badge overlay on the affected hotspot

**Canvas preparation process (for initial setup and updates):**
1. Export source PDF to clean SVG via Inkscape CLI (`inkscape --export-type=svg`)
2. Clean the SVG: remove text labels (rendered dynamically), keep structural geometry
3. Upload SVG to object storage, register in `assets.canvas`
4. Map hotspots: for each asset visible on the canvas, create a `canvas_hotspot` row with geometry (rect/circle/polygon/path) and link to `asset_id`
5. Define layers and assign hotspots to layers
6. Create nav_route entries linking corresponding hotspots across canvases
7. Set LOD thresholds: `min_zoom_visible` / `max_zoom_visible` per layer

**Database tables (full definitions in DB_SCHEMA.md §8):**
- `assets.canvas` — 2 rows (sld_topology, floor_plan)
- `assets.canvas_layer` — ~12 rows (6 layers per canvas)
- `assets.canvas_hotspot` — ~200+ rows (every visible asset on both canvases)
- `assets.canvas_nav_route` — ~100+ rows (cross-canvas drill-through links)

**When the mall changes (tenant moves, new DB, renovations):**
- Update the source PDF if the physical layout changed → re-export SVG → update `assets.canvas.svg_path` + increment `version`
- Add/update/remove hotspot rows in `assets.canvas_hotspot` for affected assets
- Update polygon geometry for tenant boundary changes
- Add nav_route entries for new cross-canvas links
- No code changes required — the React renderer reads geometry from the API

### C.3 Monitoring (Read-Only)

**This system is monitoring-only. Remote switching of breakers and lighting is permanently out of scope. All physical switching is performed on site by authorised personnel.**

- **Real-time state:** Breaker open/closed/tripped, M4M readings, live PQ metrics. Target latency <1s from field sample to browser pixel.
- **WebSocket protocol:** Backend publishes state changes to Redis pub/sub channel per MB. Frontend subscribes via single WSS connection, receives JSON patches for changed assets only (not full state dump).
- **Breaker state monitoring:** Continuous polling of all 104 outgoing breaker states. State transitions (open→closed, closed→tripped, etc.) logged with timestamp in `telemetry.breaker_state`. Unexpected state changes trigger alarm evaluation.
- **48V relay bypass detection:** For breakers marked `essential_supply=true`, the system compares expected state (relay command = open during load shedding) against actual state (breaker register = closed). A mismatch indicates the relay has been bypassed by a contractor — this triggers the highest-severity alarm. See C.6.1.
- **Lighting burn-hour tracking:** Burn hours accumulated from lighting circuit state polling. No remote on/off control — state is observed, not commanded.
- **Power quality:** V (L-L, L-N), I (per phase + neutral), P, Q, S, PF, THD-V, THD-I, frequency, harmonics to 15th order. All per MP2 function set for the 104 outgoings.
- **Device communication monitoring:** Distinct handling for "device unreachable" (Modbus timeout) versus "equipment fault" (breaker tripped, PQ anomaly). Communication loss triggers notification with tiered escalation; equipment faults trigger immediate alarms per severity.
- **Device replacement tracking:** When a physical device is replaced, the operator records the replacement date via the asset management interface. All operational counters (switching cycles, burn hours, uptime) are calculated from the replacement date forward, ensuring maintenance forecasting reflects the actual hardware in service.

### C.4 Data Logging & Storage

- **Events:** switching, trips, errors, state transitions — all with timestamp, asset_id, user_id (if user-initiated), severity, diagnostic payload.
- **Historical PQ:** TimescaleDB hypertables with continuous aggregates at 1-min, 15-min, 1-hour, 1-day rollups.
- **Retention:** Raw pq_sample 90 days; pq_15min 5 years; pq_daily indefinite.
- **Error states:** Recorded with timestamp + asset ID + diagnostic payload in events.event.
- **Energy registers:** Cumulative kWh/kVARh logged every 30s, stored in telemetry.energy_register.

### C.5 Reporting

- **Monthly automated reports:** Usage summary, error summary, PQ summary, top offenders. Generated via cron, distributed via email (Resend) + dashboard download.
- **On-demand reports:** User-defined date range + asset selection. Generated async (queued via Redis), notification when ready.
- **Export formats:** PDF and CSV. XLSX for energy billing workbooks.
- **Delivery:** Dashboard download link + email distribution list (configurable per report template in reports.schedule).

### C.6 Notifications & Alerts

#### C.6.1 Highest-Priority Alarm: 48V Relay Bypass Detection

**Scenario:** A contractor bypasses the 48V relay load-shedding system on a tenant board, adding unauthorized non-essential load to the generator essential supply. During mains failure, this risks overload across an entire generator bank (~40 tenants affected per bank).

**Detection logic:** For every breaker with `essential_supply=true`, the system continuously compares:
- **Expected state:** relay command (open during load shedding event)
- **Actual state:** breaker register (closed = bypassed)

A mismatch triggers a `CRITICAL` event with `kind='relay_bypass'`. This is the single most important alarm in the system.

**Relay state source (OPEN QUESTION — see SPRINT_0_TRACKER Action 1):**
The relay command state source is unconfirmed. Profection has been asked whether the 48V relay controller exposes its state via a Modbus register. The build implements a pluggable `RelayStateProvider` interface so the detection module works regardless of the answer:

| Scenario | Provider | How it works |
|---|---|---|
| **Relay state readable via Modbus** (preferred) | `ModbusRelayStateProvider` | Direct register read of relay command state. Most reliable. |
| **Relay state NOT readable** (fallback A) | `ScheduleBasedRelayStateProvider` | During mains failure (detected via incomer PQ loss), any non-essential breaker in "closed" state is flagged. Requires `essential_supply` classification to be correct. |
| **Relay state NOT readable** (fallback B) | `CurrentBasedRelayStateProvider` | During mains failure, non-essential breakers drawing current (i_l1 > threshold) are flagged as potential bypasses. Higher false-positive rate. |

If Profection confirms NO by 2026-04-25, the build proceeds with Fallback A and the interface remains pluggable for future upgrade.

**Response context in alarm:** Because operators are new and unfamiliar with the building, the bypass alarm includes: asset location breadcrumb ("MB 2.1 → Row 3 → DB-24A → Pick n Pay cold room"), generator bank affected ("Bank A — 60% of centre"), estimated additional load, and recommended action ("Dispatch electrician to DB-24A to restore relay connection").

#### C.6.2 Communication Loss vs Equipment Fault

The system distinguishes between two fundamentally different failure modes:

| Condition | Detection | Severity | Action |
|---|---|---|---|
| **Device unreachable** | Modbus TCP timeout (3 consecutive missed polls) | Warning → escalates to Error after 5 min | Notification, then tiered escalation |
| **Equipment fault** | Breaker tripped, PQ anomaly, overcurrent | Per threshold severity | Immediate alarm per configured severity |

Communication loss displays the asset as "COMMS LOSS" (grey) on the canvas — never shows stale data as current.

#### C.6.3 Tiered Escalation

| Tier | Trigger | Channel |
|---|---|---|
| 1 — Notify | Event detected | In-app toast + email |
| 2 — Escalate | Unacknowledged after 15 min | SMS to on-call operator |
| 3 — Elevate | Unacknowledged after 30 min | SMS to Watson Mattheus admin |

#### C.6.4 General Alert Configuration

- **Real-time alerts:** Critical events (trip, sustained over/under voltage, comms loss, relay bypass) → immediate notification.
- **Configurable thresholds:** Per-asset or per-asset-class in events.threshold with hysteresis to prevent flapping.
- **Delivery channels:**
  - In-app: WebSocket toast notification (all severities)
  - Email: Resend (warning, error, critical)
  - SMS: BulkSMS South Africa (critical only)
  - Webhook: configurable endpoint for Slack/Teams integration (all severities)

---

## PART D — BUILD PHASES & RELEASE SEQUENCE

### D.1 Release Sequence

**Hard deadline:** Full system operational and testing-ready for commissioning plug-in within 14 weeks.

**Three-party delivery model:**

| Party | Scope |
|---|---|
| **DB manufacturer** | Physical switchgear, Ekip/M4M modules, PLC programming, VLAN networking |
| **Watson Mattheus + Claude** | SCADA GUI application (backend, frontend, database, cloud deployment) |
| **Interface contract** | This SPEC.md defines the Modbus register map, IP addressing, polling intervals, and device naming convention. Delivered to DB manufacturer as a proposal for comment. |

**Release sequence:**

| Release | Scope | Timeline | Acceptance Criteria |
|---|---|---|---|
| **R1 — MVP** | Live breaker state monitoring, alarm notifications (including relay bypass detection), continuous PQ data logging | Within 14-week window | All 104 breakers reporting state; all M4M 30 PQ readings logging; all alarms triggering on simulated events |
| **R2 — Usage & Reporting** | Equipment usage tracking, burn hours, switching cycle counters, monthly automated reports | ~4 weeks after R1 | Monthly reports generating and distributing; burn hour counters accurate |
| **R3 — Visual Navigation** | Floor plan canvas, SLD topology canvas, cross-canvas navigation, operator training tools | ~8 weeks after R1 | Full visual interface operational; untrained operator can navigate from alarm to physical location |

**Development approach:** Software developed against simulated/mocked Modbus data in parallel with DB manufacturer's hardware installation. Integration testing begins when first main board is commissioned and on the network.

### D.2 Permanently Out of Scope

The following features are explicitly excluded and must never be implemented:

- Remote breaker switching (open/close commands)
- Remote lighting control (on/off commands)
- Two-step confirmation UI for control commands
- Command-readback verification
- Rate-limiting on control endpoints
- `is_controllable` flag on breakers (removed from schema)

All physical switching is performed on site by authorised personnel. This system monitors, records, and alerts — it does not control.

### D.3 Commissioning Acceptance Criteria

The system is accepted for production when all of the following are demonstrated during commissioning testing with the DB manufacturer's live network:

1. All 104 breakers reporting state to the database within the <1s latency target
2. All M4M 30 power quality readings logging correctly across all 9 main boards
3. All configured alarms triggering on simulated test events
4. 48V relay bypass detection correctly identifying a simulated bypass scenario
5. Communication loss correctly distinguished from equipment fault
6. Tiered escalation delivering notifications through all channels (in-app, email, SMS)
7. Full visual interface operational (R3 — floor plan + SLD canvases)
8. Reporting pipeline producing output (R2 — monthly reports)
9. All user roles functioning correctly (Admin, Operator, Viewer)
10. Edge gateway resilience: local buffer retains data during simulated internet outage

### D.4 Build Phases (Detail)

See `BUILD_STRATEGY.md` for the complete build timeline with skill assignments. Summary aligned to release sequence:

**R1 — MVP (Weeks 1–14):**

| Phase | Weeks | Focus | Key Skills |
|---|---|---|---|
| 1. Foundation | 1–3 | Schema, auth, CI/CD, config, cloud infra | data-schema-designer, auth-system-builder, cicd-pipeline-writer |
| 2. Real-time Core | 4–6 | WebSocket, Modbus gateway, event bus, edge gateway | dashboard-backend, event-system-designer, data-pipeline-builder |
| 3. Asset Management | 7–9 | CRUD, asset registry, documents | api-endpoint-generator, web-artifacts-builder, sld-extraction |
| 4. Monitoring Dashboard | 10–12 | Live dashboard, breaker state, bypass detection, alarms | state-machine-builder, react-component-optimizer, notification-system-builder |
| 5. Power Quality | 13–14 | PQ trends, continuous aggregates, commissioning testing | database-query-optimizer, caching-strategy, performance-optimizer |

**R2 — Usage & Reporting (~4 weeks post-R1):**

| Phase | Weeks | Focus | Key Skills |
|---|---|---|---|
| 6. Reporting | 15–17 | Report engine, PDF/CSV/XLSX export, scheduling, burn hours | report-generator, pdf, xlsx, cron-job-builder |
| 7. Hardening | 18 | Security audit, load test, compliance | security-audit, load-testing-script, compliance-checking-ai |

**R3 — Visual Navigation (~8 weeks post-R1):**

| Phase | Weeks | Focus | Key Skills |
|---|---|---|---|
| 8. Canvas & Training | 19–22 | Floor plan canvas, SLD canvas, cross-canvas nav, training UI | web-artifacts-builder, sld-extraction, write-documentation |

---

## PART E — NON-FUNCTIONAL REQUIREMENTS

| Area | Target | Measurement Method |
|---|---|---|
| Latency | <1s field → browser for state changes | WebSocket round-trip instrumentation |
| Throughput | ≥100 concurrent users without degradation | Load test with k6 (load-testing-script skill) |
| Scalability | 10,000+ assets, 10⁸ log rows/year | TimescaleDB continuous aggregates + partitioning |
| Availability | 99.9% uptime | PostgreSQL streaming replication + auto-failover |
| Security | TLS 1.3, RBAC, annual pen-test | security-audit skill + external audit |
| Usability | Responsive, WCAG 2.1 AA | Playwright accessibility tests |
| Maintainability | Modular codebase, ≥80% test coverage, ADRs | CI coverage gates + architecture-review skill |
| Compliance | POPIA, GDPR-ready, 7-year audit retention | compliance-checking-ai skill |
| Bundle size | <200KB initial JS (gzipped) | Vite build analysis in CI |
| API response | <100ms p95 for REST, <50ms for WS broadcast | Backend instrumentation |

### E.1 Top 5 Delivery Risks (from PRE_MORTEM_ANALYSIS.md)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Profection late delivering register maps / bench hardware | HIGH | CRITICAL | Build against Modbus simulator with TODO markers. Budget 2 weeks integration rework. Escalate via client if no response by 2026-04-25. |
| 2 | Arno review bottleneck (single engineer for all domain decisions) | HIGH | HIGH | Pre-approve merge zones for non-domain code (CI, styling, boilerplate). Fixed review blocks 3×/week. Batch domain questions. |
| 3 | Mock data divergence from real ABB devices | MEDIUM | HIGH | Verify mock ranges against ABB datasheets. Flag all register addresses as provisional. First real-device test at earliest MB commissioning. |
| 4 | 14-week timeline compression during integration | MEDIUM | HIGH | Negotiate pilot MB commissioning by Week 8–10 (not Week 14). Stagger integration across main boards. |
| 5 | Edge gateway hardware not ordered / delayed | MEDIUM | HIGH | Order by 2026-04-21 (SPRINT_0_TRACKER Action 3). Industrial mini-PC has ~2 week lead time. Code against any Linux box in the interim. |

Full analysis with 20 failure modes: `PRE_MORTEM_ANALYSIS.md`

### E.2 POPIA Data Processing Register

| Data Element | Table | Legal Basis | Retention | Subject Access |
|---|---|---|---|---|
| Email, full name | `core.users` | Legitimate interest (safety monitoring) | Account lifetime + 7 years post-deactivation | Admin can export on request |
| IP address, user agent | `core.audit_log` | Legitimate interest (security forensics) | 7 years (immutable) | Admin can export on request |
| Login timestamps | `core.session` | Legitimate interest (session management) | Session lifetime + 90 days | Admin can export on request |
| Telemetry (PQ, state) | `telemetry.*` | Legitimate interest (equipment monitoring) | 90 days raw, 5 years aggregated | Not personal data |
| Alarm acknowledgements | `events.event` | Legitimate interest (operational safety) | 7 years | Admin can export by user_id |

**Data subject rights:** The system administrator (Admin role) can fulfil access, correction, and portability requests via the admin panel. Deletion requests are handled by soft-delete (`deleted_at`) — hard deletion is not supported due to audit trail integrity requirements under both POPIA and the building's safety monitoring obligations. This legal basis must be documented in the privacy notice presented during user onboarding.

**Breach notification:** If a data breach is detected (unauthorized access to `core.users` or `core.audit_log`), Watson Mattheus must notify the Information Regulator within 72 hours per POPIA §22. The incident response procedure is maintained outside this spec by Watson Mattheus.

---

## PART F — OPEN GAPS

The full gap list (21 items) is maintained in sheet "Gaps & Actions" of `design/SLD_FIELD_MAP.xlsx`. Critical highlights:

- **GAP-16:** `TS1` breaker code on DB-39 (Pick n Pay, MB 5.1) — not in legend. Confirm with design office: custom ACB or typo for TS2?
- **GAP-18:** DB-26 labelled "TOTALSPORTS" on drawing 300 but "EXACT" on drawing 301. Tenant allocation to be reconciled on site.
- **GAP-19/20/21:** Network plan VLAN numbering, subnet scheme, and firewall rule-set awaiting client review.

---

## PART G — DELIVERABLES CROSS-REFERENCE

**Specification & design:**

| # | Deliverable | File | Maintainer |
|---|---|---|---|
| 1 | Master specification (this file) | `SPEC.md` | Arno (content) + Claude (format) |
| 2 | Build strategy & timeline | `BUILD_STRATEGY.md` | Claude, reviewed by Arno |
| 3 | Database schema reference | `DB_SCHEMA.md` | Claude |
| 4 | Skills catalogue | `SKILLS.md` | Claude |
| 5 | Technology assessment | `TECHNOLOGY_ASSESSMENT.md` | Claude, reviewed by Arno |
| 6 | Frontend framework decision | `FRONTEND_FRAMEWORK_DECISION.md` | Claude |

**Analysis & review:**

| # | Deliverable | File | Maintainer |
|---|---|---|---|
| 7 | Project clarity report | `PROJECT_CLARITY_REPORT.md` | Claude (interrogation) + Arno (responses) |
| 8 | Architecture review (12 findings) | `ARCHITECTURE_REVIEW.md` | Claude |
| 9 | Pre-mortem analysis (20 failure modes) | `PRE_MORTEM_ANALYSIS.md` | Claude |
| 10 | Assumption map (30 assumptions) | `ASSUMPTION_MAP.md` | Claude |
| 11 | Schema review (25 findings) | `SCHEMA_REVIEW.md` | Claude |
| 12 | Schema audit — final pass (8 findings) | `SCHEMA_AUDIT_FINAL.md` | Claude |
| 13 | Security audit — pre-build (22 findings) | `SECURITY_AUDIT_PREBUILD.md` | Claude |
| 14 | Spec completeness gap analysis (15 gaps) | `SPEC_GAP_ANALYSIS.md` | Claude |

**Build readiness:**

| # | Deliverable | File | Maintainer |
|---|---|---|---|
| 15 | Build handoff ("start here" for coding session) | `BUILD_HANDOFF.md` | Claude |
| 16 | Sprint 0 action tracker (pre-build blockers) | `SPRINT_0_TRACKER.md` | Arno (owner) + Claude (format) |

**Interface documents (Profection):**

| # | Deliverable | File | Maintainer |
|---|---|---|---|
| 17 | Interface specification | `WM-KW-SCADA-IF-001_Interface_Specification.docx` | Watson Mattheus |
| 18 | Bench test request | `WM-KW-SCADA-REQ-001_Bench_Test_Request.docx` | Watson Mattheus |

**Database migrations:**

| # | Deliverable | File | Maintainer |
|---|---|---|---|
| 19 | Initial schema migration | `db/migrations/0001_initial.sql` | Claude |
| 20 | Schema review fixes | `db/migrations/0001a_schema_review_fixes.sql` | Claude |
| 21 | Canvas & spatial mapping | `db/migrations/0002_canvas_layers.sql` | Claude |
| 22 | Asset documents (pending — R2) | `db/migrations/0003_asset_documents.sql` | Claude |

**Asset data:**

| # | Deliverable | File | Maintainer |
|---|---|---|---|
| 23 | Master inventory workbook (8 sheets, 104 items) | `design/SLD_FIELD_MAP.xlsx` | Claude (generated) |
| 24 | Per-MB SLD extract (machine-readable) | `design/sld_per_mb_extract.json` | sld-extraction pipeline |
| 25 | Overview SLD extract (machine-readable) | `design/sld_overview_extract.json` | sld-extraction pipeline |
| 26 | SLD extraction skill | `skills/sld-extraction/SKILL.md` | Claude |

---

**END OF SPECIFICATION**
