# TECHNOLOGY ASSESSMENT: Frontend Framework for Kingswalk SCADA GUI

**Analyst:** Watson Mattheus Consulting — independent assessment
**Date:** 2026-04-10
**Technology under evaluation:** React 19 (Vite + TypeScript SPA)
**Alternatives assessed:** Angular 19, Vue 3, Svelte 5, Inductive Automation Ignition (commercial SCADA platform)
**Use context:** Web-based SCADA GUI for a 104-breaker / 9-main-board shopping mall electrical installation in Savannah, South Africa. Accessed from fixed operator workstations and facility manager laptops over intranet/VPN. Backend: FastAPI + PostgreSQL/TimescaleDB + Modbus TCP edge gateway.
**Decision required:** Adopt / Do Not Adopt / Pilot / Defer
**Assessor posture:** Independent — no vendor affiliation

---

## EXECUTIVE RECOMMENDATION

**Recommendation:** ADOPT React 19 (Vite + TypeScript) — with one architectural condition
**Confidence:** HIGH
**One-sentence rationale:** React delivers the best combination of real-time WebSocket performance, interactive SVG floor-plan capability, South African developer availability, and long-term ecosystem depth for a web-first industrial control system — provided the frontend is built behind a clean API abstraction layer so a framework migration remains feasible if React's architectural churn becomes untenable.

The condition matters: React has undergone three major paradigm shifts in seven years (class → hooks → server components → compiler). While each shift improved the framework, the pattern means your codebase will need periodic refactoring to stay on the supported path. The mitigation is architectural: keep all business logic, WebSocket management, and data transformation in framework-agnostic TypeScript modules. Only the view layer should touch React APIs. This gives you a 60–70% code reuse path to Vue or Svelte if you ever need to migrate.

---

## TECHNOLOGY READINESS LEVEL

| Framework | TRL | Production evidence |
|---|---|---|
| **React 19** | **9** | 10M+ production deployments worldwide. Meta, Airbnb, Netflix, Shopify. React Foundation under Linux Foundation (Feb 2026). Stable compiler since Oct 2025. |
| Angular 19 | 9 | Google, Microsoft, Deutsche Bank. Angular 19 LTS through May 2026, v20 imminent. 10-year track record in enterprise. |
| Vue 3 | 8–9 | Alibaba, GitLab, BMW. State of Vue 2025 shows 93% developer satisfaction. Pinia at 80% adoption. Vapor Mode (performance) planned 2026. |
| Svelte 5 | 7–8 | Apple (partial), Spotify embeds, smaller-scale production. Runes migration (Svelte 5) still settling. Smaller community. |
| Ignition | 9 | 4,000+ SCADA installations globally. Dominant in North American industrial. Java-based, Perspective module for web. |

**Maturity trajectory:** React is mature and accelerating (compiler, Foundation). Angular is mature but slowing. Vue is mature and stable. Svelte is maturing rapidly but ecosystem is 3–5× smaller. Ignition is mature but niche to industrial.

---

## CAPABILITY ASSESSMENT

### Fit to Requirements

| Requirement (from SPEC.md) | React 19 | Angular 19 | Vue 3 | Svelte 5 | Ignition |
|---|---|---|---|---|---|
| WebSocket real-time (<1s) | EXCEEDS — native API, concurrent rendering | MEETS — RxJS observable streams | MEETS — composable reactive | MEETS — native reactivity | MEETS — built-in tag binding |
| SVG floor-plan (100+ interactive hotspots) | EXCEEDS — DOM-native SVG, d3-zoom | MEETS — DOM SVG, less ecosystem for d3 | MEETS — good SVG support | MEETS — good SVG support | PARTIAL — Perspective uses canvas, not DOM SVG |
| RBAC + audit trail | MEETS | MEETS — Angular Guards native | MEETS | MEETS | EXCEEDS — built-in user/role system |
| PDF/CSV reporting | N/A (server-side) | N/A | N/A | N/A | EXCEEDS — built-in reporting engine |
| Responsive design / WCAG 2.1 AA | MEETS — Radix/HeadlessUI | MEETS — Angular CDK a11y | MEETS — fewer a11y libs | PARTIAL — smaller ecosystem | PARTIAL — limited theming |
| TimescaleDB charting (PQ trends) | EXCEEDS — Recharts, ECharts, Victory | MEETS — ngx-charts, ECharts | MEETS — vue-echarts | MEETS — LayerChart | MEETS — built-in trending |
| Modular / extensible for new asset types | MEETS | EXCEEDS — opinionated module system | MEETS | MEETS | MEETS — tag-based, config-driven |
| Deployment (intranet, zero client install) | EXCEEDS — static SPA, nginx | EXCEEDS — same | EXCEEDS — same | EXCEEDS — same | PARTIAL — requires Java gateway server |

**Overall requirements fit:**

| Framework | Fit |
|---|---|
| React 19 | **STRONG** |
| Angular 19 | STRONG |
| Vue 3 | ADEQUATE–STRONG |
| Svelte 5 | ADEQUATE |
| Ignition | ADEQUATE (over-engineered for scope, under-delivers on custom SVG) |

---

## LIMITATIONS — THE HONEST PART

### React 19

**Architectural churn (the real risk):**
React has shifted its core programming model three times since 2019. Each shift made the framework better, but also deprecates patterns from the prior era. A codebase written in "React 18 hooks style" today will feel dated by 2029. You will need to budget engineering time for periodic modernisation, or accept running on older patterns with community support gradually thinning.

- Class components → Hooks (2019): migration effort was moderate
- Client-only → Server Components (2023): fundamental re-architecture; irrelevant for a SPA but creates ecosystem confusion
- Manual memo → React Compiler (2025): opt-in today, likely expected by 2028

**Mitigation:** Keep React as a thin view layer. All business logic, WebSocket management, data models, and API clients should live in framework-agnostic TypeScript modules. This limits the "React surface area" to ~30% of the codebase, making paradigm shifts manageable.

**Decision fatigue:**
React is unopinionated — you choose your own router, state manager, form library, CSS approach. This is powerful for experienced teams but creates decision overhead and inconsistency risk if multiple developers make different choices.

**Mitigation:** Lock the stack in the spec (React Router 7, Zustand, Tailwind, Radix, React Hook Form + Zod). No deviations without ADR approval.

### Angular 19

**Bundle size and complexity:**
Angular ships a larger runtime (~130KB gzipped vs React's ~45KB). For an intranet app this is tolerable, but the framework's opinionated structure (modules, decorators, dependency injection, RxJS) creates a steeper learning curve and slower onboarding for new developers.

**RxJS coupling:**
Angular's real-time story relies on RxJS observables. RxJS is powerful but notoriously difficult to debug, and observable chains with WebSocket can create subtle memory leak patterns that are hard to diagnose in production.

**Migration path:**
Angular's decorators and DI system make components less portable. Moving from Angular to another framework is harder than moving from React or Vue.

### Vue 3

**Smaller SA developer pool:**
Vue is the third-most-popular framework globally but has a noticeably smaller hiring pool in South Africa compared to React. OfferZen data shows React roles outnumber Vue roles ~4:1 in SA job listings.

**Enterprise perception:**
Vue lacks a major corporate backer (Evan You is the BDFL, supported by sponsors). Some enterprise clients and procurement teams are uncomfortable with this governance model, even though the framework is technically excellent.

**Industrial SCADA precedent:**
Fewer documented SCADA/industrial HMI deployments use Vue compared to React or Angular. This isn't a technical limitation but means fewer reference architectures to draw from.

### Svelte 5

**Ecosystem depth:**
Svelte's component library, charting, and accessibility ecosystem is 3–5× smaller than React's. For standard CRUD this doesn't matter, but for a SCADA floor plan with custom SVG interactions, charting, and complex forms, you'll be building more from scratch.

**Runes migration:**
Svelte 5 introduced "Runes" — a new reactivity model. The ecosystem is mid-migration (April 2026), with some libraries still on Svelte 4 patterns. Adopting now means navigating this transition.

**Hiring:**
Svelte developers in South Africa are rare. You'd likely be training React/Vue developers to use Svelte, adding onboarding time.

### Ignition (Inductive Automation)

**Cost:**
Ignition licensing is USD-denominated. A single gateway license starts at ~$4,950/module. For a full SCADA deployment (Perspective + Alarm Notification + Reporting + Tag Historian) you're looking at $15,000–$25,000 upfront plus annual support. At current ZAR/USD (~R18.50), that's R280K–R460K before implementation.

**Custom UI limitations:**
Ignition Perspective uses a canvas-based renderer, not DOM SVG. Building a highly custom interactive floor plan with per-element hover states, CSS transitions, and accessible tooltips is significantly harder than in a browser-native SPA.

**Vendor lock-in:**
Ignition uses a proprietary tag model, scripting language (Jython), and project structure. Migrating away from Ignition means rebuilding from scratch.

**Over-scoped:**
Ignition is designed for 10,000+ tag industrial plants — refineries, water treatment, manufacturing. For a 104-breaker shopping mall electrical installation, it's architectural overkill with licensing cost that doesn't scale down.

---

## SOUTH AFRICAN CONTEXT

### Developer availability (SA market)

| Framework | SA job listings (relative) | Typical contractor rate (R/day) | Hiring difficulty |
|---|---|---|---|
| React | 100% (baseline) | R4,300 – R10,000 | Low — largest pool |
| Angular | ~60% | R4,500 – R10,500 | Moderate |
| Vue | ~25% | R4,500 – R10,000 | Higher — smaller pool |
| Svelte | ~5% | R5,000+ (specialist) | High — very scarce |
| Ignition | ~2% (SCADA integrators) | R6,000–R12,000 (specialist) | High — niche |

Source: OfferZen salary surveys 2025–2026, Arc.dev freelance rates.

### Load-shedding resilience

The SCADA backend and edge gateway must be on UPS/generator regardless of the frontend choice — they talk Modbus TCP to live switchgear. The frontend framework choice doesn't affect load-shedding resilience; that's an infrastructure concern (server hosting, network uptime). All five options serve over the same HTTPS/WSS connection.

**Recommendation:** Host the FastAPI backend and PostgreSQL on a cloud VPS with SA presence (AWS af-south-1 Cape Town, Azure South Africa North, or Hetzner SA) to decouple from site power. The React SPA is a static bundle served from the same host.

### POPIA compliance

No personal information is processed in the SCADA frontend — it monitors electrical switchgear, not people. User credentials (email, name, role) are stored in PostgreSQL on SA-hosted infrastructure. POPIA applies to the user management module but is identical across all framework choices.

### ZAR cost exposure

| Item | React/Angular/Vue/Svelte | Ignition |
|---|---|---|
| Framework license | R0 (open source) | R280K–R460K (USD-denominated) |
| Hosting (cloud VPS) | ~R2,500/month | ~R4,000/month (Java gateway needs more RAM) |
| Currency risk | None on framework | High — annual support fees in USD |

---

## TOTAL COST OF OWNERSHIP (5-year horizon)

Estimates assume a solo or 2-person development team, cloud-hosted, with periodic contractor support for major features.

| Cost category | React | Angular | Vue | Svelte | Ignition |
|---|---|---|---|---|---|
| **License (5yr)** | R0 | R0 | R0 | R0 | R460K + R90K support |
| **Implementation (Y1)** | R180K | R210K | R190K | R220K | R350K (integrator) |
| **Infrastructure (5yr)** | R150K | R150K | R150K | R150K | R240K |
| **Training** | R15K | R30K | R20K | R40K | R60K |
| **Maintenance (5yr)** | R200K | R200K | R200K | R250K | R150K |
| **Framework migration risk** | R50K reserve | R80K reserve | R40K reserve | R60K reserve | R300K (full rewrite) |
| **5-year total** | **R595K** | **R670K** | **R600K** | **R720K** | **R1,650K** |

**Key TCO uncertainties:** React's architectural churn could push maintenance higher if a major paradigm shift forces a rewrite of the view layer (~R80K–R120K). Ignition's USD pricing could worsen with ZAR depreciation. Svelte's smaller ecosystem could increase implementation time.

---

## ALTERNATIVE COMPARISON MATRIX

| Dimension | React 19 | Angular 19 | Vue 3 | Svelte 5 | Ignition |
|---|---|---|---|---|---|
| TRL | 9 | 9 | 8–9 | 7–8 | 9 |
| Requirements fit | STRONG | STRONG | ADEQUATE+ | ADEQUATE | ADEQUATE |
| 5-year TCO | R595K | R670K | R600K | R720K | R1,650K |
| Lock-in risk | LOW | MODERATE | LOW | LOW | HIGH |
| SA skill availability | HIGH | MODERATE | LOW–MOD | LOW | VERY LOW |
| Ecosystem depth | DEEP | DEEP | GOOD | THIN | DEEP (SCADA) |
| API churn risk | MODERATE | LOW | LOW | MODERATE | LOW |
| Custom SVG capability | EXCELLENT | GOOD | GOOD | GOOD | POOR |
| WebSocket performance | EXCELLENT | GOOD | GOOD | GOOD | GOOD |
| **Overall** | **BEST** | **STRONG** | **GOOD** | **VIABLE** | **WRONG FIT** |

### Why not Angular?

Angular is the closest alternative and would work well. The reason React edges it out for Kingswalk specifically: Angular's RxJS-based WebSocket handling is more complex to debug in a real-time SCADA context, the bundle is heavier (matters less on intranet but still), and the SA hiring pool is smaller. If your team already had Angular expertise, this would flip.

### Why not Vue?

Vue 3 is technically excellent and has the lowest API churn risk of any option (Evan You has been remarkably disciplined about backwards compatibility). The limiting factor is SA developer availability (~25% of React's pool) and fewer industrial HMI reference architectures. If you could guarantee long-term access to a Vue-proficient developer, Vue would be a strong choice.

### Why not Ignition?

Ignition solves a different problem (large-scale industrial plant SCADA with thousands of tags, OPC-UA, alarm management built in). For a 104-breaker shopping mall with a custom floor plan, it's the wrong tool: expensive, locked-in, and weak at custom interactive SVG. The R1.65M 5-year cost and USD exposure alone disqualify it for this scope.

---

## VENDOR LOCK-IN AND EXIT STRATEGY

### React lock-in assessment

| Dimension | Risk | Notes |
|---|---|---|
| Data | NONE | All data in PostgreSQL/TimescaleDB — framework-independent |
| API | NONE | FastAPI REST/WebSocket — framework-independent |
| View layer | MODERATE | JSX components are React-specific |
| Skills | LOW | React/TypeScript skills transfer to Vue, Svelte, or Angular |
| Contract | NONE | Open source, MIT license |

### Exit strategy

**If React becomes untenable (major breaking change, Meta abandons it, or ecosystem fragments):**

1. The backend (FastAPI + PG + TimescaleDB + Modbus gateway) is completely unaffected — zero changes needed.
2. The framework-agnostic TypeScript layer (WebSocket manager, data models, API client, business logic) ports directly — this is ~60–70% of the frontend codebase.
3. Only the React-specific view layer (~30–40% of frontend code) needs rewriting in Vue/Svelte/Angular.
4. Estimated migration effort: 4–8 weeks for a competent developer.

**Lock-in mitigation (build this from day one):**
- `/src/core/` — framework-agnostic TypeScript: WebSocket manager, Zustand stores (Zustand is framework-agnostic despite React origins), API client, data models, business rules.
- `/src/ui/` — React-specific: components, hooks, routing. This is the only replaceable layer.
- All SVG floor-plan geometry and asset positioning data stored in the database, not hardcoded in React components.

---

## PILOT RECOMMENDATION

**Pilot recommended:** YES — but scoped tightly.

**Pilot scope:** Build one vertical slice of the SCADA GUI before committing to full implementation:
1. Connect to one Main Board (MB 1.1, drawing 643.E.301, 10 outgoings) via Modbus TCP simulator
2. Display live breaker state via WebSocket on a floor-plan SVG fragment
3. Show one PQ trend chart (voltage over 24 hours) from TimescaleDB
4. Implement login + RBAC (Operator can toggle a simulated breaker, Viewer cannot)

**Duration:** 3 weeks

**Success criteria:**
- WebSocket state updates render in browser within 500ms of Modbus poll
- SVG floor plan handles 10 simultaneous state changes without frame drops
- RBAC correctly blocks Viewer from breaker control
- One developer can understand and modify the codebase within 2 hours of onboarding

**Failure criteria:**
- WebSocket latency consistently exceeds 1s under normal load
- SVG rendering cannot handle the interactive overlay without custom canvas fallback
- A replacement developer cannot onboard within a reasonable timeframe

**Pilot budget:** ~R25K (3 weeks of developer time + cloud hosting)

**What happens if the pilot fails:** Rerun the same pilot in Vue 3. The backend and data layer are identical — only the view layer changes.

---

## IMPLEMENTATION RISKS

| Risk | Likelihood (1–5) | Impact (1–5) | Mitigation |
|---|---|---|---|
| React major paradigm shift within 3 years | 3 | 3 | Framework-agnostic core architecture; view layer is replaceable |
| Key developer leaves; replacement unfamiliar with codebase | 3 | 4 | Thorough documentation, ADRs, locked stack decisions, React's large hiring pool |
| WebSocket reconnection failures on unstable site network | 3 | 4 | Exponential backoff with jitter; visual "disconnected" banner; queued state reconciliation on reconnect |
| SVG floor plan performance degrades as asset count grows | 2 | 3 | Virtualise off-screen elements; LOD switching at zoom levels; benchmark at 2× current asset count |
| Zustand or Radix UI library abandoned | 2 | 2 | Both have large communities; Zustand is tiny (~1KB) and replaceable; Radix is headless and portable |
| Load-shedding takes down site network to SCADA server | 3 | 5 | Cloud-hosted backend with SA presence; site UPS for edge gateway and managed switches |
| ZAR depreciation increases cloud hosting costs | 3 | 2 | Costs are small (~R2,500/month); budget 20% annual increase |

---

## DECISION SUMMARY

**Adopt React 19 (Vite + TypeScript) if:**
- You build the framework-agnostic core architecture from day one (non-negotiable)
- You lock the supporting stack in the spec (no ad-hoc library choices)
- You run the 3-week pilot on MB 1.1 before committing to full build

**Consider Vue 3 instead if:**
- You have long-term access to a Vue-proficient developer
- You prioritise API stability over ecosystem depth

**Do not adopt Angular if:**
- The development team is small — Angular's ceremony-to-output ratio is too high for a 1–2 person team

**Do not adopt Ignition if:**
- The scope remains a 104-breaker shopping mall installation with custom floor-plan requirements

**Do not adopt Svelte 5 yet:**
- Ecosystem and SA talent pool are too thin for a long-lived industrial system

**Next step:** Run the MB 1.1 vertical-slice pilot (3 weeks, ~R25K). If it passes all success criteria, proceed to full implementation with React 19. Update SPEC.md §2.2 with the locked stack table and add the framework-agnostic architecture constraint to the project ADR register.
