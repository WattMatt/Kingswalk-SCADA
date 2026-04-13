# Kingswalk SCADA Monitoring System — Build Session Instructions

You are building a web-based SCADA monitoring GUI for Kingswalk Shopping Centre. This is a safety-critical industrial monitoring system. Read everything in this file before writing any code.

## How This Project Works

This project has **two operators working in parallel:**

1. **Arno (spec side)** — maintains SPEC.md and the companion documents from a separate machine. He updates requirements, resolves open questions, and reviews your output.
2. **You (build side)** — this Claude Code session on the Mac Mini. You read the spec, write code, run tests, and deploy.

**The spec folder is shared via cloud sync.** When Arno updates SPEC.md, the changes appear here. When you create code, he can see your progress. Treat the spec documents as READ-ONLY — never edit them from this session. If you find a spec gap, create an issue in `SPEC_FEEDBACK.md` (see below).

## First Command

Before writing any code, read these files **in this order:**

```
1. spec/BUILD_HANDOFF.md          ← Start here. Context, constraints, what bites you.
2. spec/SPEC.md                   ← Master specification. Everything is in here.
3. spec/BUILD_STRATEGY.md         ← Build phases, skill triggers, coding standards.
4. spec/DB_SCHEMA.md              ← Database schema reference.
5. spec/SECURITY_AUDIT_PREBUILD.md ← 22 security findings. Section 8.8 of BUILD_HANDOFF lists the Phase 1 items.
```

## Project Structure

```
kingswalk-scada/                 ← Git repo root (you create this)
├── CLAUDE.md                    ← This file (project instructions for Claude Code)
├── spec/                        ← Spec documents (READ-ONLY, synced from Arno's machine)
│   ├── SPEC.md
│   ├── BUILD_HANDOFF.md
│   ├── BUILD_STRATEGY.md
│   ├── DB_SCHEMA.md
│   ├── SECURITY_AUDIT_PREBUILD.md
│   ├── SPEC_GAP_ANALYSIS.md
│   ├── SPRINT_0_TRACKER.md
│   ├── ASSUMPTION_MAP.md
│   ├── ARCHITECTURE_REVIEW.md
│   ├── PRE_MORTEM_ANALYSIS.md
│   ├── SCHEMA_REVIEW.md
│   ├── SCHEMA_AUDIT_FINAL.md
│   ├── TECHNOLOGY_ASSESSMENT.md
│   ├── FRONTEND_FRAMEWORK_DECISION.md
│   ├── SKILLS.md
│   └── design/
│       ├── SLD_FIELD_MAP.xlsx
│       ├── sld_per_mb_extract.json
│       └── sld_overview_extract.json
├── db/
│   └── migrations/
│       ├── 0001_initial.sql      ← Copy from spec/db/migrations/
│       ├── 0001a_schema_review_fixes.sql
│       └── 0002_canvas_layers.sql
├── backend/                      ← FastAPI (Python 3.12)
│   ├── pyproject.toml
│   ├── src/
│   │   ├── api/                  ← FastAPI routes
│   │   ├── core/                 ← Business logic (auth, RBAC, alarm eval)
│   │   ├── db/                   ← SQLAlchemy models, repositories
│   │   ├── edge/                 ← Edge gateway code (Modbus poller)
│   │   ├── events/               ← Event bus, alarm processing
│   │   ├── reports/              ← Report generation (arq worker)
│   │   └── ws/                   ← WebSocket manager
│   └── tests/
├── frontend/                     ← React 19 (TypeScript, Vite)
│   ├── package.json
│   ├── src/
│   │   ├── core/                 ← Framework-agnostic business logic (60-70% of FE code)
│   │   ├── ui/                   ← React components (import from core/)
│   │   ├── stores/               ← Zustand stores
│   │   └── hooks/                ← Custom React hooks
│   └── tests/
├── docker-compose.yml            ← Local dev (PG + TimescaleDB + Redis + PgBouncer)
├── .env.example                  ← All env vars with descriptions
├── .github/
│   └── workflows/
│       └── ci.yml                ← Lint → type → test → security → build → deploy
├── vercel.json                   ← Frontend deployment config
├── Dockerfile                    ← Backend container
├── SPEC_FEEDBACK.md              ← Your notes back to Arno (questions, gaps, issues)
└── ADR/                          ← Architecture Decision Records
    └── 0001-initial-decisions.md
```

## Build Phases

You are building **R1 — MVP**. Follow this sequence exactly:

### Phase 1: Foundation (Weeks 1-3)
1. **Scaffold** — Create the project structure above. Init git. Set up docker-compose (PostgreSQL 16 + TimescaleDB + Redis 7 + PgBouncer).
2. **Database** — Run migrations 0001, 0001a, 0002. Create database roles (`scada_app`, `scada_writer`, `scada_reader`) with least-privilege grants per SPEC.md A.5. Write RLS policies for all 11 enabled tables.
3. **Auth** — Implement the full user lifecycle (SPEC C.1): invite → onboard → login → MFA → password reset → sessions → disable. JWT (HS256, HttpOnly cookies, SameSite=Strict), argon2id (m=65536, t=3, p=4), TOTP with AES-256-GCM encrypted secrets, recovery codes in `core.recovery_code`.
4. **CI/CD** — GitHub Actions pipeline: ruff + eslint → mypy + tsc → pytest + vitest → pip-audit + npm audit → vite build → Vercel preview deploy.
5. **Config** — Doppler integration for secrets. `.env.example` with all variables.

### Phase 2: Real-time Core (Weeks 4-6)
1. **Edge gateway** — Modbus TCP poller with `ReadOnlyModbusClient` wrapper (FC03/FC04 only). Per-VLAN async polling with priority scheduler. SQLite local buffer. systemd service file.
2. **Telemetry pipeline** — Edge → cloud (INSERT ON CONFLICT DO NOTHING). Continuous aggregate refresh after buffer flush.
3. **WebSocket** — Real-time state broadcasting. JWT auth via cookie. 10 msg/sec throttle. Exponential backoff reconnection.
4. **Event bus** — Threshold evaluation, alarm generation, severity classification.

### Phase 3: Asset Management (Weeks 7-9)
1. **Asset CRUD** — All 6 entity types (main boards, breakers, measuring devices, distribution boards, tenant feeds, lighting circuits).
2. **Seed data** — Load from `spec/design/sld_per_mb_extract.json` (104 breakers, 9 main boards).

### Phase 4: Monitoring Dashboard (Weeks 10-12)
1. **Live dashboard** — Breaker state grid (open/closed/tripped/COMMS LOSS). Per-MB views.
2. **Alarm panel** — Live alarm feed, acknowledgement, severity filtering.
3. **Bypass detection** — Implement with pluggable `RelayStateProvider` (see SPEC C.6.1 for the 3 provider options).
4. **PQ trends** — Recharts line/area charts with date range and asset selectors.

### Phase 5: Power Quality & Integration (Weeks 13-14)
1. **PQ analytics** — Historical trends from continuous aggregates.
2. **Integration testing** — Against Modbus simulator.
3. **Commissioning readiness** — All 10 acceptance criteria from SPEC D.3.

## Critical Rules

### MONITORING ONLY
This system NEVER sends control commands. Modbus write function codes (FC06/FC16) are forbidden. The `ReadOnlyModbusClient` wrapper must be the only way to talk to devices. A unit test must verify that write methods raise RuntimeError. A CI grep check must verify FC06/FC16/write_register never appears in `backend/src/edge/`.

### Data Truth Chain
Every displayed value traces: Field device → Modbus register → Edge gateway → PostgreSQL → API → Browser. If any link is broken, display "COMMS LOSS" — never show stale data as current. If the last poll is older than 2× the poll interval, display "STALE" warning.

### Hallucination Prevention
- Every Modbus register address: use `# TODO: VERIFY_REGISTER — address assumed from ABB datasheet` until Profection confirms.
- Every asset reference: verify against `spec/design/sld_per_mb_extract.json`. If it's not in the JSON, it doesn't exist.
- Mock data ranges: V_L-N 210-253V, V_L-L 370-440V, PF 0.70-1.00, THD-V <8%, freq 49.5-50.5Hz.
- Never fabricate a register address, asset ID, or threshold value.

### Test Requirements
- pytest (Python) + Vitest (TypeScript)
- ≥80% coverage on changed files
- mypy strict + tsc strict — zero type errors
- ruff + eslint — zero lint errors
- All tests pass before any commit

### Security (from SECURITY_AUDIT_PREBUILD.md)
- MFA secrets: AES-256-GCM encrypted, key in Doppler (not env vars)
- Tokens: HttpOnly/Secure/SameSite=Strict cookies
- JWT: HS256, validate exp/iss/aud on ALL tokens, reject alg:none
- Password reset: no user enumeration, rate limit 3/email/hour
- Audit log: INSERT-only for scada_app role (REVOKE DELETE/UPDATE)
- DB roles: scada_app (API), scada_writer (edge), scada_reader (reports)
- RLS: concrete policies on all 11 tables — not "deferred"
- CSP + HSTS + security headers via Caddy or FastAPI middleware

## Communicating Back to Arno

When you encounter a spec gap, ambiguity, or question that blocks progress, write it to `SPEC_FEEDBACK.md` at the project root. Format:

```markdown
## [DATE] — [TOPIC]
**Status:** BLOCKING / QUESTION / SUGGESTION
**Phase:** [Which phase you're in]
**Detail:** [What you need]
**Workaround:** [What you're doing in the meantime, if anything]
```

Arno will read this file from his session and either update SPEC.md or respond directly.

## What Success Looks Like

At the end of R1 (Week 14), these things work:

1. All 104 breakers reporting state to the database within <1s
2. All M4M 30 PQ readings logging across all 9 main boards
3. All configured alarms triggering on simulated events
4. 48V relay bypass detection working (with whichever provider is confirmed)
5. Communication loss correctly distinguished from equipment fault
6. Tiered escalation delivering through all channels
7. All user roles functioning (Admin, Operator, Viewer)
8. Edge gateway resilience: local buffer works during internet outage
9. ≥80% test coverage, zero type errors, zero lint errors
10. Deployed to Railway (backend) + Vercel (frontend)
