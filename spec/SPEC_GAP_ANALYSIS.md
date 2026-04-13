# GAP ANALYSIS: Current Specification → Build-Ready Specification

**Analyst:** Claude Gap Analysis Agent
**Date:** 2026-04-11
**Context:** Kingswalk Mall SCADA Monitoring System — pre-build specification completeness audit
**Time Horizon:** Build start (target: within 2 weeks of Sprint 0 completion, ~2026-04-28)
**Purpose:** Determine whether the specification package is complete enough for a coding session to build R1 without needing to stop and ask questions that should have been answered in the spec.

---

## CURRENT STATE ASSESSMENT

*What exists today: 14 documents, 2 migrations, 1 JSON asset extract, 1 Excel workbook.*

| Dimension | Current State | Measurement | Confidence |
|-----------|--------------|-------------|------------|
| Auth & user lifecycle | 8-step lifecycle fully specified, JWT/MFA/RBAC detailed, password reset hardened, recovery codes specified, argon2id params set | MEASURED (counted spec sections) | HIGH |
| Database schema | 40+ tables across 5 schemas, 3 migrations (0001, 0001a, 0002), all columns/types/constraints documented, 2 schema audits passed | MEASURED | HIGH |
| Edge gateway polling | Async architecture, per-VLAN priority scheduler, local buffer, systemd, health endpoint, watchdog, idempotent writes — all specified | ASSESSED | HIGH |
| Modbus register addresses | Zero verified addresses. Spec mandates TODO markers on all register references. Awaiting Profection register map. | MEASURED (0 confirmed addresses) | HIGH |
| Frontend UI/UX | Stack chosen (React 19, Zustand, Tailwind 4, Radix UI), role-aware dashboards described, alarm UI detailed, PQ charts scoped | ASSESSED | MODERATE |
| Bypass detection | Logic described (compare breaker state vs relay command), highest-priority alarm specified, escalation defined | ASSESSED | MODERATE |
| Relay state source | NOT KNOWN. Assumption #3 in ASSUMPTION_MAP.md. Sprint 0 Action 1 pending response from Profection. | UNKNOWN | LOW |
| Notifications & alerting | 3-tier escalation, 4 channels, severity mapping, threshold schema with 6-band hysteresis | ASSESSED | HIGH |
| Reporting | Monthly auto-reports, on-demand, PDF/CSV/XLSX export, arq worker separation specified | ASSESSED | MODERATE |
| Deployment infrastructure | Cloud-hosted + edge gateway architecture, VPN with dual-path failover, TLS 1.3, PgBouncer pooling | ASSESSED | MODERATE |
| Security posture | 22-finding pre-build audit complete, all CRITICAL/HIGH findings resolved in spec. RLS enabled (policies pending). mTLS chosen. | MEASURED (22 findings catalogued) | HIGH |
| Testing strategy | pytest/Vitest/Playwright/k6, 80% coverage gate, 15-point code review checklist, CI pipeline defined | ASSESSED | MODERATE |
| Operations & monitoring | Structured logging, Prometheus + Grafana mentioned, edge watchdog, 99.9% uptime target | ASSESSED | LOW |
| Asset registry | 104 breakers, 9 main boards, JSON extract validated, Excel workbook with 8 sheets | MEASURED | HIGH |
| Domain-specific rules | Electrical units, realistic value ranges, hallucination checks, COMMS LOSS protocol, stale data warnings | ASSESSED | HIGH |
| Unresolved decisions | 5 "or" choices remain in SPEC.md (cloud provider, charting library, secrets manager, reverse proxy, edge hardware) | MEASURED (5 counted) | HIGH |

**Overall specification maturity: ~75% fully implementable, ~18% needs clarification, ~7% blocked by external dependencies.**

**Trend:** IMPROVING — 4 documents added in the last 48 hours (security audit, schema audit, build handoff, sprint 0 tracker). Each pass has closed gaps, not opened new ones.

---

## DESIRED STATE SPECIFICATION

*What "build-ready" means: a coding session can start Phase 1 and proceed through Phase 6 without needing to pause for specification decisions.*

| Dimension | Desired State | Source | Realism |
|-----------|--------------|--------|---------|
| Every "or" decision resolved | Zero unresolved alternatives in SPEC.md — every choice is made | Industry best practice for handoff docs | ACHIEVABLE |
| All RLS policies defined in SQL | Concrete `CREATE POLICY` statements for all 11 RLS-enabled tables | SECURITY_AUDIT F2 | ACHIEVABLE |
| Modbus register map available | Verified register addresses for all MP2/MP4 functions across ABB devices, OR explicit fallback plan with TODO protocol | SPRINT_0_TRACKER Action 2 | AMBITIOUS (depends on Profection) |
| Relay state source confirmed | Binary answer: can or cannot read relay command state via Modbus | SPRINT_0_TRACKER Action 1 | AMBITIOUS (depends on Profection) |
| Frontend component architecture documented | Component tree, state management boundaries, API contract per component | Build-ready standard | ACHIEVABLE |
| Notification templates defined | Email HTML, SMS text, toast UI, webhook payload for each alert type | Implementable spec standard | ACHIEVABLE |
| Report templates defined | Column definitions, filters, grouping logic for each of the 4 monthly report types | Implementable spec standard | ACHIEVABLE |
| "or" decisions finalized | Cloud provider, charting lib, secrets manager, reverse proxy, edge hardware — all chosen | Implementable spec standard | ACHIEVABLE |
| CI/CD pipeline configuration written | GitHub Actions YAML (or equivalent), not just described in prose | Build-ready standard | ACHIEVABLE |
| Operational runbooks drafted | At minimum: deployment, rollback, DB backup/restore, edge gateway restart, VPN failure | Production readiness | ACHIEVABLE (R1 scope can be lightweight) |
| Edge gateway hardware specified and ordered | Make/model, CPU/RAM/storage/NIC, procurement timeline | SPRINT_0_TRACKER Action 3 | ACHIEVABLE (Arno's action) |

**Desired state validation:** These criteria are derived from the BUILD_HANDOFF.md "Things That Will Bite You" list, the PRE_MORTEM_ANALYSIS top 5 failure modes, and the SECURITY_AUDIT remediation roadmap. They represent the minimum bar at which a coding session can proceed with confidence.

---

## GAP MEASUREMENT

| # | Dimension | Current | Desired | Gap | Magnitude | Confidence |
|---|-----------|---------|---------|-----|-----------|------------|
| G1 | Unresolved "or" decisions | 5 open choices | 0 | 5 decisions | MODERATE | HIGH |
| G2 | RLS policy SQL | 0 policies (11 tables enabled) | 11+ policies | 11 policies | LARGE | HIGH |
| G3 | Modbus register map | 0 verified addresses | ~48 addresses (MP2×8 + MP4×6 per device class) | 48 addresses | LARGE | HIGH |
| G4 | Relay state source | UNKNOWN | CONFIRMED yes/no | 1 binary answer | LARGE | HIGH |
| G5 | Frontend component architecture | Stack chosen, no component tree | Component tree + state boundaries | Full component architecture | MODERATE | MODERATE |
| G6 | Notification templates | Channels + escalation defined, no content | Email HTML + SMS text + webhook payload per alert type | ~8 templates | MODERATE | MODERATE |
| G7 | Report template definitions | Schema tables exist, no query/column specs | Column definitions + SQL per report type | 4 report specs | MODERATE | MODERATE |
| G8 | CI/CD pipeline YAML | Described in prose (SPEC A.4, BUILD_STRATEGY §4) | Working GitHub Actions workflow | 1 pipeline file | SMALL | HIGH |
| G9 | Operational runbooks | Zero exist | Minimum 5 runbooks | 5 runbooks | MODERATE | MODERATE |
| G10 | Edge hardware spec | "Any Linux box" | Make/model/procurement plan | 1 hardware spec | MODERATE | HIGH |
| G11 | Docker/local dev config | Zero config files | docker-compose.yml + .env.example | 2 config files | SMALL | HIGH |
| G12 | Harmonics data format | "jsonb" column, format unspecified | Concrete JSON schema for harmonics field | 1 schema definition | SMALL | MODERATE |
| G13 | Tenant-scoped data access | No permission model for viewer-tenants | RBAC rule: "viewers see only their tenant feed" or "viewers see everything" | 1 policy decision | SMALL | MODERATE |
| G14 | WebSocket message throttling | "Throttled appropriately" (no number) | Max messages/second defined | 1 threshold | SMALL | MODERATE |
| G15 | PDF rendering library | Not chosen | Library selected | 1 decision | SMALL | HIGH |

**Largest gaps:** G2 (RLS policies), G3 (register map), G4 (relay state), G5 (frontend architecture)
**No-gap dimensions:** Auth lifecycle, database schema structure, security spec, asset registry, build/deploy architecture

---

## GAP PRIORITIZATION

| Gap | Impact (1-5) | Feasibility (1-5) | Score | Tier | Urgency | Dependencies |
|-----|-------------|-------------------|-------|------|---------|-------------|
| G4 — Relay state source | 5 | 2 | 10 | HIGH | CRITICAL | Blocks bypass detection (core business case) |
| G3 — Modbus register map | 5 | 2 | 10 | HIGH | HIGH | Blocks edge gateway real-device integration |
| G2 — RLS policies | 5 | 4 | 20 | CRITICAL | HIGH | Blocks Phase 1 auth completion |
| G1 — "or" decisions | 4 | 5 | 20 | CRITICAL | HIGH | Blocks Phase 1 infrastructure setup |
| G5 — Frontend architecture | 4 | 4 | 16 | CRITICAL | MEDIUM | Blocks Phase 3 dashboard build |
| G10 — Edge hardware | 4 | 4 | 16 | CRITICAL | HIGH | Blocks Phase 2 edge gateway testing |
| G8 — CI/CD YAML | 4 | 5 | 20 | CRITICAL | HIGH | Blocks quality gates from day 1 |
| G6 — Notification templates | 3 | 4 | 12 | HIGH | LOW | Blocks Phase 4 alerting |
| G7 — Report templates | 3 | 4 | 12 | HIGH | LOW | Blocks Phase 6 reporting |
| G9 — Operational runbooks | 3 | 3 | 9 | HIGH | LOW | Blocks production readiness |
| G11 — Docker config | 3 | 5 | 15 | CRITICAL | MEDIUM | Blocks local development setup |
| G12 — Harmonics format | 2 | 5 | 10 | HIGH | LOW | Blocks PQ display implementation |
| G13 — Tenant access scope | 3 | 5 | 15 | CRITICAL | MEDIUM | Blocks viewer role implementation |
| G14 — WS throttling | 2 | 5 | 10 | HIGH | LOW | Blocks WebSocket broadcast implementation |
| G15 — PDF library | 2 | 5 | 10 | HIGH | LOW | Blocks Phase 6 reports |

**Priority sequence:**
1. **G1 — "or" decisions** (CRITICAL, score 20) — close first because every other gap depends on knowing the platform
2. **G2 — RLS policies** (CRITICAL, score 20) — close during Phase 1 auth build, required for security
3. **G8 — CI/CD YAML** (CRITICAL, score 20) — close in Phase 1 Week 1, quality gates from day one
4. **G4 — Relay state source** (HIGH, score 10) — external dependency, cannot control timeline, but MUST be answered before Phase 2 bypass detection build
5. **G3 — Modbus register map** (HIGH, score 10) — external dependency, build against simulator with fallback plan
6. **G5, G10, G11, G13** — close before their respective build phases begin

---

## ROOT CAUSE ANALYSIS

### G1: Five "or" Decisions Remain in SPEC.md

**Gap:** 5 unresolved choices (cloud provider, charting library, secrets manager, reverse proxy, edge hardware)

**5 Whys:**
1. These choices aren't made → because they felt like implementation details during spec writing
2. They felt like implementation details → because none has been benchmarked against the actual deployment constraints
3. No benchmarking → because no code exists yet and the choices seemed deferrable
4. Seemed deferrable → because each choice is individually small, but collectively they block Phase 1 infrastructure setup
5. **Root cause:** Decision fatigue during spec writing — the easy path was to list options instead of choosing

**Category:** Process deficit — no decision gate requiring all "or" statements to be resolved before handoff
**Closure implication:** These are 5-minute decisions for someone with the context. Arno can resolve them all in a single pass.

---

### G2: RLS Policies Not Written

**Gap:** 11 tables have `ENABLE ROW LEVEL SECURITY` but 0 `CREATE POLICY` statements

**5 Whys:**
1. No policies exist → because the migration was built schema-first, security-second
2. Schema-first approach → because the schema audit focused on structural correctness, not access control implementation
3. Access control deferred → because "the application authenticates via JWT and sets session variables" — which requires application code that doesn't exist yet
4. Can't write policies without the app → **FALSE** — policies can be written against `current_setting('app.current_user_id')` right now
5. **Root cause:** Circular dependency perception — "can't write policies without middleware, can't test middleware without policies" — but the policies can absolutely be written in advance

**Category:** Process deficit — the schema review cycle didn't include an RLS policy gate
**Closure implication:** Write the policies NOW in a new migration (0001b). They're deterministic given the role model (admin/operator/viewer) and table purposes.

---

### G4: Relay State Source Unknown

**Gap:** The core business case (bypass detection) depends on comparing breaker state vs relay command state. The relay command state source is unknown.

**5 Whys:**
1. Source unknown → because Profection hasn't confirmed whether the 48V relay controller exposes state via Modbus
2. Profection hasn't confirmed → because the question was only formally asked in WM-KW-SCADA-REQ-001 (bench test request)
3. Bench test request recently sent → because the relay question only became clear after the assumption mapping exercise
4. Assumption mapping done late → because the spec was being built iteratively and the bypass detection was initially described at a conceptual level
5. **Root cause:** The most critical assumption in the project was identified late in the spec phase and is now gated on an external party's response

**Category:** External constraint — cannot be resolved internally
**Closure implication:** Cannot close this gap through spec work. Must wait for Profection's answer. Spec must document the fallback architecture (hardcoded schedule, time-based rule instead of state comparison) so the build session can proceed either way.

---

### G5: Frontend Component Architecture Not Documented

**Gap:** Stack is chosen, role-based views are described narratively, but no component tree, state management boundaries, or API contract per component exists.

**5 Whys:**
1. No component architecture → because the spec focused on what to display, not how to structure the React code
2. Focused on "what" → because the spec was written for a domain audience (Arno), not a frontend developer
3. Written for domain audience → because BUILD_STRATEGY delegates component structure to the coding session
4. Delegated to coding session → because React component architecture is considered an implementation detail
5. **Root cause:** Component architecture IS an implementation detail — but for a 14-week build with AI coding, documenting the expected component tree and state boundaries reduces ambiguity and prevents rework

**Category:** Information deficit — the information needed exists conceptually but hasn't been documented
**Closure implication:** This gap can be closed by the coding session itself during Phase 1 (scaffold). It's not a spec gap per se, but a handoff gap — the build session would benefit from a component tree diagram in BUILD_HANDOFF.md. Low risk of blocking; medium risk of rework.

---

## GAP CLOSURE STRATEGIES

### G1: Resolve "or" Decisions — CRITICAL PRIORITY

**Root cause:** Decision fatigue during spec writing
**Strategy:** DECIDE (5-minute decisions by Arno)
**Actions:**

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Cloud provider | **Railway** | Simplest for Docker deployment; South Africa latency via Cloudflare; lowest DevOps burden. Migrate to AWS af-south-1 if latency exceeds 50ms. |
| Charting library | **Recharts** | React-native, simpler API, sufficient for PQ trend charts. ECharts is overkill for R1. |
| Secrets manager | **Doppler** | Free tier covers this project. Works with Railway. No AWS dependency. |
| Reverse proxy | **Caddy** | Automatic HTTPS/TLS, simpler config than nginx, sufficient for this traffic volume. |
| Edge hardware | **Advantech UNO-2271G** or equivalent industrial mini-PC | Fanless, DIN-rail, Ubuntu support, dual NIC (SCADA VLAN + management). Budget: R15K–R25K. |

**Resource:** 15 minutes of Arno's time. Zero budget.
**Success criteria:** Zero "or" statements remain in SPEC.md.
**Recurrence prevention:** Add a "no unresolved alternatives" check to the spec review checklist.

---

### G2: Write RLS Policies — CRITICAL PRIORITY

**Root cause:** Circular dependency perception
**Strategy:** BUILD (write SQL policies now in a new migration)
**Actions:**
1. Create `db/migrations/0001b_rls_policies.sql` with concrete policies for all 11 tables
2. Pattern: `current_setting('app.current_user_id', true)` for user-scoped access, `current_setting('app.current_user_role', true)` for role checks
3. Policy design per table:

| Table | SELECT | INSERT | UPDATE | DELETE |
|-------|--------|--------|--------|--------|
| core.users | Self or admin | Admin only | Self (name) or admin (role, active) | Never |
| core.session | Self or admin | App role (on login) | App role (on refresh) | App role (on logout) |
| core.invite | Admin only | Admin only | App role (on accept) | Never |
| core.password_reset | App role (matching user) | App role | Never | Never |
| core.recovery_code | App role (matching user) | App role | App role (mark used) | Never |
| core.audit_log | Admin only | App role (INSERT only) | Never | Never |
| events.event | All authenticated | App role | Operator+ (acknowledge) | Never |
| telemetry.* (4 tables) | All authenticated | scada_writer role only | Never | Never |

**Resource:** 2 hours Claude time. Zero budget.
**Success criteria:** All 11 tables have at least one policy per operation they support. Migration parses with pglast.
**Recurrence prevention:** Add "RLS policy required for every new table with RLS enabled" to SCHEMA_REVIEW checklist.

---

### G4: Relay State Source — HIGH PRIORITY (External)

**Root cause:** External dependency on Profection
**Strategy:** ACCEPT + REDESIGN (document fallback architecture)
**Actions:**
1. **Wait for answer** — Sprint 0 Action 1 (Arno → Profection, due 2026-04-18)
2. **Document fallback in SPEC.md now** — if relay state is NOT readable:
   - Fallback A: Time-based rule — during load-shedding window (mains failure detected via incomer PQ), any tenant breaker in "closed" state that should be open per the load-shedding schedule triggers the bypass alarm.
   - Fallback B: Current-based inference — if a breaker marked "non-essential" is drawing current during a mains failure event, infer bypass.
3. **Build the comparison interface abstractly** — the bypass detection module takes a `RelayStateProvider` interface that can be swapped between `ModbusRelayStateProvider`, `ScheduleBasedRelayStateProvider`, or `CurrentBasedRelayStateProvider`.

**Resource:** Already tracked in SPRINT_0_TRACKER. No additional spec work needed beyond documenting fallbacks.
**Success criteria:** Profection confirms yes/no, OR fallback architecture is documented and the build proceeds with the pluggable interface.

---

### G8: CI/CD Pipeline YAML — CRITICAL PRIORITY

**Root cause:** Spec describes the pipeline in prose but doesn't provide the file
**Strategy:** BUILD (generate during Phase 1 Week 1)
**Actions:**
1. Generate `.github/workflows/ci.yml` during Phase 1 scaffold
2. Stages: lint (ruff + eslint) → type-check (mypy + tsc) → test (pytest + vitest) → security (pip-audit + npm audit) → build (vite) → deploy (Vercel preview)
3. This is a coding session task, not a spec task — the spec already defines the gates

**Resource:** 1 hour of build time. Zero budget.
**Success criteria:** CI pipeline runs green on first real PR.

---

### G13: Tenant-Scoped Data Access — CRITICAL PRIORITY

**Root cause:** Information deficit — the SPEC doesn't state whether viewers see all data or only their tenant's data
**Strategy:** DECIDE (Arno must answer one question)
**Question:** Do Viewer-role users (the 20 tenants) see the entire building's data, or only the breakers and feeds associated with their tenancy?

**Options:**
- **Option A — Full visibility:** All viewers see all data. Simpler. Appropriate if tenants use this for general awareness.
- **Option B — Tenant-scoped:** Viewers only see their own feeds. Requires `tenant_feed.viewer_user_id` FK and additional RLS policies. More complex but more appropriate if data is commercially sensitive.

**Resource:** 1-minute decision by Arno. RLS policy implications handled in G2.
**Recurrence prevention:** Document the decision in SPEC.md §C.1 under Viewer role capabilities.

---

## GAP CLOSURE ROADMAP

### Phase 0: Before Build Starts (0–14 days)

- [ ] **G1** — Resolve 5 "or" decisions — Owner: Arno — By: 2026-04-14 — 15 min
- [ ] **G13** — Decide tenant-scoped access — Owner: Arno — By: 2026-04-14 — 1 min
- [ ] **G2** — Write RLS policies (migration 0001b) — Owner: Claude — By: 2026-04-14 — 2 hrs
- [ ] **G12** — Define harmonics JSON schema — Owner: Claude — By: 2026-04-14 — 15 min
- [ ] **G14** — Set WebSocket throttle threshold — Owner: Claude — By: 2026-04-14 — 5 min
- [ ] **G15** — Choose PDF library — Owner: Claude — By: 2026-04-14 — 5 min
- [ ] **G4** — Follow up with Profection on relay state — Owner: Arno — By: 2026-04-18 (SPRINT_0 Action 1)
- [ ] **G10** — Specify and order edge gateway hardware — Owner: Arno — By: 2026-04-18 (SPRINT_0 Action 3)

### Phase 1: Foundation (Weeks 1–3 of build)

- [ ] **G8** — Generate CI/CD pipeline YAML — Owner: Claude — By: Week 1 Day 1
- [ ] **G11** — Generate docker-compose.yml + .env.example — Owner: Claude — By: Week 1 Day 1
- [ ] **G5** — Document React component tree during scaffold — Owner: Claude — By: Week 1 Day 3

### Phase 2: Edge Gateway (Weeks 4–8)

- [ ] **G3** — Integrate Profection register map (if received) or build against simulator with TODO markers — Owner: Claude — By: Week 4
- [ ] **G4** — Implement bypass detection with chosen relay state strategy — Owner: Claude — By: Week 6

### Phase 4–6: Notifications & Reports (Weeks 10–16)

- [ ] **G6** — Design notification templates during alerting build — Owner: Claude — By: Week 10
- [ ] **G7** — Define report templates during reporting build — Owner: Claude — By: Week 14
- [ ] **G9** — Draft operational runbooks during hardening — Owner: Claude — By: Week 16

---

## RESOURCE SUMMARY

| Gap | Budget | Time | Owner | Priority |
|-----|--------|------|-------|----------|
| G1 — "or" decisions | R0 | 15 min | Arno | CRITICAL |
| G2 — RLS policies | R0 | 2 hrs (Claude) | Claude | CRITICAL |
| G3 — Register map | R0 (awaiting Profection) | External | Arno/Profection | HIGH |
| G4 — Relay state | R0 (awaiting Profection) | External | Arno/Profection | HIGH |
| G5 — Frontend arch | R0 | 2 hrs (Claude, Phase 1) | Claude | CRITICAL |
| G8 — CI/CD YAML | R0 | 1 hr (Claude, Phase 1) | Claude | CRITICAL |
| G10 — Edge hardware | R15K–R25K | 2 weeks procurement | Arno | CRITICAL |
| G13 — Tenant access | R0 | 1 min decision | Arno | CRITICAL |
| G6, G7, G9, G11, G12, G14, G15 | R0 | ~6 hrs total (Claude, spread across build) | Claude | HIGH–LOW |
| **Total** | **R15K–R25K** (hardware) | **Arno: ~30 min decisions + Sprint 0 actions** | | |

---

## PROGRESS MEASUREMENT

| Gap | Leading Indicator | Lagging Indicator | Review | Alert Threshold |
|-----|------------------|-------------------|--------|----------------|
| G1 | "or" count in SPEC.md | Zero "or" decisions remain | Once | If any "or" exists at build start, STOP |
| G2 | Policy count per table | All 11 tables have policies, migration parses | Once | If not done by Phase 1 Day 1, auth build is blocked |
| G4 | Profection response received | Bypass detection architecture chosen | Weekly | If no answer by 2026-04-25, activate fallback plan |
| G3 | Register addresses in config file | Edge gateway polls real devices | Weekly | If no map by Week 4, build against simulator |
| G10 | Purchase order placed | Hardware on site | Weekly | If not ordered by 2026-04-21, Phase 2 is at risk |

---

## GAPS ACCEPTED (NOT CLOSING IN SPEC PHASE)

| Gap | Priority | Reason Accepted | Risk Management |
|-----|---------|-----------------|----------------|
| G3 — Register map (partial) | HIGH | External dependency on Profection — cannot force timeline | Build against simulator with TODO protocol; budget 2 weeks integration rework |
| G5 — Component architecture | CRITICAL | Implementation detail best decided during scaffold, not in spec | BUILD_HANDOFF §9 workflow guides the coding session; low risk of fundamental error |
| G6 — Notification templates | HIGH | Content design is more effective during implementation when the UI context exists | Channel + escalation logic is fully specified; templates are styling, not architecture |
| G7 — Report templates | HIGH | Same — report content best designed when the data pipeline exists | Schema and worker architecture are specified; templates are content, not structure |
| G9 — Operational runbooks | HIGH | Cannot write meaningful runbooks before the system exists | Architecture review identifies the runbook topics; content comes during hardening |

---

## SUMMARY ASSESSMENT

**Verdict: The spec is build-ready for Phase 1, with 4 actions required from Arno before the build clock starts.**

The specification package is unusually mature for a pre-build handoff. The database schema has survived two independent audits. The security posture has been hardened through a full OWASP review. The architecture has been reviewed across 3 tiers. The pre-mortem identified 20 failure modes with mitigations. The assumption map catalogues 30 assumptions with fallback plans.

The remaining gaps fall into three categories:

1. **Quick decisions (G1, G13):** 5 "or" choices and 1 policy question that Arno can resolve in 15 minutes. These are the only spec gaps that are both closable today and blocking.

2. **Build-time tasks (G2, G5, G8, G11):** RLS policies, component architecture, CI/CD pipeline, Docker config. These are buildable artifacts that are better created during Phase 1 scaffold than in the spec document. They are "gaps" in the spec but "tasks" in the build plan.

3. **External dependencies (G3, G4, G10):** Register map, relay state answer, edge hardware. These are tracked in SPRINT_0_TRACKER.md with owners, deadlines, and fallback plans. The spec cannot close them — only Profection and procurement can.

**Recommendation:** Close G1 and G13 (Arno's quick decisions), then start the build. Everything else is either a build-time task or an external dependency with a documented fallback.

---

**END OF GAP ANALYSIS**
