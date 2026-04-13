# SPRINT 0 — Pre-Build Action Tracker

**Project:** Kingswalk SCADA Monitoring System
**Owner:** Arno (Watson Mattheus)
**Purpose:** These items must be completed (or at least have firm answers) before the 14-week build clock starts. Every item here blocks something in the build — if you skip Sprint 0 and start coding, you will hit these same questions at Week 6 when they're 10x more expensive to deal with.
**Target completion:** 2026-04-25 (two weeks from today)

---

## ACTION 1 — 48V Relay Command State Readability

**Assumption:** #3 (CRITICAL / UNKNOWN)
**Why it matters:** The bypass detection alarm — the core business case for the entire SCADA system — requires comparing the relay's commanded state ("I told this breaker to open") against the breaker's actual state ("the breaker is closed"). We know we can read the breaker's actual state via Modbus. We do not know how (or if) we can read the relay's command state. If the 48V relay is a dumb electromechanical device with no digital output, bypass detection as designed does not work.

**Action:** Contact Profection Switchboards with this exact question: *"Does the 48V relay load-shedding system have a digital/Modbus-readable status output? If yes, what register address? If no, what signal is available — for example, 48V DC presence on a monitored contact that could be wired to a digital input on the Ekip Com?"*

This is already Question 4 in WM-KW-SCADA-REQ-001, but it must be tracked separately because it is existential.

| Field | Detail |
|---|---|
| **Owner** | Arno |
| **Due** | 2026-04-18 (send question); 2026-04-25 (answer received) |
| **Done criteria** | Written confirmation from Profection specifying either (a) a Modbus register address for relay command state, or (b) a contact/signal that can be monitored, or (c) explicit confirmation that no readable state exists |
| **If answer is NO** | Redesign bypass detection to use inference logic: if mains is down AND generator is running AND a non-essential breaker is closed, then the relay was bypassed. Document reduced reliability. Consider adding a purpose-built relay state monitor (DI module wired to relay coil, ~R2,000). This design change must happen before the build starts. |
| **Blocks** | Phase 2 (bypass detection), commissioning acceptance criterion #4 |

**Status:** [ ] Not started  [ ] Question sent  [ ] Answer received — YES / NO / PARTIAL

---

## ACTION 2 — Profection Interface Spec Response & Register Maps

**Assumption:** #4 (CRITICAL / LOW)
**Why it matters:** Profection Switchboards is the single largest external dependency. They hold the register maps, the commissioning schedule, the VLAN implementation, the bench test hardware, and the answer to Action 1. Without their engagement, development proceeds against guesses.

**Action:** Follow up on WM-KW-SCADA-IF-001 (Interface Specification) and WM-KW-SCADA-REQ-001 (Bench Test Request). Get a written commitment on:
1. Register map delivery date (Modbus holding register addresses for breaker state, trip cause, PQ parameters)
2. Bench test unit availability date (one Ekip Com + Tmax XT trip unit for bench testing)
3. First main board commissioning date (when will the first MB be live on the network?)
4. Confirmation of the VLAN/subnet plan as specified

Establish a bi-weekly check-in cadence with Profection's project engineer.

| Field | Detail |
|---|---|
| **Owner** | Arno |
| **Due** | 2026-04-14 (follow-up call/email); 2026-04-25 (written commitment received) |
| **Done criteria** | Written response from Profection with dates for all 4 items above |
| **If no response by 2026-04-25** | Escalate to the client (property owner/developer) to apply commercial pressure. In parallel, proceed with ABB generic register documentation and explicit TODO markers on all register addresses. Budget 2 extra weeks at end for integration rework. |
| **Blocks** | Phase 2 (edge gateway), Phase 4 (integration testing), all Modbus register addresses |

**Status:** [ ] Not started  [ ] Follow-up sent  [ ] Response received  [ ] Dates confirmed

---

## ACTION 3 — Edge Gateway Hardware Specification & Procurement

**Assumption:** #24 (CRITICAL / LOW)
**Why it matters:** Every piece of edge gateway software (systemd poller, SQLite buffer, WireGuard VPN, health endpoint) assumes a physical device exists to run on. Nobody has specified what that device is, who buys it, or when it arrives. Lead times for industrial-grade hardware can be 4-8 weeks.

**Action:** Specify the edge gateway hardware this week. Three options to evaluate:

| Option | Device | Approx. Cost | Pros | Cons |
|---|---|---|---|---|
| A | Industrial PC (Advantech UNO-2000 or similar) | R15,000–R25,000 | DIN-rail mount, industrial temp range, multiple Ethernet, reliable | Cost, lead time |
| B | Raspberry Pi 5 8GB in DIN-rail enclosure | ~R3,500 | Cheap, available, adequate for monitoring-only workload | Single Ethernet (needs USB-Ethernet adapters for multi-VLAN), not industrial-grade |
| C | Server in switchroom (provided by Profection) | R0 (included) | No procurement | Must confirm with Profection; unknown specs |

Determine: Who procures it? Who installs the OS and configures the network? Does it need multiple physical Ethernet interfaces, or can it use VLAN tagging on a single trunk port?

| Field | Detail |
|---|---|
| **Owner** | Arno |
| **Due** | 2026-04-18 (specification decision); 2026-04-25 (order placed) |
| **Done criteria** | Hardware specified, quoted, ordered, with confirmed delivery date within 6 weeks (by 2026-06-06, which is build Week 8) |
| **If delayed** | Use a temporary laptop as the edge gateway for commissioning testing. This is a stopgap — it must be replaced before handover. |
| **Blocks** | Phase 2 (edge gateway deployment from Week 4), Phase 4 (commissioning testing) |

**Status:** [ ] Not started  [ ] Option selected  [ ] Quote received  [ ] Ordered  [ ] Delivery confirmed

---

## ACTION 4 — Internet Connectivity at Kingswalk

**Assumption:** #10 (CRITICAL / LOW)
**Why it matters:** The entire cloud architecture depends on a VPN tunnel from the edge gateway to the cloud. No internet = no monitoring. The 4G failover is designed for temporary outages, not as a primary connection. The site is under construction — fibre may not be provisioned yet.

**Action:** Ask the client/project manager:
1. What is the ISP for the mall?
2. When is fibre expected to be installed and active?
3. Is there a dedicated connection for SCADA, or will it share the mall's general internet?
4. What is the expected bandwidth and SLA?

| Field | Detail |
|---|---|
| **Owner** | Arno |
| **Due** | 2026-04-18 (questions sent); 2026-04-25 (answers received) |
| **Done criteria** | Confirmed ISP, fibre installation date before build Week 12 (2026-07-04), connection type (dedicated or VLAN-segregated) |
| **If fibre not available by Week 12** | Budget for a dedicated 4G/LTE router as the primary connection (~R500/month for 50GB data SIM). This works but adds latency and reduces reliability. Adjust the VPN architecture from "fibre primary + 4G failover" to "4G primary + no failover" and document the risk. |
| **Blocks** | Phase 4 (commissioning testing), production deployment |

**Status:** [ ] Not started  [ ] Questions sent  [ ] Answers received — fibre date: ___________

---

## ACTION 5 — Review SLA with Arno

**Assumption:** #14 (IMPORTANT / LOW)
**Why it matters:** Arno is the sole domain expert and the only person who can validate that the system matches the electrical installation reality. If reviews queue up, the build stalls. The pre-mortem flagged this as failure mode #2.

**Action:** Agree on a review SLA before the build starts:
- Arno reviews and responds to PRs/deliverables within **48 hours**
- If Arno cannot review within 48 hours, Claude proceeds with best judgment and flags decisions for retrospective review
- Weekly 30-minute sync call to address accumulated domain questions

| Field | Detail |
|---|---|
| **Owner** | Arno |
| **Due** | 2026-04-14 (agree on terms) |
| **Done criteria** | Verbal or written agreement on the 48-hour review SLA and weekly sync schedule |
| **If not agreed** | The 14-week timeline is at risk. Every day of review delay costs a day of build time. |
| **Blocks** | All build phases (every phase requires Arno's domain validation) |

**Status:** [ ] Not started  [ ] Agreed

---

## ACTION 6 — Proof-of-Concept Spike (3 days)

**Assumption:** #13 (CRITICAL / MODERATE)
**Why it matters:** The entire delivery model assumes Claude can generate production-quality code from the spec. No proof-of-concept exists. Before committing 14 weeks to this model, validate it with a focused spike.

**Action:** Run a 3-day spike where Claude generates the Phase 1 skeleton:
- Monorepo scaffold (`/api`, `/web`, `/edge`, `/db`)
- FastAPI project with health check, CORS, error handling
- Auth system (JWT + refresh tokens, argon2id, RBAC middleware)
- React shell with login page and protected routes
- CI/CD pipeline (GitHub Actions: lint, type, test, build)
- PostgreSQL migration runner with `0001_initial.sql`
- Vercel preview deployment

Evaluate: Does the code compile? Do tests pass? Is the architecture clean? Is Arno's review burden manageable (<2 hours)?

| Field | Detail |
|---|---|
| **Owner** | Arno + Claude |
| **Due** | 2026-04-18 (3 working days from start) |
| **Done criteria** | Working auth system with CI/CD pipeline, deployed to Vercel preview. Arno's review takes <2 hours. All tests pass. Architecture matches SPEC and BUILD_STRATEGY. |
| **If it fails** | Options: (a) hire a contract developer to work alongside Claude (budget R80K–R120K for 14 weeks part-time), (b) reduce R1 scope, (c) extend timeline. This decision must be made before committing. |
| **Blocks** | The decision to start the 14-week build clock |

**Status:** [ ] Not started  [ ] Spike in progress  [ ] Spike complete — PASS / FAIL

---

## BONUS: Essential Supply Classification Data

**Assumption:** #20 (IMPORTANT / LOW)
**Why this is here:** The bypass detection alarm targets breakers marked `essential_supply=true`. But nobody has confirmed which breakers are on essential supply and which generator bank (A or B) feeds which distribution boards. The SLD drawings show electrical topology but don't label this.

**Action:** Ask Profection or the client: "Which breakers are on essential supply? Which distribution boards are on generator Bank A vs Bank B?"

| Field | Detail |
|---|---|
| **Owner** | Arno |
| **Due** | 2026-05-01 (can be during Sprint 1, but needed before Phase 2 bypass detection work) |
| **Done criteria** | A list mapping each of the 104 breakers to essential/non-essential and each DB to generator bank A or B |
| **If not available** | Bypass detection alarm fires for ALL breakers, not just essential supply. This creates false positives on non-essential breakers. Tolerable as a temporary state but must be resolved before commissioning. |

**Status:** [ ] Not started  [ ] Question sent  [ ] Data received

---

## SPRINT 0 DECISION GATE

Before starting the 14-week build clock, the following must be true:

| Gate | Required for build start? | Current status |
|---|---|---|
| Action 1 — 48V relay question SENT | YES (answer can come later) | Pending |
| Action 2 — Profection follow-up SENT | YES | Pending |
| Action 3 — Edge hardware SPECIFIED | YES (ordered can come later) | Pending |
| Action 4 — Internet question SENT | YES (answer can come later) | Pending |
| Action 5 — Review SLA AGREED | YES | Pending |
| Action 6 — PoC spike PASSED | YES | Pending |

**If Action 1 comes back NO (relay not readable):** STOP. Redesign bypass detection before proceeding. This adds 1-2 weeks to Sprint 0 but saves 4+ weeks of rework later.

**If Action 6 fails (PoC spike):** STOP. Reassess the delivery model before committing 14 weeks. Hire a developer or reduce scope.

**If all gates pass:** Start the build clock. Week 1 begins.

---

**Last updated:** 2026-04-11
**Next review:** 2026-04-18 (one week)
