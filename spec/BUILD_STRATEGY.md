# Kingswalk SCADA GUI — Build Strategy & Skill Map

**Date:** 2026-04-11 (v3 — aligned to R1/R2/R3 release sequence, architecture review integrated)
**Owner:** Watson Mattheus Consulting Electrical Engineers
**Purpose:** Define the complete build-out strategy so that Arno's only ongoing responsibility is maintaining `SPEC.md`. All code generation, testing, deployment, quality gates, and documentation is delegated to Claude sessions using the skill map, coding standards, and verification protocols below.

---

## 1. The Operating Model

### 1.1 Single source of truth

`SPEC.md` is the only file Arno edits directly. It describes **what** the system does, **who** uses it, **what** data it handles, and **what** constraints it must meet. Everything else — code, tests, migrations, CI pipelines, deployment configs, documentation — is generated and maintained by Claude sessions that read SPEC.md as their input.

### 1.2 The workflow

```
┌──────────────────┐
│  Arno edits      │
│  SPEC.md         │
│  (requirements)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Claude reads SPEC.md + BUILD_STRATEGY.md                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ Generate   │→ │ Run tests  │→ │ Hallucin.  │→ │ Code      │ │
│  │ code       │  │ (auto CI)  │  │ check      │  │ review    │ │
│  └────────────┘  └────────────┘  └────────────┘  └───────────┘ │
│         ALL MUST PASS BEFORE OUTPUT IS PRESENTED                │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
         ┌─────────────────────────┼───────────────────────┐
         ▼                         ▼                       ▼
  Vercel preview deploy     Git commit (PR)         Files presented
  (auto per branch)         (CI must be green)      to Arno
```

### 1.3 What Arno does vs. what Claude does

| Arno's responsibility | Claude's responsibility |
|---|---|
| Update `SPEC.md` when requirements change | Read SPEC.md and generate/update code to match |
| Accept or reject pull requests | Write the code, tests, migrations, and documentation |
| Review Claude's output for domain correctness | Run tests, hallucination checks, and code review before presenting |
| Commission and test on real ABB hardware | Generate mock data and simulators for dev/test |
| Sign off on design decisions (ADRs) | Draft ADR documents for Arno to approve |
| Manage Vercel project settings and custom domain | Configure Vercel deployment pipeline and environment variables |
| Approve user invite requests | Build the full user lifecycle (invite, onboard, reset, disable) |

---

## 2. AI Output Verification & Hallucination Prevention

This is a safety-critical industrial monitoring system. Code that hallucinates a Modbus register, invents an asset ID, or fabricates a threshold could mislead operational decisions. Every Claude session must follow these verification protocols.

### 2.1 Hallucination check categories

| Category | What can go wrong | How Claude must verify |
|---|---|---|
| **Asset data** | Inventing DB codes, breaker ratings, MP assignments that don't exist | Cross-check ALL asset references against `design/sld_per_mb_extract.json` (104 items) — if a DB code isn't in the extract, it doesn't exist |
| **Modbus registers** | Fabricating register addresses for ABB devices | All register addresses must reference ABB technical documentation. If the register address isn't confirmed, use a `TODO: VERIFY_REGISTER` placeholder — never guess |
| **Electrical values** | Generating unrealistic voltage, current, or power factor values in mock data | Mock data must stay within realistic LV distribution ranges: V_L-N 210–253V, V_L-L 370–440V, PF 0.70–1.00, THD-V <8%, frequency 49.5–50.5Hz |
| **Protocol details** | Wrong Modbus function codes, wrong IEC 61850 data objects | Modbus: FC03 (read holding registers), FC04 (read input registers) — **monitoring only, no write function codes (FC06/FC16) permitted**. IEC 61850: use standard LN classes only (XCBR, MMXU, MSQI) — read-only access |
| **SQL/schema** | Generating queries against non-existent tables or columns | Every query must be validated against `DB_SCHEMA.md`. Claude must `\dt` or read the migration before writing queries |
| **API contracts** | Inventing endpoints that don't exist yet | Every API call in frontend code must have a corresponding backend endpoint. Claude must verify both sides match |
| **Configuration** | Hardcoding values that should come from env/config | Zero hardcoded secrets, URLs, ports, or thresholds in code. All configurable values via environment or database |
| **Dependencies** | Importing packages that don't exist or are deprecated | Every `import` must be verified: `pip show <pkg>` or `npm ls <pkg>`. No phantom packages |

### 2.2 Mandatory verification steps (every Claude session)

Before presenting any code output, Claude must:

1. **Schema check** — Read `DB_SCHEMA.md` or run the migration. Confirm every table/column referenced in code actually exists.
2. **Asset check** — If code references specific assets (DB codes, MB codes, MP codes), confirm they exist in `sld_per_mb_extract.json`.
3. **Test execution** — Run `pytest` (API) and `npx vitest run` (frontend). All tests must pass. No skipped tests.
4. **Type check** — Run `mypy` (Python) and `tsc --noEmit` (TypeScript). Zero type errors.
5. **Lint check** — Run `ruff check` (Python) and `eslint` (TypeScript). Zero lint errors.
6. **Dependency check** — Confirm all imported packages are in `pyproject.toml` or `package.json`.
7. **Security scan** — Run `bandit` (Python) or `npm audit` on any new dependencies.
8. **Diff review** — Before committing, use `code-review` skill to review the diff for logic errors, missed edge cases, and SPEC compliance.

### 2.3 Hallucination-proof data flow

```
SLD drawings (PDF)
    │
    ▼ (pdftotext extraction — already done)
sld_per_mb_extract.json  ←── ONLY SOURCE OF ASSET TRUTH
    │
    ▼ (seed migration)
PostgreSQL (assets schema) ←── ONLY SOURCE OF RUNTIME TRUTH
    │
    ▼ (API queries)
FastAPI endpoints ←── ONLY SOURCE OF DATA FOR FRONTEND
    │
    ▼ (HTTP/WS)
React UI ←── NEVER HARDCODES ASSET DATA
```

**Rule:** No asset data is ever hardcoded in frontend or backend code. All asset data flows from the database, which is seeded from the extract, which is parsed from the drawings. If the drawing doesn't show it, it doesn't exist.

### 2.4 When Claude is uncertain

If Claude cannot verify a fact (register address, ABB protocol detail, electrical specification):
1. Insert a `# TODO: VERIFY — [specific question]` comment in the code
2. Add the item to `design/SLD_FIELD_MAP.xlsx` → Gaps & Actions sheet
3. Flag it explicitly to Arno in the output summary
4. **Never guess. Never fabricate. Mark and skip.**

---

## 3. Coding Standards & Architecture Patterns

### 3.1 Python (FastAPI backend)

| Rule | Enforcement |
|---|---|
| Python 3.12+, strict typing everywhere | `mypy --strict` in CI |
| Async-first: all I/O operations use `async/await` | Code review gate |
| Pydantic v2 for all request/response schemas | `data-validation-layer` skill |
| Repository pattern for database access (no raw SQL in route handlers) | Architecture review |
| Service layer between routes and repositories | `architecture-review` skill |
| One file = one concern. No god files >300 lines | Lint rule + code review |
| All exceptions inherit from `app.core.exceptions.AppError` | `error-handler` skill |
| Docstrings on every public function (Google style) | `ruff` rule D100–D107 |
| No `print()` statements — use structured logger only | `ruff` rule T201 |
| Secrets via environment variables only — never in code | `bandit` scan |

### 3.2 TypeScript (React frontend)

| Rule | Enforcement |
|---|---|
| TypeScript strict mode (`"strict": true` in tsconfig) | `tsc --noEmit` in CI |
| No `any` types — ever | ESLint `@typescript-eslint/no-explicit-any` |
| Framework-agnostic core in `/src/core/` — no React imports | ESLint rule restricting React imports in `/core/` |
| React components in `/src/ui/` only | Directory structure + code review |
| Zustand for all state management — no prop drilling past 2 levels | Code review gate |
| Zod schemas mirror Pydantic schemas (shared types via codegen) | `data-validation-layer` skill |
| All API calls go through `/src/core/api-client.ts` — never raw fetch in components | ESLint rule + code review |
| CSS via Tailwind only — no inline styles, no CSS modules | ESLint plugin |
| Components must have display name and JSDoc description | ESLint rule |
| Max component file size: 200 lines. Extract hooks, extract sub-components | Code review |

### 3.3 SQL / Database

| Rule | Enforcement |
|---|---|
| All schema changes via numbered migrations — never manual DDL | Migration runner (Alembic / dbmate) |
| Migrations are idempotent (`IF NOT EXISTS`, `IF EXISTS` guards) | Code review |
| Every FK has an index | `database-query-optimizer` audit |
| No `SELECT *` in production code | `ruff` / code review |
| All queries parameterised — no string interpolation | `bandit` scan |
| Hypertable chunk intervals documented in migration comments | Code review |

### 3.4 Architecture layers

```
┌─────────────────────────────────────────────────────┐
│ FRONTEND (React)                                    │
│  /src/core/     — models, API client, WS manager    │  Framework-agnostic
│  /src/stores/   — Zustand stores                     │  Framework-agnostic
│  /src/ui/       — components, pages, hooks           │  React-specific
└──────────────────────────┬──────────────────────────┘
                           │ HTTPS / WSS
┌──────────────────────────┴──────────────────────────┐
│ BACKEND (FastAPI)                                   │
│  /app/routes/    — thin HTTP handlers (validate →   │
│                    call service → return response)   │
│  /app/services/  — business logic, no I/O           │
│  /app/repos/     — database access (SQLAlchemy)     │
│  /app/ws/        — WebSocket handlers               │
│  /app/core/      — config, auth, logging, errors    │
└──────────────────────────┬──────────────────────────┘
                           │ SQL / Redis
┌──────────────────────────┴──────────────────────────┐
│ DATA (PostgreSQL + TimescaleDB + Redis)             │
└──────────────────────────┬──────────────────────────┘
                           │ Internal (Redis queue)
┌──────────────────────────┴──────────────────────────┐
│ EDGE (Modbus TCP gateway)                           │
│  /edge/poller/      — pymodbus async poller         │
│  /edge/writer/      — command execution             │
│  /edge/simulator/   — mock devices for dev          │
└─────────────────────────────────────────────────────┘
```

---

## 4. Code Review & Quality Gates

### 4.1 Review protocol (every phase)

Every piece of code Claude generates passes through a three-tier review before it reaches Arno:

| Gate | What it checks | Skill | Blocks merge? |
|---|---|---|---|
| **Gate 1: Automated CI** | Tests pass, types check, lint clean, coverage ≥80% | `cicd-pipeline-writer` | YES |
| **Gate 2: AI code review** | Logic errors, SPEC compliance, security, edge cases, naming | `code-review` | YES |
| **Gate 3: Architecture review** | Layering violations, dependency direction, scalability | `architecture-review` | YES (Phase 3, 6, 8) |
| **Gate 4: Security audit** | OWASP top 10, injection, auth bypass, privilege escalation | `security-audit` | YES (Phase 1, 4, 8) |
| **Gate 5: Arno domain review** | Does this match the electrical installation reality? | Manual | YES |

### 4.2 Code review checklist (Claude runs `code-review` with this)

```
[ ] Does the code match SPEC.md requirements for this phase?
[ ] Are all asset references validated against sld_per_mb_extract.json?
[ ] Are all DB queries validated against DB_SCHEMA.md?
[ ] Is there a test for every public function?
[ ] Is there a test for every error path (not just happy path)?
[ ] Are all configurable values in environment/config (no hardcoded magic numbers)?
[ ] Is every API endpoint authenticated and role-gated?
[ ] Is every mutation audit-logged?
[ ] Are all user inputs validated (Pydantic + Zod)?
[ ] Is the code under 300 lines per file?
[ ] Are there no TODO/FIXME/HACK comments left unresolved?
[ ] Does the frontend follow the core/ui split?
[ ] Are all new dependencies justified and security-scanned?
```

---

## 5. Automated Testing Pipeline

### 5.1 Testing pyramid

```
                    ┌───────────┐
                    │  E2E      │  Playwright — critical user flows
                    │  (slow)   │  Runs: pre-merge, nightly
                    ├───────────┤
                    │Integration│  API + DB + Redis together
                    │  (medium) │  Runs: every push
                ┌───┴───────────┴───┐
                │   Unit tests      │  Isolated functions/components
                │   (fast)          │  Runs: every push
                └───────────────────┘
```

### 5.2 CI pipeline (GitHub Actions on Vercel)

```yaml
# Triggered on: push to any branch, PR to main
jobs:
  lint:        ruff check + eslint + prettier
  typecheck:   mypy --strict + tsc --noEmit
  unit-test:   pytest (API) + vitest (web)       # Coverage ≥80%
  integ-test:  pytest (with test DB)              # All endpoints
  security:    bandit (Python) + npm audit (web)
  build:       vite build (web) + Docker build (API)
  e2e:         playwright (against Vercel preview) # Pre-merge only
  coverage:    upload to Codecov, fail if <80%
```

### 5.3 CI gates — what blocks a merge

| Check | Threshold | Blocks merge? |
|---|---|---|
| Unit tests pass | 100% pass | YES |
| Integration tests pass | 100% pass | YES |
| E2E tests pass | 100% pass (critical flows) | YES |
| Python type check (mypy) | 0 errors | YES |
| TypeScript type check (tsc) | 0 errors | YES |
| Lint (ruff + eslint) | 0 errors | YES |
| Line coverage (pytest-cov) | ≥80% | YES |
| Branch coverage (pytest-cov) | ≥70% | YES |
| Frontend coverage (vitest) | ≥80% | YES |
| Security scan (bandit) | 0 high/critical | YES |
| Dependency audit (npm audit) | 0 critical | YES |
| Bundle size (web) | <500KB gzipped | WARNING (soft) |
| Lighthouse score | ≥90 performance | WARNING (soft) |

### 5.4 Test data strategy

| Environment | Data source | Refresh |
|---|---|---|
| Unit tests | In-memory fixtures, factory functions | Per test run |
| Integration tests | Dockerised PG with test migrations + seed | Per test suite |
| E2E tests | Vercel preview + seeded test DB | Per deployment |
| Dev (local) | Modbus simulator + mock data generator | On demand |
| Staging | Modbus simulator + 30 days of synthetic telemetry | Weekly |
| Production | Real ABB field devices | Live |

---

## 6. Vercel Deployment & Environment Management

### 6.1 Architecture on Vercel

```
                        Vercel
                    ┌──────────────────────────────┐
                    │  React SPA (static build)    │  ← Vite output
                    │  served from Vercel Edge CDN  │
                    │  Custom domain: scada.kw.co.za│
                    └──────────────┬───────────────┘
                                   │ HTTPS (Vercel auto-TLS)
                                   │
              ┌────────────────────┴────────────────────┐
              │  Vercel Serverless Functions (optional)  │  ← API proxy / BFF
              │  OR external API host                    │
              └────────────────────┬────────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │  FastAPI backend                         │
              │  Hosted on: Railway / Render / VPS      │
              │  (not Vercel — needs persistent WS +    │
              │   background workers + Modbus gateway)  │
              └────────────────────┬────────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │  PostgreSQL + TimescaleDB + Redis        │
              │  Hosted on: Supabase / Railway / VPS    │
              └─────────────────────────────────────────┘
```

**Why split:** Vercel excels at static SPA hosting with edge CDN, automatic TLS, and preview deployments. But the SCADA backend needs persistent WebSocket connections, background Modbus polling, and Redis queues — none of which fit Vercel's serverless model. The frontend goes on Vercel; the backend goes on a persistent host.

### 6.2 Vercel environments

| Environment | Branch | URL | Purpose |
|---|---|---|---|
| **Production** | `main` | `scada.kingswalk.co.za` | Live operator access |
| **Staging** | `staging` | `staging-scada.kingswalk.co.za` | Pre-release testing with simulator |
| **Preview** | Any PR branch | `pr-{n}-scada.vercel.app` | Per-PR preview for review |
| **Development** | `develop` | `dev-scada.vercel.app` | Latest dev build |

### 6.3 Vercel configuration

| Setting | Value |
|---|---|
| Framework preset | Vite |
| Build command | `cd web && npm run build` |
| Output directory | `web/dist` |
| Node version | 20 |
| Environment variables | `VITE_API_URL`, `VITE_WS_URL`, `VITE_ENV` — per environment |
| Preview comments | Enabled — every PR gets a deploy preview link |
| Web Analytics | Enabled — page load, CWV tracking |
| Speed Insights | Enabled — real user monitoring |
| Protection | Password protection on staging/preview (Vercel Authentication) |

### 6.4 Deployment workflow

```
Arno updates SPEC.md
    │
    ▼
Claude generates code → creates PR → pushes to branch
    │
    ▼
GitHub Actions CI runs (lint, type, test, security) ─── FAIL → fix and re-push
    │ PASS
    ▼
Vercel auto-deploys preview ─── PR gets preview URL comment
    │
    ▼
Arno reviews preview + PR diff
    │ APPROVE
    ▼
Merge to `main` → Vercel auto-deploys to production
```

### 6.5 Skills for Vercel setup

| Task | Skill(s) |
|---|---|
| Vercel project config (`vercel.json`, env vars) | `configuration-system` |
| GitHub Actions + Vercel integration | `cicd-pipeline-writer` |
| Custom domain + TLS | `configuration-system` |
| Preview environment protection | `auth-system-builder` |
| Deployment monitoring | `monitoring-alert-system` |

---

## 7. User Management System (Full Lifecycle)

Phase 1 in the previous version only covered auth (JWT + RBAC). A real system needs the full user lifecycle.

### 7.1 User lifecycle

```
Admin creates invite
    │
    ▼
Invite email sent (magic link, 72hr expiry)
    │
    ▼
User clicks link → set password + setup MFA
    │
    ▼
User active (can login)
    │
    ├── User logs in → JWT issued → session active
    ├── User requests password reset → reset email → new password
    ├── User updates profile (name, email, notification preferences)
    ├── Admin changes user role (Viewer → Operator → Admin)
    ├── Admin disables user → soft delete → sessions revoked
    └── Admin re-enables user → account restored
```

### 7.2 User management features

| Feature | Backend | Frontend | Skill(s) |
|---|---|---|---|
| **Invite flow** | `POST /api/users/invite` — generates magic link token, sends email | Admin panel: invite form (email, role, name) | `auth-system-builder`, `notification-system-builder` |
| **Onboarding** | `POST /api/auth/activate` — validates token, sets password | Set password page + MFA setup wizard | `auth-system-builder`, `web-artifacts-builder` |
| **Login** | `POST /api/auth/login` — argon2id verify, TOTP check, JWT issue | Login page with MFA step | `auth-system-builder` |
| **Password reset** | `POST /api/auth/forgot-password` → email with reset link | Forgot password page + new password form | `auth-system-builder`, `notification-system-builder` |
| **Profile management** | `PATCH /api/users/me` — name, email, notification prefs | Profile page with edit form | `api-endpoint-generator`, `web-artifacts-builder` |
| **MFA management** | `POST /api/auth/mfa/setup`, `DELETE /api/auth/mfa` | MFA settings page (enable, disable, recovery codes) | `auth-system-builder` |
| **Role management** | `PATCH /api/users/{id}/role` — Admin only | Admin panel: user list with role dropdown | `middleware-creator`, `web-artifacts-builder` |
| **User disable/enable** | `DELETE /api/users/{id}` (soft), `POST /api/users/{id}/restore` | Admin panel: disable button + confirmation | `api-endpoint-generator` |
| **Session management** | `GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}` | Active sessions list with revoke button | `auth-system-builder` |
| **Audit trail** | All of the above logged to `core.audit_log` | Audit log viewer (Admin only, filterable) | `event-system-designer`, `web-artifacts-builder` |

### 7.3 Database additions for user lifecycle

```sql
-- Added to core schema
CREATE TABLE core.invite (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           citext NOT NULL,
    role            core.user_role NOT NULL,
    token_hash      text NOT NULL,          -- argon2id hash of magic link token
    invited_by      uuid REFERENCES core.users(id),
    expires_at      timestamptz NOT NULL,
    accepted_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.password_reset (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         uuid NOT NULL REFERENCES core.users(id),
    token_hash      text NOT NULL,
    expires_at      timestamptz NOT NULL,
    used_at         timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.session (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         uuid NOT NULL REFERENCES core.users(id),
    refresh_hash    text NOT NULL,          -- hash of refresh token
    ip              inet,
    user_agent      text,
    expires_at      timestamptz NOT NULL,
    revoked_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
```

---

## 8. Messaging & Email Systems

### 8.1 Email service (transactional)

| Email type | Trigger | Template | Skill(s) |
|---|---|---|---|
| **Invite** | Admin invites new user | Welcome + magic link + role info | `notification-system-builder` |
| **Password reset** | User requests reset | Reset link (1hr expiry) | `notification-system-builder` |
| **MFA recovery** | User requests recovery codes | Recovery code list (one-time view) | `notification-system-builder` |
| **Alert notification** | Threshold breached, breaker trip | Severity-coloured alert card with asset details | `notification-system-builder`, `email-automation-sequence` |
| **Alert escalation** | Alert unacknowledged after N minutes | Escalation notice to supervisor | `notification-system-builder`, `cron-job-builder` |
| **Report delivery** | Monthly report generated | Report summary + PDF/XLSX attachment | `notification-system-builder`, `report-generation-automator` |
| **Account disabled** | Admin disables user | Notification of account suspension | `notification-system-builder` |

### 8.2 Email provider strategy

| Provider | Use case | Cost | Notes |
|---|---|---|---|
| **Resend** (recommended) | All transactional email | Free tier: 3,000/month, then $0.50/1000 | Modern API, React Email templates, good deliverability |
| **Postmark** (alternative) | Transactional only | $1.25/1000 | Excellent deliverability, dedicated IPs |
| **SMTP (self-hosted)** | Fallback | R0 | Postfix on backend host, for environments without internet |

**Implementation:** Abstract email behind an `EmailService` interface in `/api/app/core/email.py`. Swap providers via environment variable (`EMAIL_PROVIDER=resend|postmark|smtp`).

### 8.3 In-app messaging

| Channel | Implementation | Skill(s) |
|---|---|---|
| **Toast notifications** | WebSocket push → Zustand store → Radix Toast component | `notification-system-builder`, `dashboard-backend` |
| **Notification centre** | Persistent notifications in DB → API → bell icon dropdown | `notification-system-builder`, `web-artifacts-builder` |
| **Alert banner** | Critical alerts displayed as full-width banner until acknowledged | `web-artifacts-builder`, `state-machine-builder` |

### 8.4 SMS alerts (optional, Phase 8+)

For critical-severity alerts (breaker trip on anchor feeder, total comms loss):

| Provider | Notes |
|---|---|
| **BulkSMS** (SA-based) | ZAR billing, good SA network coverage, API-first |
| **Twilio** | USD billing, global coverage, higher cost |

**Implementation:** Same `NotificationService` interface, SMS channel added as a delivery option. User configures phone number and opt-in per severity level in their profile.

### 8.5 Notification preference model

```sql
CREATE TABLE core.notification_preference (
    id              serial PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES core.users(id),
    channel         text NOT NULL CHECK (channel IN ('email','in_app','sms','webhook')),
    severity_min    events.severity NOT NULL DEFAULT 'warning',
    enabled         boolean NOT NULL DEFAULT true,
    config          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- email address, phone, webhook URL
    UNIQUE (user_id, channel)
);
```

---

## 9. Build Phases — Aligned to R1/R2/R3 Release Sequence

**Hard deadline:** R1 MVP operational and testing-ready within 14 weeks (by ~2026-07-18).
**System scope:** MONITORING ONLY — no remote control of breakers or lighting. All physical switching is performed on site by authorised personnel.

### PHASE 1 — Foundation, Auth & Infrastructure Hardening (Weeks 1–3)
**SPEC sections:** B.2, B.3, B.3.2–B.3.6, C.1
**Deliverable:** Monorepo scaffold, CI/CD, cloud infra, auth lifecycle, edge gateway skeleton with architecture hardening.

| Task | Skill(s) | Output |
|---|---|---|
| Project scaffold (monorepo: `/api`, `/web`, `/edge`, `/db`) | `configuration-system` | Repo structure, env files, Docker Compose |
| PostgreSQL 16 + TimescaleDB schema + PgBouncer | `data-schema-designer` | Validate `0001_initial.sql`, PgBouncer config (§B.3.4) |
| Database migration runner (Alembic) | `data-migration-script` | Alembic config + initial migration |
| FastAPI project skeleton | `api-endpoint-generator` | `/api` with health check, CORS (§B.3.6), middleware |
| React (Vite+TS) project skeleton | `web-artifacts-builder` | `/web` with Vite, Tailwind, Radix, React Router |
| CI/CD pipeline (GitHub Actions) | `cicd-pipeline-writer` | Lint, type, test, security, build, deploy |
| Vercel project setup | `configuration-system` | `vercel.json`, env vars, preview deploys |
| Cloud region selection + hosting setup | `configuration-system` | AWS af-south-1 or Azure SA North (§B.3.6) |
| Health check endpoint | `health-check-endpoint` | `GET /healthz` on backend + edge gateway `/health` (§B.3.2) |
| Structured logging (`structlog`, JSON) | `logging-system` | JSON logging with request IDs on all components |
| Error handling patterns | `error-handler` | Global exception handlers |
| Coding standards config | `configuration-system` | ruff, mypy, eslint, prettier, tsconfig strict |
| `.env` schema + secrets management | `configuration-system` | Documented env vars, secrets manager (§B.3.6) |
| Redis AOF configuration | `configuration-system` | `appendfsync=everysec` for session persistence (§B.3.6) |
| Auth system (JWT + refresh, argon2id, TOTP MFA) | `auth-system-builder` | `/api/auth/` endpoints |
| Invite flow (magic link, email, expiry) | `auth-system-builder`, `notification-system-builder` | `/api/users/invite` + email template |
| Password reset flow | `auth-system-builder`, `notification-system-builder` | `/api/auth/forgot-password` + email |
| RBAC middleware (Admin, Operator, Viewer) | `middleware-creator` | Permission decorators |
| User CRUD + role management | `api-endpoint-generator` | `/api/users/` full lifecycle |
| Session management (list, revoke) | `auth-system-builder` | `/api/auth/sessions` |
| Rate limiting on auth endpoints (IP-based) | `rate-limiter` | 5 attempts per IP per 15 minutes (§A.5) |
| Email service integration (Resend) | `notification-system-builder` | `EmailService` abstraction |
| Audit log (immutable, every mutation) | `event-system-designer` | `core.audit_log` auto-middleware |
| Input validation (Pydantic + Zod) | `data-validation-layer` | Shared validation schemas |
| Login + MFA + onboarding UI | `web-artifacts-builder` | Login page, MFA step, set-password wizard |
| Admin panel — user management UI | `web-artifacts-builder` | User list, invite, role change, disable |
| Unit + integration tests | `unit-test-writer`, `integration-test-writer` | Auth flow end-to-end |
| Security audit (auth) | `security-audit` | OWASP auth checklist |

**Quality gate:** CI pipeline green. Auth lifecycle end-to-end on Vercel preview. PgBouncer + Redis AOF configured.

---

### PHASE 2 — Real-Time Monitoring Core (Weeks 4–8)
**SPEC sections:** B.3.2, B.4, B.5, B.6, C.2, C.3, C.6
**Deliverable:** Edge gateway polling all VLANs, live breaker state + PQ data flowing to cloud, bypass detection active, alarms triggering.

| Task | Skill(s) | Output |
|---|---|---|
| Seed migration from `sld_per_mb_extract.json` | `data-migration-script` | `0002_seed_assets.sql` — 104 breakers, 9 MBs, verified |
| Asset registry CRUD (all types) | `api-endpoint-generator` | `/api/assets/` endpoints for MB, breaker, device, DB, tenant |
| Per-asset document repository | `file-upload-handler` | Object storage + `assets.asset_document` |
| Edge gateway: per-VLAN async polling (§B.3.2) | `data-pipeline-builder` | 9 independent `AsyncModbusTcpClient` loops |
| Edge gateway: systemd service + watchdog (§B.3.2) | `configuration-system` | `Restart=always`, `WatchdogSec=30`, `sd_notify` heartbeat |
| Edge gateway: local buffer + rate-limited flush (§B.3.2) | `data-pipeline-builder` | SQLite buffer, 500-row batch flush, `ON CONFLICT DO NOTHING` |
| Edge gateway: polling priority scheduler (§B.3.2) | `state-machine-builder` | Breaker 250ms > PQ 1s > THD 5s > energy 30s > counters 60s |
| VPN tunnel: WireGuard + dual-path failover (§B.3.3) | `configuration-system` | PersistentKeepalive=25, fibre primary + 4G secondary |
| Cloud-side edge gateway watchdog alarm | `monitoring-alert-system` | CRITICAL alarm if no telemetry for >30s |
| WebSocket layer (per-MB pub/sub via Redis) | `dashboard-backend` | State changes pushed to browser <1s |
| WebSocket authentication (JWT required) | `auth-system-builder` | Unauthenticated connections rejected |
| WebSocket reconnection protocol (§B.3.5) | `dashboard-backend` | Backoff + jitter + full state sync + "Reconnecting..." banner |
| Telemetry ingestion endpoint (mTLS or API key) | `api-endpoint-generator` | Defence-in-depth on edge→cloud path (§A.5) |
| Breaker state monitoring + state transition logging | `event-system-designer` | `telemetry.breaker_state` with `(breaker_id, ts DESC)` index |
| 48V relay bypass detection (§C.6.1) | `state-machine-builder` | CRITICAL alarm with full operator context |
| Communication loss vs equipment fault distinction (§C.6.2) | `state-machine-builder` | "COMMS LOSS" grey overlay, tiered escalation |
| Event system (types, severity, routing) | `event-system-designer` | `events.event` with `(asset_id, ts DESC)` index |
| Threshold engine (per-asset, hysteresis) | `state-machine-builder` | Threshold evaluator against `events.threshold` |
| Notification service (multi-channel) | `notification-system-builder` | In-app toast + email + SMS dispatch |
| Tiered escalation (§C.6.3) | `cron-job-builder`, `notification-system-builder` | 15min → SMS operator, 30min → SMS admin |
| Live alarm panel + alarm acknowledgement | `web-artifacts-builder`, `state-machine-builder` | Real-time alarm list, Unacked → Acked → Cleared |
| Alert configuration UI | `web-artifacts-builder` | Threshold CRUD per asset |
| Live monitoring dashboard | `web-artifacts-builder`, `react-component-optimizer` | Breaker state overview, PQ readings, alarm badges |
| Modbus simulator (for dev/test) | `mock-data-generator` | Simulated 9-VLAN Modbus responses |
| Unit + integration tests | `unit-test-writer`, `integration-test-writer` | Polling, bypass detection, escalation, WS reconnect |

**Quality gate:** All 104 breakers reporting simulated state <1s. Bypass alarm triggers on simulated scenario. Comms loss correctly distinguished. All alarms firing.

---

### PHASE 3 — Power Quality & Data Logging (Weeks 9–12)
**SPEC sections:** B.4 (telemetry schema), C.3, C.4
**Deliverable:** Full PQ data logging, continuous aggregates, historical trends, device replacement tracking.

| Task | Skill(s) | Output |
|---|---|---|
| PQ sample ingestion (M4M 30 data) | `data-pipeline-builder` | `telemetry.pq_sample` hypertable, 1s polling |
| Energy register logging | `data-pipeline-builder` | `telemetry.energy_register` hypertable, 30s polling |
| Lighting state monitoring + burn hours | `data-pipeline-builder` | `telemetry.lighting_state`, accumulated burn hours |
| TimescaleDB continuous aggregates | `database-query-optimizer` | pq_1min, pq_15min, pq_hourly, pq_daily |
| Aggregate refresh after buffer flush (§B.3.6) | `database-query-optimizer` | `CALL refresh_continuous_aggregate()` for affected ranges |
| Retention policies | `data-migration-script` | Raw 90d, 15min 5yr, daily indefinite |
| Report worker separation (`arq`) (§B.3.6) | `queue-system-builder` | Dedicated worker process, statement_timeout=120s |
| PQ trend charts (historical) | `web-artifacts-builder` | Recharts/ECharts, date range + asset selector |
| Device replacement tracking UI | `web-artifacts-builder` | Record replacement date, counters reset from that date |
| Performance optimization | `performance-optimizer`, `caching-strategy` | Query optimization, Redis caching for hot paths |
| Unit + integration tests | `unit-test-writer`, `integration-test-writer` | Aggregate accuracy, retention, trend chart data |

**Quality gate:** All 18 M4M 30 devices logging PQ. Continuous aggregates materialising. Historical trends rendering. Replacement date resets counters.

---

### PHASE 4 — Commissioning Testing & R1 Hardening (Weeks 13–14)
**SPEC sections:** D.3, Part E
**Deliverable:** R1 MVP ready for commissioning plug-in with real ABB hardware.

| Task | Skill(s) | Output |
|---|---|---|
| Integration testing against first live MB | Manual + `integration-test-writer` | Real Modbus data flowing end-to-end |
| Commissioning acceptance criteria validation (D.3, items 1–6, 9–10) | `integration-test-writer` | All 10 acceptance items verified |
| Load testing (28 users, 150 WS connections) | `load-testing-script` | k6 script + baseline report |
| Security audit (full system) | `security-audit` | OWASP top 10, auth flows, mTLS, CORS |
| POPIA compliance review | `compliance-checking-ai` | Data handling audit |
| API documentation (OpenAPI) | `write-documentation` | Auto-generated + narrative |
| Operator quick-start guide | `write-documentation`, `docx` | Alarm response procedures, navigation guide |
| Vercel production deployment | `configuration-system` | Custom domain, env vars, protection |
| Backend production deployment | `configuration-system` | Cloud hosting, Docker, PgBouncer |
| Database production setup + backup | `configuration-system` | PG + TimescaleDB, daily backup, WAL archiving |
| Infrastructure monitoring | `monitoring-alert-system` | Edge health, VPN state, PG connections, disk |
| Hallucination audit | `code-review` | All asset refs match extract, all queries match schema |
| Dependency audit | `security-audit` | All deps current, no known CVEs |

**Quality gate:** All commissioning acceptance criteria (D.3) demonstrated. R1 sign-off.

---

### PHASE 5 — R2: Usage, Reporting & Burn Hours (~Weeks 15–18)
**SPEC sections:** C.5, D.1 (R2)
**Deliverable:** Monthly reports, burn hour tracking, switching cycle counters, export pipeline.

| Task | Skill(s) | Output |
|---|---|---|
| Report template system | `report-generator` | `reports.template` + `reports.schedule` CRUD |
| Monthly automated reports (usage, errors, PQ) | `report-generation-automator`, `cron-job-builder` | Cron-triggered, queued via Redis/arq worker |
| PDF export | `pdf` | Branded PDF report generation |
| CSV/XLSX export | `xlsx` | Energy billing workbooks |
| Report distribution (email + dashboard) | `notification-system-builder` | Configurable distribution lists |
| Burn hour counters (accurate from replacement date) | `database-query-optimizer` | Counter queries respect `replaced_at` |
| Switching cycle counters | `database-query-optimizer` | Count state transitions per breaker |
| Report download UI | `web-artifacts-builder` | Report history, download links |
| Notification preferences UI | `web-artifacts-builder` | Per-channel, per-severity opt-in |
| Profile settings page | `web-artifacts-builder` | Profile edit + notification preferences |
| PostgreSQL read replica (if needed) | `configuration-system` | Route dashboard reads to replica |
| Unit + integration tests | `unit-test-writer`, `integration-test-writer` | Report accuracy, export format validation |

**Quality gate:** Monthly reports generating and distributing. Burn hour counters verified accurate.

---

### PHASE 6 — R3: Visual Navigation & Training (~Weeks 19–22)
**SPEC sections:** C.2.1, D.1 (R3)
**Deliverable:** Floor plan canvas, SLD topology canvas, cross-canvas navigation, operator training.

| Task | Skill(s) | Output |
|---|---|---|
| SVG canvas renderer (React + d3-zoom) | `web-artifacts-builder` | Zoomable, pannable SVG canvas component |
| SLD topology canvas (from 643.E.300) | `web-artifacts-builder` | MB → breaker → DB hierarchy with live state overlay |
| Floor plan canvas (from 2239-100-0) | `web-artifacts-builder` | Tenant zones, MB rooms, DB positions |
| Canvas layer system (toggle, LOD, z-order) | `web-artifacts-builder` | Layer panel, auto-show/hide by zoom level |
| Cross-canvas navigation (SLD ↔ floor plan) | `web-artifacts-builder` | "Show on Floor Plan" / "Show on SLD" drill-through |
| Real-time state overlay via WebSocket | `dashboard-backend` | Colour-coded hotspots, pulsing alarm badges |
| Canvas hotspot mapping (200+ assets) | `sld-extraction` | Populate `canvas_hotspot` table |
| SLD extraction pipeline | `sld-extraction` | PDF → SVG → hotspot geometry |
| Operator training documentation | `write-documentation`, `docx` | Full operator manual |
| Developer documentation | `write-documentation` | Architecture guide, API reference, onboarding |
| Final architecture review | `architecture-review` | Scalability validation, tech debt audit |
| Prometheus metrics + Grafana dashboards | `monitoring-alert-system` | Infrastructure observability |
| Backup & recovery runbook | `write-documentation` | PG backup, PITR, failover procedures |
| Unit + E2E tests | `unit-test-writer`, `integration-test-writer` | Canvas rendering, navigation, hotspot clicks |

**Quality gate:** Full visual interface operational. Untrained operator can navigate from alarm to physical location. All commissioning acceptance criteria (D.3) including items 7–8 demonstrated.

---

## 10. Complete Skill Registry (Updated)

| Category | # | Skills |
|---|---|---|
| Backend & API | 12 | `api-endpoint-generator`, `auth-system-builder`, `middleware-creator`, `data-validation-layer`, `rate-limiter`, `error-handler`, `health-check-endpoint`, `webhook-handler`, `pagination-implementer`, `search-implementer`, `queue-system-builder`, `retry-logic-implementer` |
| Data & Database | 7 | `data-schema-designer`, `data-migration-script`, `database-query-optimizer`, `data-pipeline-builder`, `data-quality-monitor`, `caching-strategy`, `mock-data-generator` |
| Frontend & UI | 4 | `web-artifacts-builder`, `react-component-optimizer`, `performance-optimizer`, `dashboard-backend` |
| Architecture | 5 | `event-system-designer`, `state-machine-builder`, `configuration-system`, `notification-system-builder`, `architecture-review` |
| Testing & Quality | 5 | `unit-test-writer`, `integration-test-writer`, `load-testing-script`, `security-audit`, `compliance-checking-ai` |
| Reporting & Docs | 6 | `report-generator`, `report-generation-automator`, `pdf`, `xlsx`, `cron-job-builder`, `file-upload-handler` |
| DevOps & Deploy | 4 | `cicd-pipeline-writer`, `logging-system`, `monitoring-alert-system`, `release-management-automation` |
| Documentation | 3 | `write-documentation`, `docx`, `code-review` |
| Messaging & Email | 2 | `notification-system-builder`, `email-automation-sequence` |
| **Total** | **48** | |

---

## 11. Project File Structure (Updated)

```
009. SCADA/
├── DRAWINGS/
│   ├── SCHEMATIC OVERVIEW/          ← Source SLD PDFs (643.E.300–309)
│   └── FLOOR PLAN/                  ← Mall floor plan PDF
├── EQUIPMENT SPECIFICATIONS/        ← ABB datasheets (M4M 30, Datalogger, PDCOM)
└── KINGSWALK SCADA GUI/
    ├── SPEC.md                      ← Master orchestration document (v4.0)
    ├── BUILD_STRATEGY.md            ← This document (v3 — R1/R2/R3 aligned)
    ├── SKILLS.md                    ← Catalogue of all 50 skills
    ├── TECHNOLOGY_ASSESSMENT.md     ← Framework decision (full)
    ├── FRONTEND_FRAMEWORK_DECISION.md ← Framework decision (summary)
    ├── DB_SCHEMA.md                 ← Schema reference
    ├── skills/                      ← 50 skill SKILL.md files
    │   ├── sld-extraction/          ← PDF extraction pipeline (custom)
    │   ├── api-endpoint-generator/
    │   ├── auth-system-builder/
    │   └── ... (48 more)
    ├── design/
    │   ├── SLD_FIELD_MAP.xlsx       ← Master inventory & network plan (8 sheets)
    │   ├── sld_per_mb_extract.json  ← Per-MB extract (104 items — asset truth)
    │   └── sld_overview_extract.json ← Overview extract (topology + areas)
    ├── docs/
│   ├── adr/                         ← Architectural Decision Records
│   ├── operator-manual/             ← End-user documentation
│   └── developer-guide/             ← Developer onboarding
├── api/                             ← FastAPI backend
│   ├── app/
│   │   ├── auth/                    ← Login, invite, reset, MFA, sessions
│   │   ├── assets/                  ← Asset CRUD
│   │   ├── telemetry/               ← PQ data, historical queries
│   │   ├── events/                  ← Event pipeline, thresholds
│   │   ├── reports/                 ← Report engine, scheduling
│   │   ├── notifications/           ← Multi-channel dispatch
│   │   ├── core/                    ← Config, logging, middleware, email
│   │   └── ws/                      ← WebSocket server
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── alembic/                     ← Migration runner
│   └── pyproject.toml
├── web/                             ← React SPA (deployed to Vercel)
│   ├── src/
│   │   ├── core/                    ← Framework-agnostic TS
│   │   │   ├── api-client.ts        ← Single HTTP client
│   │   │   ├── ws-manager.ts        ← WebSocket connection manager
│   │   │   ├── models/              ← TypeScript interfaces (mirror Pydantic)
│   │   │   └── validators/          ← Zod schemas (mirror Pydantic)
│   │   ├── stores/                  ← Zustand stores
│   │   │   ├── auth-store.ts
│   │   │   ├── asset-store.ts
│   │   │   ├── telemetry-store.ts
│   │   │   └── notification-store.ts
│   │   ├── ui/                      ← React-specific
│   │   │   ├── components/          ← Shared components
│   │   │   ├── pages/               ← Route pages
│   │   │   ├── layouts/             ← Shell layouts (sidebar, topbar)
│   │   │   └── hooks/               ← Custom React hooks
│   │   └── routes/                  ← React Router config
│   ├── tests/
│   ├── e2e/                         ← Playwright tests
│   ├── vercel.json                  ← Vercel config
│   └── package.json
├── edge/                            ← Modbus TCP edge gateway (monitoring only)
│   ├── poller/                      ← Per-VLAN async polling loops
│   ├── buffer/                      ← Local SQLite buffer for VPN outages
│   ├── simulator/                   ← Mock Modbus devices for dev/test
│   └── tests/
├── db/
│   └── migrations/
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.test.yml      ← Test environment (PG + Redis)
│   └── .github/workflows/
│       ├── ci.yml                   ← Main CI pipeline
│       ├── deploy-api.yml           ← Backend deployment
│       └── vercel-preview.yml       ← Vercel preview comments
└── scripts/
    ├── seed.py
    ├── simulate.py
    └── verify-extract.py            ← Validates code against SLD extract
```

---

## 12. Phase Dependencies & Timeline (Aligned to R1/R2/R3)

```
═══════════════════════════ R1 — MVP (14 weeks) ═══════════════════════════

Phase 1 ─── Foundation + Auth + Infra ──── Weeks 1–3
  │
  ▼
Phase 2 ─── Real-Time Monitoring Core ──── Weeks 4–8
  │           (edge gateway, WS, bypass
  │            detection, alarms, dashboard)
  ▼
Phase 3 ─── Power Quality & Logging ────── Weeks 9–12
  │           (PQ ingestion, aggregates,
  │            trends, report worker)
  ▼
Phase 4 ─── Commissioning & Hardening ──── Weeks 13–14
              (live integration, security,
               load test, production deploy)

  ═══════════════ R1 SIGN-OFF ═══════════════

═══════════════════ R2 — Usage & Reporting (~4 weeks) ═════════════════════

Phase 5 ─── Reports, Burn Hours, Export ── Weeks 15–18
              (monthly reports, PDF/CSV/XLSX,
               counters, read replica)

  ═══════════════ R2 SIGN-OFF ═══════════════

═══════════════════ R3 — Visual Navigation (~4 weeks) ═════════════════════

Phase 6 ─── Canvas, SLD, Floor Plan ────── Weeks 19–22
              (SVG canvases, cross-nav,
               operator training, final docs)

  ═══════════════ R3 SIGN-OFF ═══════════════
```

**R1 estimate:** 14 weeks (hard deadline ~2026-07-18).
**R2 estimate:** ~4 weeks post-R1.
**R3 estimate:** ~4 weeks post-R2.
**Total:** ~22 weeks for all three releases.

---

## 13. Spec-Driven Change Management

### 13.1 When Arno changes SPEC.md

1. Edit SPEC.md.
2. Open Claude session: *"SPEC.md has been updated. Diff the changes and identify affected phases, skills, files, and tests. Generate a change plan."*
3. Claude produces a targeted change plan.
4. Arno approves.
5. Claude implements, runs all gates, presents output.

### 13.2 When Claude finds a gap

1. Insert `# TODO: VERIFY — [question]` in code.
2. Add to `design/SLD_FIELD_MAP.xlsx` → Gaps & Actions sheet.
3. Flag to Arno with specific question.
4. Arno resolves by updating SPEC.md.

### 13.3 Architectural Decision Records

All non-trivial choices in `/docs/adr/`. Claude drafts. Arno approves. Binding for all future sessions.

---

## 14. Summary

| What | Where | Who maintains it |
|---|---|---|
| Requirements | `SPEC.md` | Arno |
| Build strategy & skills | `BUILD_STRATEGY.md` | Claude (Arno approves changes) |
| Technology decisions | `TECHNOLOGY_ASSESSMENT.md` | Claude (Arno signs off) |
| Asset data (source of truth) | `design/sld_per_mb_extract.json` | Extracted from SLD drawings |
| Database schema | `DB_SCHEMA.md` + migrations | Claude (generated from SPEC) |
| All application code | `/api`, `/web`, `/edge` | Claude (generated, tested, reviewed) |
| All tests | `/api/tests`, `/web/tests`, `/web/e2e` | Claude (generated per phase) |
| CI/CD pipeline | `.github/workflows/` | Claude (Phase 0) |
| Deployment | Vercel (web) + Railway/VPS (API) | Claude configures, Arno manages credentials |
| Documentation | `/docs/` | Claude (Phase 8) |
| Quality gates | CI checks + code review | Automated + Claude `code-review` |
| Hallucination prevention | Verification protocol (§2) | Claude (mandatory every session) |

**48 skills. 8 phases. 22 weeks. One file to maintain.**
