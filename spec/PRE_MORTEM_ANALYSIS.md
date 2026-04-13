# PRE-MORTEM ANALYSIS

**Plan / Project:** Kingswalk Mall SCADA GUI — Monitoring, Alarms & PQ Logging System
**Pre-Mortem Date:** 2026-04-11
**Prospective Horizon:** 14 weeks (commissioning deadline ~2026-07-18)
**Failure Frame:** "It is 2026-07-18. The DB manufacturer has commissioned the first main boards and is ready for integration testing. The SCADA GUI has failed to deliver a working system that can connect to the live network, display breaker states, trigger alarms, and log PQ data. The 14-week window is blown. Looking back, here is what went wrong."

---

## PLAN SUMMARY (Pre-Analysis Baseline)

**Objective:** Deliver a fully operational, cloud-hosted SCADA monitoring GUI that reads ~150 ABB field devices across 9 main boards, displays live breaker state, detects 48V relay bypass events, triggers tiered alarms, and logs continuous power quality data — ready for commissioning plug-in within 14 weeks.

**Key milestones:**
- Weeks 1–3: Foundation (schema, auth, CI/CD, cloud infrastructure)
- Weeks 4–6: Real-time core (WebSocket, Modbus gateway, event bus, edge gateway)
- Weeks 7–9: Asset management (CRUD, asset registry, documents)
- Weeks 10–12: Monitoring dashboard (live state, bypass detection, alarms)
- Weeks 13–14: Power quality (PQ trends, continuous aggregates, commissioning testing)

**Critical assumptions:**
1. Watson Mattheus drives the Modbus register map specification; DB manufacturer accepts and implements it
2. Cloud deployment with on-site edge gateway meets the <1s latency target
3. Bypass detection can be inferred from breaker state vs relay command comparison
4. Internet connectivity exists at site for cloud access
5. Claude can generate production-quality code across the full stack within the timeline
6. Arno has sufficient availability to review, test, and make domain decisions at each phase gate

**Key dependencies:**
- DB manufacturer delivers commissioned hardware on the VLAN network with Modbus TCP accessible
- Construction progress doesn't delay electrical infrastructure installation
- Cloud provider (Railway/AWS/Azure) available with TimescaleDB support
- Operator recruitment completed before user acceptance testing
- Site internet connectivity provisioned before integration testing

**Resources committed:**
- Software team: Arno (domain expert, part-time reviewer) + Claude (full-stack code generation)
- No dedicated human developers
- Budget: Not explicitly defined (risk factor)

---

## FAILURE MODE TAXONOMY

### EXECUTION FAILURES

| # | Failure Mode | Root Cause | Probability | Impact | Early Warning Signal |
|---|---|---|---|---|---|
| E1 | **Edge gateway latency exceeds 1s target** | Cloud architecture adds site→cloud round trip that wasn't in original on-site design. VPN overhead + geographic distance to cloud DC + Modbus polling time combine to exceed budget | Medium | High | First Modbus-to-browser round trip measurement during integration exceeds 800ms |
| E2 | **Arno becomes the bottleneck** | Every domain decision, schema review, and PR approval funnels through one person who also has other engineering projects. Claude generates faster than Arno can review | High | High | PR review queue exceeds 3 items; phase gates delayed by >3 days waiting for Arno's review |
| E3 | **Mock data diverges from real ABB device behaviour** | Software developed against simulated Modbus data that doesn't match actual Ekip/M4M register responses. Integration testing reveals data format mismatches, unexpected register values, or polling behaviour differences | High | High | No real device available for even partial validation by week 8 |
| E4 | **WebSocket fan-out doesn't scale to 150 devices at polling cadence** | 104 breakers at 250ms + PQ at 1s + energy at 30s creates a higher message throughput than anticipated. Redis pub/sub + WebSocket broadcast creates backpressure | Medium | Medium | Load test (simulated 150 devices) shows message delivery lag >500ms or dropped messages |
| E5 | **Auth system takes longer than planned** | argon2id + TOTP MFA + JWT rotation + recovery codes + session management + RBAC middleware is a complex auth stack for weeks 1–3. Scope creep into edge cases (MFA reset, force logout, rate limiting) | Medium | Medium | Auth system still incomplete at end of week 3; blocking real-time core phase |
| E6 | **Code quality debt from AI generation** | Claude generates working code that passes tests but accumulates architectural inconsistencies across sessions. Different sessions make conflicting design choices without a human developer maintaining coherence | Medium | High | Increasing test failures when integrating modules from different phases; conflicting patterns in codebase |

### ASSUMPTION FAILURES

| # | Failure Mode | Root Cause | Probability | Impact | Early Warning Signal |
|---|---|---|---|---|---|
| A1 | **DB manufacturer rejects or significantly modifies the register map proposal** | WM assumes they drive the spec, but the DB manufacturer has their own standard PLC programming templates and preferred register layouts. Negotiation takes weeks, not days | Medium | Critical | DB manufacturer response to register map proposal is delayed >2 weeks or contains >30% changes |
| A2 | **48V relay bypass detection logic is more complex than assumed** | Assumed simple breaker-state-vs-relay-command comparison. In practice, relay state may not be available via Modbus (it's a hardwired 48V circuit, not a digital signal). Detection may require inferring from load profile patterns, not direct state comparison | Medium | High | DB manufacturer confirms no dedicated relay status register exists; alternative detection method needed |
| A3 | **Cloud hosting with TimescaleDB is more complex/expensive than expected** | TimescaleDB on managed PostgreSQL requires specific provider support. Railway doesn't offer TimescaleDB natively. AWS/Azure TimescaleDB requires self-managed instances. Cost of managed DB + Redis + backend containers + bandwidth exceeds unstated budget | Medium | Medium | TimescaleDB not available on first-choice cloud provider; self-hosting required; monthly cloud costs exceed R5,000 |
| A4 | **Site internet connectivity not provisioned in time** | Construction site may not have permanent internet installed during the 14-week window. Temporary construction internet may be unreliable or insufficient bandwidth for continuous telemetry upload | Medium | High | No confirmed internet service order by week 6; construction project manager cannot commit to a date |
| A5 | **Claude-generated code doesn't handle ABB protocol edge cases** | Modbus TCP has device-specific quirks: connection timeouts, register block read limitations, byte ordering (big-endian vs little-endian), exception response codes. AI-generated Modbus code works against simulators but fails against real devices | High | High | First real-device connection attempt fails or returns garbled data |

### EXTERNAL SHOCK FAILURES

| # | Failure Mode | Root Cause | Probability | Impact | Early Warning Signal |
|---|---|---|---|---|---|
| X1 | **Construction delays push electrical installation beyond week 14** | Building construction is delayed (weather, contractor disputes, material supply chain). Electrical infrastructure installation hasn't started when software is ready for integration | Medium | Critical | Construction programme shows electrical rough-in not started by week 6; DB manufacturer has no installation date |
| X2 | **Load shedding disrupts site commissioning** | South Africa load shedding at Stage 4+ makes site commissioning intermittent. Generator testing and SCADA integration testing require stable power, which may not be available during commissioning window | Low | Medium | Eskom announces Stage 4+ schedule overlapping the commissioning window |
| X3 | **ABB supply chain delay** | M4M 30 modules, Ekip Com units, or Tmax XT breakers are on extended lead time. DB manufacturer has ordered but delivery is delayed. Can't commission what hasn't arrived | Medium | Critical | DB manufacturer reports ABB equipment delivery pushed by >4 weeks |
| X4 | **Claude API availability or capability regression** | AI model changes, API rate limits, or service disruptions during the build window slow or block code generation. Anthropic pricing changes make sustained use uneconomical | Low | High | API errors increase; model quality on SCADA-specific tasks degrades; costs per session exceed budget |

### POLITICAL / ORGANIZATIONAL FAILURES

| # | Failure Mode | Root Cause | Probability | Impact | Early Warning Signal |
|---|---|---|---|---|---|
| P1 | **Centre ownership/management doesn't prioritise SCADA system** | The property owner or centre manager views the SCADA system as Watson Mattheus' project, not their operational priority. Doesn't allocate budget for operators, cloud hosting, or internet connectivity | Medium | High | No operator recruitment initiated by week 8; hosting budget not confirmed; "we'll worry about that later" responses |
| P2 | **DB manufacturer treats interface contract as low priority** | DB manufacturer focuses on physical installation (their core business). Software interface specifications are deprioritised — register map feedback is delayed, VLAN configuration is deferred, Modbus accessibility is an afterthought | High | Critical | DB manufacturer hasn't responded to register map proposal by week 4; no VLAN test environment available |
| P3 | **Scope creep from stakeholders seeing early demos** | Property owners/managers see the R1 dashboard in development and request features (custom reports, tenant billing integration, access control, CCTV integration) that expand scope beyond monitoring | Medium | Medium | Feature requests from viewers start arriving before R1 is complete; Arno starts adding items to SPEC.md |

### RESOURCE FAILURES

| # | Failure Mode | Root Cause | Probability | Impact | Early Warning Signal |
|---|---|---|---|---|---|
| R1 | **No budget defined for cloud hosting and ongoing operations** | The spec defines the technology stack but not the operational budget. Monthly cloud costs (managed PG + TimescaleDB + Redis + backend hosting + bandwidth + email/SMS) could be R3,000–R10,000/month. No one has committed to paying this | High | Medium | No cloud account provisioned by week 2; no purchase order or billing arrangement for hosting |
| R2 | **Arno's time is split across other projects** | Arno is a consulting engineer with multiple projects. Kingswalk SCADA gets 20–30% of his time instead of 50%+. Review backlogs grow, domain decisions are delayed, phase gates slip | High | High | Arno unavailable for >3 consecutive working days during any phase; response time to PRs exceeds 48 hours |
| R3 | **No edge gateway hardware specified or procured** | The spec calls for an "on-site edge gateway device" but doesn't specify what it is (Raspberry Pi? Industrial PC? VM on site server?). Hardware procurement has lead time. No one has ordered it | High | Medium | Edge gateway hardware not selected by week 4; not on-site by week 10 |
| R4 | **Operator recruitment not started** | 3 operators need to be appointed before go-live. This requires a job description, recruitment, hiring, and training. None of this has started. No one owns this task | High | Medium | No job description written by week 6; no candidates by week 10 |

### TIMING FAILURES

| # | Failure Mode | Root Cause | Probability | Impact | Early Warning Signal |
|---|---|---|---|---|---|
| T1 | **Integration testing window too short** | Weeks 13–14 are allocated for PQ trends and commissioning testing. But integration with real hardware always surfaces unexpected issues. 2 weeks is insufficient for debugging Modbus connectivity, validating all 104 breakers, and running full alarm scenarios | High | High | Any phase slips by >3 days, compressing the integration window below 2 weeks |
| T2 | **DB manufacturer's commissioning and software integration testing must happen simultaneously** | DB manufacturer commissions boards sequentially (one MB at a time). Each board needs individual validation. If they commission all 9 boards in weeks 13–14, SCADA integration testing is trying to hit a moving target | Medium | Medium | DB manufacturer's commissioning schedule not aligned with SCADA testing plan |
| T3 | **R2 and R3 features creep into R1 timeline** | Floor plan canvas (R3) is deferred but the spec says operators need self-explanatory UI from day one. Pressure to include visual navigation in R1 because operators "won't understand the system without it" | Medium | Medium | Arno or stakeholders push for floor plan canvas to be in R1; scope of R1 dashboard expands |

---

## TOP 5 FAILURE MODES (Ranked by Probability × Impact)

### #1: DB Manufacturer Treats Interface Contract as Low Priority (P2) — CRITICAL

**Probability:** High (>50%) — DB manufacturers' core competency is physical switchgear, not software interfaces. Interface specifications are typically an afterthought in South African electrical contracting.

**Impact if occurs:** Critical — without Modbus register maps confirmed, IP addressing implemented, and VLANs configured, the SCADA GUI has nothing to connect to. The entire software build is rendered useless regardless of its quality.

**Root cause (5 Whys):**
1. Why didn't the DB manufacturer deliver the interface? → They deprioritised it
2. Why did they deprioritise it? → Physical installation was behind schedule and consumed all their attention
3. Why was physical installation behind? → Construction delays cascaded to electrical fit-out
4. Why didn't WM escalate earlier? → No formal interface delivery milestones were contractually agreed
5. **Root cause:** The interface contract is not embedded in the DB manufacturer's commercial agreement with enforceable milestones

**Early warning signal:** DB manufacturer has not responded to the register map proposal within 2 weeks of delivery. No VLAN test environment available by week 6. DB manufacturer's project manager cannot confirm Modbus accessibility dates.

**Warning threshold:** If no signed-off register map by week 4, escalate immediately.

**Prevention strategy:**
1. Deliver the register map proposal to the DB manufacturer within 1 week (by 2026-04-18)
2. Include interface delivery milestones in the commercial agreement: register map sign-off by week 4, first VLAN test point by week 8, first MB on network by week 10
3. Request a pre-commissioning Modbus test — even one Ekip Com module on a bench with correct register configuration — by week 6
4. Design the edge gateway to work against a Modbus simulator that matches the agreed register map, so software development is not blocked

**Prevention cost:** 2–3 days of Arno's time to prepare and negotiate the interface contract. Low cost, extremely high return.

---

### #2: Arno Becomes the Single-Point-of-Failure Bottleneck (E2 + R2) — CRITICAL

**Probability:** High (>50%) — Arno is a consulting engineer with multiple clients. The build model routes ALL domain decisions, PR reviews, and phase gate approvals through him. Claude generates code far faster than a part-time reviewer can absorb.

**Impact if occurs:** High — every phase slips by the duration of Arno's review backlog. A 3-day delay per phase across 5 phases = 15 days = the entire buffer in a 14-week plan.

**Root cause (5 Whys):**
1. Why did phases slip? → PRs waited for Arno's review
2. Why was Arno slow to review? → He was managing other Watson Mattheus projects simultaneously
3. Why couldn't someone else review? → Arno is the only person who understands both the electrical domain and the software spec
4. Why is there no backup? → The team is two entities: Arno and Claude. No junior engineer or developer to share the load
5. **Root cause:** Single-person dependency with no delegation path for domain review, combined with a team model that assumes Arno's near-full-time availability

**Early warning signal:** Arno's average PR review time exceeds 48 hours. More than 2 PRs queued without review. Arno misses a scheduled phase gate review.

**Warning threshold:** If review latency exceeds 3 working days at any point, the 14-week deadline is at risk.

**Prevention strategy:**
1. Pre-schedule Arno's review blocks: 2 hours every Monday and Thursday for the 14-week window (calendar commitments, not intentions)
2. Define a "pre-approved" zone: for code that doesn't touch the schema, protocol, or asset model, Claude can merge without Arno's review if CI passes. Arno reviews the batch weekly
3. Front-load domain decisions: resolve all ambiguous schema, protocol, and alarm logic questions in weeks 1–2 so that execution phases have fewer blocking decisions
4. Create an "Arno Decision Log" document where decisions are recorded so Claude doesn't re-ask the same question in different sessions

**Prevention cost:** 4 hours to set up the decision framework and pre-approve zones. Saves potentially weeks of delay.

---

### #3: Mock Data Diverges from Real ABB Device Behaviour (E3 + A5) — HIGH

**Probability:** High (>50%) — Modbus TCP implementations vary between device families. ABB Ekip Com modules, M4M 30 analysers, and Tmax XT trip units each have their own register maps, byte ordering, and polling behaviour. Simulators will approximate but not replicate these.

**Impact if occurs:** High — integration testing reveals that the polling engine, data parsing, and state detection all need rework. What worked against the simulator fails against real hardware. This rework happens in the already-compressed weeks 13–14.

**Root cause (5 Whys):**
1. Why did integration fail? → Real device data didn't match the mock data format
2. Why didn't the mock match? → The simulator was built from ABB documentation, not from actual device captures
3. Why not from device captures? → No physical device was available during development
4. Why wasn't a device available? → Site is under construction; no hardware installed yet
5. **Root cause:** 14-week parallel development means the software team has zero access to real hardware for ~12 of 14 weeks. All assumptions about device behaviour are theoretical until integration

**Early warning signal:** DB manufacturer cannot provide a bench test device by week 6. Register map has ambiguities (register sizes, signed vs unsigned, scaling factors) that can't be resolved without a real device.

**Warning threshold:** If no real Modbus device has been tested against by week 10, budget 2 extra weeks for integration debugging.

**Prevention strategy:**
1. Request one M4M 30 module and one Ekip Com module from the DB manufacturer for bench testing (even a demo/evaluation unit) by week 4
2. If physical bench test units are unavailable, request a Modbus register dump (CSV export of all registers with sample values) from the DB manufacturer from a previously commissioned installation of the same ABB hardware
3. Build the Modbus simulator with configurable byte ordering, scaling, and error injection — not just "happy path" data
4. Design the edge gateway polling engine with a compatibility layer: register definitions are config-driven (JSON/YAML), not hardcoded. This makes fixing real-device mismatches a config change, not a code change

**Prevention cost:** R5,000–R15,000 for evaluation hardware rental; 1 day of Arno's time to arrange with DB manufacturer. Alternatively, 0 cost for requesting register dumps from a prior installation.

---

### #4: Integration Testing Window Too Short (T1) — HIGH

**Probability:** High (>50%) — 2 weeks for integration testing against 9 main boards, 104 breakers, and ~150 devices is aggressive even without prior delays. Any phase slip compresses this window further.

**Impact if occurs:** High — the system either ships untested (unacceptable for a professional monitoring system) or the deadline slips. The DB manufacturer's commissioning schedule may not accommodate a re-test window.

**Root cause (5 Whys):**
1. Why was 2 weeks insufficient? → More issues were found during integration than anticipated
2. Why were there more issues? → Software was developed against simulators, not real hardware
3. Why were simulators insufficient? → Device-specific quirks only manifest with real hardware
4. Why couldn't testing start earlier? → Hardware wasn't commissioned until weeks 12–13
5. **Root cause:** The plan assumes linear execution with no buffer. Integration testing is the riskiest phase but allocated the least time

**Early warning signal:** Any phase slips by more than 3 days. DB manufacturer cannot confirm a commissioning date for the first MB by week 8.

**Warning threshold:** If the integration testing window drops below 10 working days, the delivery date is at risk.

**Prevention strategy:**
1. Add a 1-week buffer: compress phases 1–4 by deferring non-critical scope to R2, freeing week 12 for early integration testing. Total integration window: 3 weeks (weeks 12–14) instead of 2
2. Request the DB manufacturer to commission one "pilot" MB early (week 8–10) so integration testing can start incrementally against real hardware while software development continues
3. Define a "commissioning readiness checklist" that the DB manufacturer must complete per MB before SCADA integration begins — prevents wasted time on half-configured boards
4. Accept that R1 commissioning may validate a subset (e.g., 3 of 9 MBs fully tested, 6 validated by extension) with remaining boards tested during weeks 15–16 as a follow-on

**Prevention cost:** 1 day to negotiate pilot MB with DB manufacturer. Schedule compression requires prioritisation decisions in weeks 1–4.

---

### #5: No Edge Gateway Hardware Specified or Procured (R3) — MEDIUM-HIGH

**Probability:** High (>50%) — the spec says "on-site edge gateway" but doesn't name the hardware. Nobody has ordered it. Procurement takes time, especially for industrial-grade hardware in South Africa.

**Impact if occurs:** Medium — without the edge gateway, the cloud-hosted application cannot reach the Modbus devices. This blocks integration testing entirely, even if everything else is ready.

**Root cause (5 Whys):**
1. Why wasn't the gateway available? → It wasn't ordered
2. Why wasn't it ordered? → No one was assigned this task
3. Why wasn't it assigned? → The spec describes the software, not the hardware procurement
4. Why not? → The project scope split assigns hardware to the DB manufacturer, but the edge gateway sits between the two scopes
5. **Root cause:** The edge gateway falls in the gap between Watson Mattheus' software scope and the DB manufacturer's hardware scope. Neither party has explicitly taken ownership

**Early warning signal:** No hardware specification document by week 2. No purchase order by week 4. No delivery confirmation by week 8.

**Warning threshold:** If edge gateway hardware is not on-site and powered by week 10, integration testing cannot proceed.

**Prevention strategy:**
1. Specify the edge gateway hardware this week: recommend an industrial mini-PC (e.g., Advantech UNO-2271G or similar) with dual Ethernet (one for SCADA VLAN, one for internet/VPN), running Ubuntu 22 + Python 3.12 + WireGuard
2. Assign procurement to Watson Mattheus (it's their software scope, not the DB manufacturer's)
3. Order the hardware within 2 weeks (by 2026-04-25) to account for 4–6 week delivery lead time to South Africa
4. As a contingency, configure the edge gateway to run on a temporary laptop during commissioning testing if the industrial hardware hasn't arrived

**Prevention cost:** R8,000–R25,000 for industrial edge gateway hardware. 2 hours to specify. Must be ordered immediately.

---

## COMPOSITE FAILURE RISK ASSESSMENT

**Overall risk level:** HIGH

**Primary risk concentration:** The risk is concentrated in the **interface between software and hardware** — specifically, the DB manufacturer dependency (P2), mock-to-real data gap (E3/A5), and the edge gateway procurement gap (R3). The software build itself is achievable; the integration with physical infrastructure is where failure is most likely.

**Most surprising finding:** The edge gateway — the physical device that bridges Modbus to cloud — is not specified, not ordered, not owned by either party, and has a procurement lead time that already threatens the timeline. This is a completely avoidable failure mode that nobody has addressed.

**Most overlooked assumption:** The 48V relay bypass detection (A2). The spec assumes breaker state vs relay command is a simple comparison, but the 48V relay circuit may be entirely hardwired with no Modbus-visible state. If the relay status isn't in a register, bypass detection requires a fundamentally different approach (load profile analysis, current signature comparison) that is significantly more complex to build and validate.

---

## PRE-MORTEM ACTION LIST

| # | Action | Failure Mode(s) Addressed | Owner | Deadline | Expected Risk Reduction |
|---|---|---|---|---|---|
| 1 | Deliver Modbus register map proposal to DB manufacturer | P2, A1, E3 | Arno | 2026-04-18 (week 1) | Critical |
| 2 | Negotiate interface delivery milestones into DB manufacturer's commercial agreement | P2, X1 | Arno | 2026-04-25 (week 2) | Critical |
| 3 | Specify edge gateway hardware and place purchase order | R3 | Arno | 2026-04-25 (week 2) | High |
| 4 | Schedule Arno's fixed review blocks (Mon/Thu, 2hrs each) for 14 weeks | E2, R2 | Arno | 2026-04-14 (this week) | High |
| 5 | Define "pre-approved merge" zones for non-domain code | E2, R2 | Arno + Claude | 2026-04-18 (week 1) | Medium |
| 6 | Request bench test device (M4M 30 or Ekip Com) from DB manufacturer | E3, A5 | Arno | 2026-04-25 (week 2) | High |
| 7 | Confirm 48V relay status is available via Modbus register | A2 | Arno (ask DB manufacturer) | 2026-04-25 (week 2) | High |
| 8 | Confirm site internet service order with construction PM | A4 | Arno | 2026-04-25 (week 2) | Medium |
| 9 | Confirm cloud hosting budget with centre ownership | R1, P1 | Arno | 2026-05-02 (week 3) | Medium |
| 10 | Request DB manufacturer to commission 1 pilot MB by week 8–10 | T1, T2, E3 | Arno | 2026-04-25 (week 2) | High |
| 11 | Initiate operator recruitment (job description + posting) | R4 | Centre management (Arno to prompt) | 2026-05-09 (week 4) | Medium |
| 12 | Front-load all schema/protocol/alarm logic decisions into weeks 1–2 | E2 | Arno + Claude | 2026-04-25 (week 2) | Medium |

---

## ASSUMPTION VALIDATION REQUIRED

| # | Assumption | Validation Method | By When | Owner |
|---|---|---|---|---|
| 1 | DB manufacturer will accept WM's register map proposal | Deliver proposal and track response | Week 2 | Arno |
| 2 | 48V relay bypass is detectable via Modbus register data | Ask DB manufacturer: is relay state available as a Modbus register? If not, what signals are available? | Week 2 | Arno |
| 3 | Cloud site-to-edge latency stays within 1s budget | Deploy test VPN tunnel + Modbus simulator; measure round trip | Week 5 | Claude |
| 4 | TimescaleDB available on chosen cloud provider at acceptable cost | Provision test instance; confirm pricing | Week 2 | Claude |
| 5 | Site internet connectivity will be available for commissioning | Confirm service order with construction PM | Week 3 | Arno |
| 6 | Claude can maintain code consistency across 14 weeks of sessions | Establish coding standards, shared context docs, automated CI checks | Week 1 | Claude |
| 7 | 28 users (5+3+20) can be served without performance degradation | Load test with k6 at 30 concurrent WebSocket connections | Week 12 | Claude |

---

## EARLY WARNING DASHBOARD

| # | Metric / Signal | Warning Threshold | Response Trigger | Monitoring Frequency | Owner |
|---|---|---|---|---|---|
| 1 | DB manufacturer response to register map | No response by day 14 | Arno escalates to DB manufacturer management | Weekly | Arno |
| 2 | Arno PR review queue depth | >2 PRs unreviewed for >48hrs | Activate pre-approved merge zones | Twice weekly | Claude |
| 3 | Phase completion vs schedule | Any phase >3 days late | Compress non-critical scope; protect integration window | Weekly | Arno + Claude |
| 4 | Edge gateway hardware delivery status | Not on-site by week 8 | Activate laptop contingency; escalate with supplier | Fortnightly | Arno |
| 5 | DB manufacturer commissioning schedule | No confirmed date for first MB by week 6 | Arno meets DB manufacturer on-site to assess readiness | Monthly | Arno |
| 6 | Site internet service order status | No confirmed install date by week 6 | Provision temporary 4G/5G backup; budget for mobile data | Monthly | Arno |
| 7 | Cloud hosting monthly cost | Exceeds R8,000/month | Review architecture; consider optimisation or alternative provider | After first month live | Claude |
| 8 | Integration test success rate | <80% of breakers reporting correctly after first week of integration | Extend integration window; defer non-critical R1 scope | Daily during integration | Arno + Claude |

---

## PLAN MODIFICATIONS RECOMMENDED

1. **Add a formal interface contract milestone to the DB manufacturer relationship.** The register map proposal must be delivered by week 1 and signed off by week 4. Without this, the project has no enforceable mechanism to ensure the hardware is software-ready.

2. **Specify and order edge gateway hardware immediately.** This is a procurement gap that will silently kill the timeline if not addressed in the next 2 weeks. Recommend Advantech industrial PC or equivalent; budget R15,000–R25,000.

3. **Compress phases 1–4 to free a 3-week integration window (weeks 12–14).** The current 2-week window is insufficient. Achieve this by: (a) using a battle-tested auth library instead of building from scratch (saves ~1 week), (b) deferring asset document management to R2 (saves ~3 days), (c) building a simpler alarm view for R1 with the full dashboard deferred to R2.

4. **Request a pilot MB commissioning by week 8–10.** Even one main board on the network with Modbus accessible transforms integration risk from "complete unknown" to "known quantity with scaling factor."

5. **Confirm 48V relay Modbus visibility immediately.** If the relay status is not available via Modbus, the bypass detection approach needs redesign now — not during integration testing. This is a 1-email question to the DB manufacturer.

6. **Establish Arno's review cadence and pre-approved merge zones before build starts.** The bottleneck risk is high and entirely preventable with upfront process design.

7. **Define and commit the operational budget.** Cloud hosting, SMS alerts, email service, and edge gateway hardware all have ongoing costs. If centre management hasn't committed budget, the system may be built but never run.

---

## WHAT THIS PLAN DOES WELL (Risk-Balanced View)

Despite the identified risks, this project has several genuine strengths:

1. **Exceptionally thorough specification.** SPEC.md v3.0 at 800+ lines is one of the most detailed SCADA system specifications I've analysed. The database schema, polling cadence, network addressing plan, and asset registry are all production-ready detail. This dramatically reduces the risk of mid-build ambiguity.

2. **Monitoring-only scope is the right decision.** By removing remote control, the project eliminated an entire class of safety-critical failure modes. A monitoring system that displays stale data is embarrassing; a control system that sends wrong commands is dangerous. This decision makes the 14-week timeline realistic.

3. **Domain expert involvement is continuous, not handoff-based.** Arno isn't writing a spec and throwing it over the wall — he's embedded in the review loop. This prevents the classic "built exactly what was specified, but not what was needed" failure.

4. **The AI-assisted build model is well-suited to this project.** The system has clear input (Modbus registers), clear output (web dashboard), well-defined data model (104 breakers, 9 boards, known relationships), and well-documented target technology (ABB datasheets available). These are ideal conditions for AI code generation — bounded, well-specified, and verifiable.

5. **The release sequence (R1/R2/R3) is correctly prioritised.** Monitoring and alarms first, reporting second, visual navigation third. This means the highest-value feature (bypass detection) ships first, and each subsequent release adds value without blocking core functionality.

6. **The three-party model is clear.** Unlike many projects where scope boundaries are vague, the split between DB manufacturer (hardware), Watson Mattheus (software), and the interface contract is explicit. The risk is not in the model — it's in ensuring the DB manufacturer honours their side of it.
