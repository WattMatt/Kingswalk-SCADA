# ASSUMPTION MAP: Kingswalk SCADA Monitoring System

**Analyst:** Claude Assumption Mapper
**Date:** 2026-04-11
**Subject:** Full build-out of a cloud-hosted SCADA monitoring GUI for Kingswalk Shopping Centre — 104 breakers, 9 main boards, ~150 field devices, 14-week R1 deadline.
**Stakes:** If key assumptions are wrong: the 14-week deadline slips (contractual/commercial risk), the bypass detection alarm — the core business case — doesn't work on day one, or the system cannot integrate with real ABB hardware after 14 weeks of development against mocks.
**Context:** Pre-build. Spec v4.0 is complete, architecture reviewed, pre-mortem done. No code written yet. Site under construction. DB manufacturer (Profection Switchboards) has received the interface specification but has not yet responded. Build clock has not started.

---

## ASSUMPTION INVENTORY

| # | Assumption | Category | Explicit/Implicit | Stated Basis |
|---|------------|----------|-------------------|-------------|
| 1 | 48V relay bypass can be detected by comparing breaker register state against relay command state via Modbus | Technical | EXPLICIT | SPEC C.6.1 — "system compares expected state (relay command = open) against actual state (breaker register = closed)" |
| 2 | ABB Ekip Com and Tmax XT trip units expose breaker open/closed/tripped state via a readable Modbus register | Technical | IMPLICIT | Assumed from ABB datasheet familiarity; no register map from Profection yet |
| 3 | The 48V relay command state is readable from a Modbus register or can be inferred from a measurable signal | Technical | IMPLICIT | Never explicitly stated how the system knows the relay has commanded "open" — this is the reference side of the comparison |
| 4 | Profection Switchboards will deliver Modbus register maps and bench test hardware in time for integration testing (Weeks 13–14) | Dependency | EXPLICIT | Interface spec WM-KW-SCADA-IF-001 sent; no response yet |
| 5 | Profection will commission the first main board to the network early enough for meaningful integration testing | Dependency | IMPLICIT | Pre-mortem identified this; no confirmed commissioning date |
| 6 | pymodbus AsyncModbusTcpClient is stable enough for 24/7 production use at ~450 reads/second | Technical | IMPLICIT | SPEC names pymodbus; no load testing or production reference cited |
| 7 | Per-VLAN async polling can achieve 250ms breaker state updates across 104 breakers on 9 concurrent polling loops | Technical | EXPLICIT | Architecture review §1.4; designed but not benchmarked |
| 8 | Mock/simulated Modbus data will be representative enough of real ABB device responses that integration is not a surprise | Technical | IMPLICIT | BUILD_STRATEGY assumes parallel development against simulator; no fidelity guarantee |
| 9 | Cloud hosting in South Africa (AWS af-south-1 or Azure SA North) provides <20ms VPN latency to the Kingswalk site | Infrastructure | EXPLICIT | Architecture review recommendation; not measured |
| 10 | Internet connectivity at Kingswalk mall is reliable and has sufficient bandwidth for SCADA telemetry (~2–5 GB/month) | Infrastructure | IMPLICIT | Cloud architecture depends on it; mall is under construction, ISP not confirmed |
| 11 | WireGuard VPN will work through the mall's network infrastructure (NAT, firewalls, ISP) without issue | Infrastructure | IMPLICIT | SPEC names WireGuard; mall network config unknown |
| 12 | 14 weeks is achievable for R1 MVP (monitoring + alarms + PQ logging) using Claude as the primary developer | Timing | EXPLICIT | SPEC D.1 — hard deadline; no comparable project baseline |
| 13 | Claude/AI code generation can produce production-quality FastAPI + React + edge gateway code from the spec documents alone | Resource | IMPLICIT | Entire delivery model rests on this; no proof-of-concept code exists yet |
| 14 | Arno can review and approve deliverables fast enough to not bottleneck the 14-week timeline | Resource | EXPLICIT | Pre-mortem FM#2 identified Arno as sole domain expert and single point of failure |
| 15 | Untrained operators (new hires) can effectively use the system with contextual alarm guidance alone — no classroom training required | Customer | EXPLICIT | SPEC B.1 — "design for untrained operators" with self-explanatory alarms |
| 16 | 28 concurrent users (5 admin + 3 operator + 20 viewer) is the correct sizing — no spike beyond this | Customer | EXPLICIT | Project clarity report; hard-counted roles |
| 17 | R4,000–R5,500/month cloud hosting cost is within Watson Mattheus / client budget | Financial | EXPLICIT | Architecture review cost estimate; budget not formally defined |
| 18 | The asset inventory (104 breakers, 9 MBs) from the SLD drawings is complete and accurate | Technical | EXPLICIT | `sld_per_mb_extract.json` extracted from 10 source PDFs |
| 19 | PostgreSQL 16 + TimescaleDB 2.x (community edition) on a managed instance handles ~1.55M PQ rows/day + state logging without performance issues | Technical | EXPLICIT | Architecture review scalability analysis; estimated comfortable but not benchmarked |
| 20 | The essential_supply / generator_bank classification per breaker is known and can be populated in the database before go-live | Technical | IMPLICIT | Schema has the columns; no confirmed data source for which breakers are essential vs non-essential |
| 21 | POPIA compliance is achievable with the current schema design (7-year audit log, encrypted MFA secrets, soft delete) | Regulatory | EXPLICIT | SPEC Part E; no formal POPIA assessment done |
| 22 | IEC 61850 MMS protocol on TS2 anchor feeders works alongside Modbus TCP without conflicts on the same network | Technical | IMPLICIT | SPEC names dual-stack on TS2; no integration experience cited |
| 23 | ABB M4M 30 network analyser readings (V, I, P, Q, S, PF, THD, harmonics) map cleanly to the telemetry.pq_sample schema columns | Technical | IMPLICIT | Schema designed from ABB datasheets; no register-to-column mapping verified |
| 24 | Edge gateway hardware (unspecified device) is available, ordered, and powerful enough to run Python async polling + SQLite buffer + WireGuard VPN simultaneously | Resource | IMPLICIT | Pre-mortem FM#5 flagged this; no hardware spec or procurement plan |
| 25 | The Vercel + Railway/Docker + managed PG deployment model works for a South African SCADA system with no dedicated DevOps person | Resource | IMPLICIT | No DevOps or DBA on team; cloud services assumed self-managing |
| 26 | React 19 + Zustand + Recharts/ECharts can render live updating SVG floor plans with 200+ hotspots at acceptable performance | Technical | IMPLICIT | Technology assessment evaluated React; no prototype with SCADA-scale SVG exists |
| 27 | Redis 7 pub/sub can fan out breaker state changes to 28 WebSocket connections with <50ms latency | Technical | EXPLICIT | Architecture review latency chain; reasonable but not benchmarked |
| 28 | The mall's VLAN/subnet plan (10.10.XX.0/24) will be implemented exactly as specified by the networking contractor | Infrastructure | IMPLICIT | SPEC B.5 defines the plan; implementation is Profection's scope |
| 29 | Continuous aggregates (pq_1min, pq_15min, pq_hourly, pq_daily) will not materially lag behind real-time data for dashboard queries | Technical | EXPLICIT | Architecture review finding 2.1; mitigation designed but not tested |
| 30 | The 4G/LTE failover SIM will have coverage at the Kingswalk site | Infrastructure | IMPLICIT | Dual-path VPN failover assumes 4G is available; site is in Savannah — coverage not verified |

**Total assumptions extracted:** 30
**Implicit assumptions (previously unstated):** 17 (57%)

---

## PRIORITY MATRIX

| # | Assumption | Criticality | Confidence | Priority |
|---|------------|-------------|------------|---------|
| 3 | 48V relay command state is readable via Modbus | CRITICAL | UNKNOWN | TEST FIRST |
| 2 | ABB trip units expose breaker state via Modbus register | CRITICAL | LOW | TEST FIRST |
| 4 | Profection delivers register maps + bench hardware on time | CRITICAL | LOW | TEST FIRST |
| 24 | Edge gateway hardware specified and ordered | CRITICAL | LOW | TEST FIRST |
| 10 | Internet connectivity at Kingswalk mall | CRITICAL | LOW | TEST FIRST |
| 13 | Claude/AI generates production-quality code | CRITICAL | MODERATE | TEST URGENTLY |
| 12 | 14 weeks achievable for R1 MVP | CRITICAL | MODERATE | TEST URGENTLY |
| 5 | First MB on network in time for integration testing | CRITICAL | LOW | TEST FIRST |
| 6 | pymodbus AsyncModbusTcpClient stable for 24/7 production | IMPORTANT | MODERATE | TEST IN CYCLE |
| 7 | 250ms polling achievable with per-VLAN async | IMPORTANT | MODERATE | TEST IN CYCLE |
| 8 | Mock Modbus data representative of real devices | IMPORTANT | LOW | TEST IN CYCLE |
| 1 | Bypass detection works via register comparison | CRITICAL | MODERATE | TEST URGENTLY |
| 14 | Arno not a bottleneck | IMPORTANT | LOW | TEST IN CYCLE |
| 20 | Essential/non-essential classification data exists | IMPORTANT | LOW | TEST IN CYCLE |
| 22 | IEC 61850 + Modbus TCP coexist on same network | IMPORTANT | MODERATE | MONITOR |
| 23 | M4M 30 readings map to pq_sample schema | IMPORTANT | MODERATE | TEST IN CYCLE |
| 11 | WireGuard works through mall network | IMPORTANT | LOW | TEST IN CYCLE |
| 9 | <20ms VPN latency to SA cloud region | SUPPORTING | MODERATE | MONITOR |
| 28 | VLAN/subnet plan implemented as specified | IMPORTANT | MODERATE | MONITOR |
| 25 | Vercel/Railway works without DevOps | SUPPORTING | MODERATE | MONITOR |
| 26 | React 19 renders 200+ SVG hotspots performantly | SUPPORTING | MODERATE | MONITOR |
| 30 | 4G coverage at Kingswalk site | SUPPORTING | LOW | TEST IF RESOURCES ALLOW |
| 19 | PG + TimescaleDB handles 1.55M rows/day | SUPPORTING | HIGH | ACCEPT |
| 27 | Redis pub/sub <50ms fan-out | SUPPORTING | HIGH | ACCEPT |
| 16 | 28 users is correct sizing | SUPPORTING | HIGH | ACCEPT |
| 17 | R4,000–R5,500/month within budget | SUPPORTING | MODERATE | MONITOR |
| 18 | 104-breaker inventory is complete/accurate | SUPPORTING | HIGH | ACCEPT |
| 21 | POPIA compliance achievable | SUPPORTING | MODERATE | MONITOR |
| 15 | Untrained operators can use contextual alarms | SUPPORTING | MODERATE | MONITOR |
| 29 | Continuous aggregates don't lag materially | SUPPORTING | MODERATE | MONITOR |

---

## CRITICAL ASSUMPTIONS — DEEP ANALYSIS

### Assumption #3: 48V Relay Command State Is Readable

**Full statement:** The SCADA system can determine, via a Modbus register or other measurable signal, whether the 48V relay has commanded a breaker to open during a load-shedding event — this is the "expected state" side of the bypass detection comparison.

**Category:** Technical
**Explicit or Implicit:** IMPLICIT — the spec describes the comparison logic (expected vs actual) but never specifies how the expected state is obtained. The breaker register tells us actual state (open/closed). But what tells us the relay *commanded* open?

**Criticality:** CRITICAL — This is the single most important alarm in the system. If we cannot read the relay command state, bypass detection does not work. The entire business case — "detect when a contractor bypasses the load-shedding relay" — fails.

**Confidence:** UNKNOWN — No evidence either way. The 48V relay system is on the power distribution side, not the Modbus monitoring side. It may not have a register. It may be an electromechanical relay with no digital interface.

**Evidence basis:** BELIEF — the spec assumes it's possible but provides no mechanism.

**What if wrong:** The core value proposition of the system fails. Bypass detection requires an alternative approach: possibly inferring relay state from generator status + mains status + breaker state pattern analysis (if mains is down AND generator is running AND a non-essential breaker is closed, then the relay was bypassed). This is indirect inference, not direct register comparison, and is less reliable.

**Test design:**
- Test type: Expert consultation + hardware investigation
- Specific test: Ask Profection Switchboards explicitly: "Does the 48V relay load-shedding system have a digital/Modbus-readable status output? If yes, what register? If no, what signal is available (e.g., 48V DC presence on a monitored contact)?" This is already Question 4 in WM-KW-SCADA-REQ-001, but it must be tracked as the single highest-priority question.
- Owner: Arno
- Timeline: Must be answered within 2 weeks (before build clock starts)
- Success signal: Profection confirms a readable register or a contact that can be wired to a digital input on the Ekip Com
- Failure signal: The relay is a dumb electromechanical device with no readable state
- Decision if wrong: Redesign bypass detection to use inference logic (mains status + generator status + breaker state pattern). Document the reduced reliability. Consider adding a purpose-built relay state monitor (a simple DI module wired to the relay coil).

---

### Assumption #2: ABB Trip Units Expose Breaker State via Modbus Register

**Full statement:** The Tmax XT and Emax 2 trip units, when connected via Ekip Com gateway, expose the breaker open/closed/tripped state as a readable Modbus holding register at a known address.

**Category:** Technical
**Explicit or Implicit:** IMPLICIT — the spec assumes Modbus polling returns breaker state, but the specific register address is marked as TODO and no register dump exists.

**Criticality:** CRITICAL — Without readable breaker state, the system cannot monitor any breaker, cannot detect trips, cannot detect bypasses. The entire monitoring function fails.

**Confidence:** LOW — ABB documentation confirms Ekip Com supports Modbus TCP and exposes trip unit data. But the exact register map for this firmware version and configuration has not been obtained. Register addresses can vary by firmware version, trip unit model, and Ekip Com configuration.

**Evidence basis:** ESTIMATED — Based on ABB datasheets and general Ekip Com documentation. Not validated against the specific hardware being installed.

**What if wrong:** If breaker state is not readable via Modbus at all (extremely unlikely given ABB's architecture), the project fails. More realistically, the risk is that the register addresses are different from what we assume, requiring reconfiguration during commissioning. This is a schedule risk, not a feasibility risk.

**Test design:**
- Test type: Bench test with real hardware
- Specific test: Obtain an Ekip Com + Tmax XT trip unit from Profection (requested in WM-KW-SCADA-REQ-001, Priority 1). Connect via Modbus TCP. Read all holding registers. Map breaker state register address. Verify open/closed/tripped values.
- Owner: Arno (hardware), Claude (software integration)
- Timeline: Must have hardware within 4 weeks
- Success signal: Breaker state readable at a confirmed register address with documented values
- Failure signal: Ekip Com firmware does not expose breaker state, or requires specific configuration that Profection hasn't applied
- Decision if wrong: Escalate to ABB technical support. If register is available but at a non-standard address, update the register map. If fundamentally unavailable, evaluate IEC 61850 as the primary protocol (which does expose XCBR status natively).

---

### Assumption #4: Profection Delivers Register Maps + Bench Hardware On Time

**Full statement:** Profection Switchboards will respond to WM-KW-SCADA-IF-001 and WM-KW-SCADA-REQ-001 within a reasonable timeframe, provide Modbus register maps, supply bench test hardware, and answer the 48V relay question — all before the integration testing window (Weeks 13–14).

**Category:** Dependency
**Explicit or Implicit:** EXPLICIT — Pre-mortem FM#1 identified this as the highest-likelihood failure mode.

**Criticality:** CRITICAL — Without register maps, the edge gateway cannot be built against real data structures. Without bench hardware, integration testing is impossible. Without the 48V relay answer (Assumption #3), bypass detection cannot be designed.

**Confidence:** LOW — The documents have been sent but no response received. Profection's priorities are hardware delivery and PLC programming. Software interface documentation is historically deprioritised by DB manufacturers.

**Evidence basis:** ASSUMED — Based on the formal request being sent. No commitment from Profection yet.

**What if wrong:** Development proceeds against assumed register maps (from ABB generic documentation). Integration testing is delayed or compressed. Worst case: the real register layout differs significantly, requiring 2–4 weeks of rework during commissioning.

**Test design:**
- Test type: Relationship management + contractual follow-up
- Specific test: Arno follows up with Profection within 1 week of sending the documents. Establish a bi-weekly check-in. Get written commitment on register map delivery date and bench hardware availability.
- Owner: Arno
- Timeline: Response within 2 weeks; hardware within 6 weeks
- Success signal: Written confirmation with dates
- Failure signal: No response after 2 weeks, or verbal "we'll get to it" without dates
- Decision if wrong: Escalate to the client (property owner) to apply commercial pressure. In parallel, develop the edge gateway against ABB's generic register documentation with explicit TODO markers for all register addresses. Budget 2 extra weeks at the end for integration rework.

---

### Assumption #24: Edge Gateway Hardware Is Specified and Ordered

**Full statement:** A physical device exists (or will be procured) to run the edge gateway — a Python process doing per-VLAN async Modbus polling, SQLite local buffering, WireGuard VPN, and systemd supervision — and this device has sufficient CPU, RAM, and network interfaces.

**Category:** Resource
**Explicit or Implicit:** IMPLICIT — The pre-mortem flagged this (FM#5), but no hardware spec, procurement plan, or budget exists. The spec says "on-site device running Python Modbus poller" without naming the device.

**Criticality:** CRITICAL — Without the edge gateway, there is no telemetry. The hardware needs to be physically present, configured, and connected to the SCADA VLANs.

**Confidence:** LOW — No hardware has been specified, quoted, ordered, or budgeted. Lead times for industrial-grade edge computers can be 4–8 weeks.

**Evidence basis:** BELIEF — it's assumed "a device" will be available.

**What if wrong:** At Week 13, there is no physical device to run the software. The edge gateway code exists but cannot be deployed. The entire system is disconnected from the field.

**Test design:**
- Test type: Procurement planning
- Specific test: Specify the edge gateway hardware this week. Options: (a) Industrial PC (e.g., Advantech UNO-2000, ~R15,000–R25,000), (b) Raspberry Pi 5 8GB in DIN-rail enclosure (~R3,500, acceptable for monitoring-only), (c) Existing server in the switchroom if one is being installed by Profection. Determine: who procures it? Who is responsible for OS install and network configuration?
- Owner: Arno
- Timeline: Specify by Week 1 of build. Order by Week 2. Receive by Week 6.
- Success signal: Hardware ordered with confirmed delivery date within 6 weeks
- Failure signal: No budget allocated, or "Profection will handle it" without confirmation
- Decision if wrong: Use a temporary laptop as the edge gateway for commissioning testing. This is a stopgap, not a solution — it must be replaced before handover.

---

### Assumption #10: Internet Connectivity at Kingswalk Mall

**Full statement:** The Kingswalk mall site has (or will have by commissioning) a reliable internet connection with sufficient bandwidth for the SCADA edge gateway to maintain a WireGuard VPN tunnel to the cloud and transfer ~2–5 GB/month of telemetry data.

**Category:** Infrastructure
**Explicit or Implicit:** IMPLICIT — The entire cloud architecture depends on internet connectivity. The spec mentions VPN and a 4G failover, but the primary connection is never specified.

**Criticality:** CRITICAL — Without internet, the edge gateway cannot reach the cloud. The monitoring system is offline. The 4G failover is designed for temporary outages, not as a primary connection.

**Confidence:** LOW — The site is under construction. It's unknown whether fibre has been provisioned, who the ISP is, what the expected uptime is, or when it will be available.

**Evidence basis:** BELIEF — assumed because "it's a shopping centre, it will have internet." But construction sites often have internet as one of the last services connected.

**What if wrong:** The SCADA system cannot go live even if the software and hardware are ready. The edge gateway operates in permanent "local buffer" mode with no cloud connectivity. Operators must physically visit the site to view data.

**Test design:**
- Test type: Infrastructure verification
- Specific test: Ask the client / project manager: "What is the ISP? When is fibre expected? Is there a dedicated connection for SCADA, or will it share the mall's general internet? What is the expected bandwidth and SLA?"
- Owner: Arno
- Timeline: Answer needed within 2 weeks
- Success signal: Confirmed ISP, fibre installation date before Week 12, dedicated or VLAN-segregated connection for SCADA
- Failure signal: "We haven't thought about it yet" or fibre installation scheduled after go-live
- Decision if wrong: Budget for a dedicated 4G/LTE router as the primary connection (not just failover). ~R500/month for a 50GB data SIM. This works but adds latency and reduces reliability.

---

### Assumption #13: Claude/AI Generates Production-Quality Code

**Full statement:** An AI coding agent (Claude), working from SPEC.md, BUILD_STRATEGY.md, and the skill library, can generate a complete, production-ready SCADA monitoring system including FastAPI backend, React frontend, edge gateway, database migrations, CI/CD pipeline, and all tests — with sufficient quality that Arno's review is a domain validation step, not a code rewrite.

**Category:** Resource
**Explicit or Implicit:** IMPLICIT — the entire delivery model assumes this. BUILD_STRATEGY §1.1 says "everything other than SPEC.md is generated by Claude." But no proof-of-concept code exists.

**Criticality:** CRITICAL — If AI code generation produces code that requires significant manual rework, the 14-week timeline is impossible. There is no backup developer.

**Confidence:** MODERATE — Claude has demonstrated strong code generation in this session (docx generation, schema design, architectural reasoning). But generating a complete, tested, deployed SCADA system is a different order of magnitude. The spec is detailed enough to guide generation, but edge cases, integration bugs, and deployment issues are inherently unpredictable.

**Evidence basis:** ESTIMATED — based on Claude's known capabilities and the quality of the spec documents. Not validated against a comparable project.

**What if wrong:** Timeline slips. Arno must either write code himself (not his role), hire a developer (budget and time impact), or reduce R1 scope.

**Test design:**
- Test type: Proof-of-concept sprint
- Specific test: Before starting the full 14-week build, run a 3-day spike: have Claude generate Phase 1 (foundation + auth skeleton). Evaluate: does the code compile? Do tests pass? Is the architecture clean? Is Arno's review burden manageable? This spike validates the delivery model before committing 14 weeks to it.
- Owner: Arno + Claude
- Timeline: Week 0 (before the build clock starts)
- Success signal: Working auth system with CI/CD pipeline, deployed to Vercel preview, within 3 days. Arno's review takes <2 hours.
- Failure signal: Code requires significant manual fixes. Tests don't pass. Architecture doesn't match spec.
- Decision if wrong: Hire a contract developer to work alongside Claude. Claude generates first-pass code, developer reviews and fixes. Budget: R80,000–R120,000 for a 14-week part-time senior Python/React developer.

---

### Assumption #12: 14 Weeks Is Achievable for R1 MVP

**Full statement:** The R1 scope (live breaker state monitoring, alarm notifications including bypass detection, continuous PQ data logging) can be built, tested, and deployed within 14 weeks.

**Category:** Timing
**Explicit or Implicit:** EXPLICIT — SPEC D.1 states this as a hard deadline.

**Criticality:** CRITICAL — This is a contractual/commercial commitment. Missing it has direct business consequences.

**Confidence:** MODERATE — The spec is very detailed, the build phases are well-planned, and the scope has been deliberately limited (monitoring only, no control). But: no comparable project exists as a baseline, the delivery model is novel (AI-generated code), and dependencies on Profection and internet connectivity introduce external risk.

**Evidence basis:** ESTIMATED — based on phase-by-phase time allocation in BUILD_STRATEGY v3. No empirical data.

**What if wrong:** Options: (a) reduce R1 scope (drop PQ logging, keep only breaker state + alarms), (b) extend deadline, (c) add resources (hire developer per Assumption #13).

**Test design:**
- Test type: Milestone tracking
- Specific test: Establish weekly milestone checkpoints against the BUILD_STRATEGY phases. If Phase 1 (Weeks 1–3) takes more than 4 weeks, the timeline is at risk and scope reduction decisions must be made immediately.
- Owner: Arno
- Timeline: Continuous from Week 1
- Success signal: Each phase completes within its allocated window ±1 week
- Failure signal: Any phase takes >150% of allocated time
- Decision if wrong: At Week 6, if behind schedule: drop PQ logging from R1 (move to R2), focus exclusively on breaker state + bypass detection + alarms. This is the minimum viable monitoring system.

---

## IMPORTANT ASSUMPTIONS — SUMMARY

| # | Assumption | If Wrong | Minimum Viable Test | Owner | Timeline |
|---|------------|---------|---------------------|-------|---------|
| 6 | pymodbus stable for 24/7 production | Edge gateway crashes intermittently; monitoring gaps | Run pymodbus stress test: 9 concurrent async clients, 450 reads/sec, 72 hours continuous | Claude | Week 4–5 |
| 7 | 250ms polling achievable per-VLAN | Bypass detection latency >1s; stale states | Benchmark with simulator: 9 VLANs × 17 devices, measure actual loop time | Claude | Week 4 |
| 8 | Mock Modbus data representative | Integration testing reveals unexpected device behavior | Compare mock register structure against ABB datasheet register table; validate with bench unit | Arno | Week 6 |
| 14 | Arno not a bottleneck | Reviews queue up; phases stall waiting for approval | Agree upfront: Arno reviews within 48 hours or Claude proceeds with best judgment | Arno | Week 0 |
| 20 | Essential/non-essential classification data exists | Cannot populate essential_supply column; bypass detection has no target set | Ask Profection or client: "Which breakers are on essential supply? Which distribution boards are on generator Bank A vs B?" | Arno | Week 2 |
| 22 | IEC 61850 + Modbus coexist | TS2 anchor feeders can't be monitored simultaneously with Modbus devices | Test with bench hardware if available; otherwise defer IEC 61850 to R2 | Arno | Week 8 |
| 23 | M4M 30 readings → pq_sample mapping | Wrong columns populated; PQ data is garbage | Obtain M4M 30 register dump from Profection; map each register to schema column | Arno + Claude | Week 6 |
| 11 | WireGuard works through mall network | VPN cannot establish; edge gateway offline | Test WireGuard on a comparable network (behind NAT, commercial firewall); confirm UDP 51820 is passable | Claude | Week 8 |
| 5 | First MB on network for integration testing | No real-device testing before go-live; commissioning is first integration attempt | Get commissioning schedule from Profection; negotiate early access to one MB | Arno | Week 4 |

---

## ASSUMPTION DEPENDENCY MAP

**Foundational assumptions (others depend on these):**

- **Assumption #10 (Internet connectivity)** → #9 (VPN latency), #11 (WireGuard works), #30 (4G coverage), and the entire cloud architecture. If there is no internet, assumptions 9, 11, 12, and 30 are all irrelevant.

- **Assumption #4 (Profection delivers)** → #2 (register maps), #3 (48V relay answer), #5 (first MB on network), #8 (mock data fidelity), #20 (essential supply classification), #23 (M4M 30 mapping), #28 (VLAN plan implemented). Profection is the single largest external dependency.

- **Assumption #13 (AI code generation works)** → #12 (14-week timeline). If AI code quality is insufficient, the timeline assumption falls automatically.

**Cascade chains:**

1. If **#4** (Profection) is wrong → **#2** (register maps) unknown → **#1** (bypass detection) can't be verified → **#3** (relay state) still unknown → the business case is unproven at go-live.

2. If **#10** (internet) is wrong → **#9** (latency) is moot → cloud architecture doesn't work → **#12** (14-week timeline) fails because the architecture needs redesign for on-premise deployment.

3. If **#13** (AI code quality) is wrong → **#12** (14 weeks) fails → scope must be cut → **#1** (bypass detection) may be deferred, defeating the purpose.

---

## HIDDEN ASSUMPTIONS REQUIRING IMMEDIATE ATTENTION

1. **#3 — 48V relay command state is readable:** This is the most dangerous assumption in the entire project. The bypass detection logic requires TWO inputs: actual breaker state (readable via Modbus, likely) and expected relay command (source unknown). If the relay is a simple electromechanical device with no digital output, the entire bypass detection feature needs a fundamentally different design. This question is in the Profection request letter, but it has not been flagged as existential. **It is existential.**

2. **#24 — Edge gateway hardware not specified:** There is no procurement plan for the physical device that runs the edge gateway software. Every technical decision about the edge gateway (systemd, per-VLAN polling, local buffer, WireGuard) assumes a device exists. Nobody has asked: "What device? Who buys it? When does it arrive? Does it have enough network interfaces for 9 VLANs?"

3. **#10 — Internet connectivity at a construction site:** The cloud architecture was chosen for good reasons (no on-site server maintenance, easy remote access). But it creates an absolute dependency on internet connectivity at a site that is still under construction. If fibre is not installed by commissioning week, the system cannot function regardless of how good the software is.

4. **#20 — Essential supply classification data:** The bypass detection alarm targets breakers marked `essential_supply=true`. But who provides this data? The SLD drawings show the electrical topology but don't label breakers as essential vs non-essential. The generator bank assignment (A vs B) per distribution board is also unconfirmed. Without this data, the system knows something is happening but can't identify bypasses specifically.

---

## ASSUMPTION TESTING ROADMAP

### Sprint 0 — Before Build Clock Starts (This Week)

- [ ] **#3** — Ask Profection: "How does the SCADA system read the 48V relay command state?" — **Owner: Arno** — Due: 2026-04-18
- [ ] **#4** — Follow up with Profection on interface spec response; get written commitment on register map delivery date — **Owner: Arno** — Due: 2026-04-18
- [ ] **#24** — Specify edge gateway hardware; get quote; place order — **Owner: Arno** — Due: 2026-04-18
- [ ] **#10** — Confirm ISP and fibre installation date at Kingswalk — **Owner: Arno** — Due: 2026-04-18
- [ ] **#14** — Agree on review SLA (48-hour turnaround) with Arno — **Owner: Arno** — Due: 2026-04-14
- [ ] **#13** — Run 3-day proof-of-concept spike (Phase 1 skeleton) to validate AI delivery model — **Owner: Claude + Arno** — Due: 2026-04-18

### Sprint 1 — Weeks 1–3 of Build

- [ ] **#12** — Track Phase 1 milestone completion against 3-week target — **Owner: Arno**
- [ ] **#20** — Obtain essential supply / generator bank classification from Profection or design drawings — **Owner: Arno** — Due: 2026-05-01
- [ ] **#5** — Get commissioning schedule from Profection; identify earliest MB network availability — **Owner: Arno** — Due: 2026-05-01

### Sprint 2 — Weeks 4–8 of Build

- [ ] **#2** — Validate breaker state register address against bench hardware — **Owner: Arno** — Due: 2026-05-22
- [ ] **#6** — Run pymodbus 72-hour stress test (9 concurrent clients, 450 reads/sec) — **Owner: Claude** — Due: 2026-05-15
- [ ] **#7** — Benchmark per-VLAN polling loop time against 250ms target — **Owner: Claude** — Due: 2026-05-08
- [ ] **#8** — Compare mock register layout against real ABB device (from bench unit) — **Owner: Arno + Claude** — Due: 2026-05-22
- [ ] **#23** — Map M4M 30 registers to pq_sample columns against real register dump — **Owner: Arno + Claude** — Due: 2026-05-22
- [ ] **#11** — Test WireGuard on comparable NAT/firewall setup — **Owner: Claude** — Due: 2026-05-29

### Sprint 3 — Weeks 9–14 of Build

- [ ] **#1** — End-to-end bypass detection test against simulated (or real) scenario — **Owner: Arno + Claude** — Due: 2026-06-26
- [ ] **#22** — Test IEC 61850 + Modbus coexistence on TS2 feeders (if bench hardware available) — **Owner: Arno** — Due: 2026-06-19
- [ ] **#30** — Verify 4G coverage at Kingswalk site — **Owner: Arno** — Due: 2026-06-12

### Accept Without Testing

- **#16** (28 users): Hard-counted from stakeholder interview. Negligible impact if slightly off.
- **#18** (104 breakers): Extracted from 10 verified SLD drawings. High confidence.
- **#19** (PG + TimescaleDB performance): Architecture review confirmed comfortable headroom. Monitor in production.
- **#27** (Redis pub/sub latency): Well within published Redis benchmarks for this scale.
- **#17** (cloud cost R4–5.5K/month): Reasonable estimate; monitor actual spend in production.

---

## ASSUMPTION LOG (LIVING DOCUMENT)

| # | Assumption | Category | Criticality | Initial Confidence | Current Confidence | Evidence Update | Date Updated | Owner |
|---|------------|----------|-------------|-------------------|-------------------|-----------------|-------------|-------|
| 1 | Bypass detection via register comparison | Technical | CRITICAL | MODERATE | MODERATE | Design documented in SPEC C.6.1; not tested | 2026-04-11 | Arno |
| 2 | Trip units expose state via Modbus | Technical | CRITICAL | LOW | LOW | Bench hardware requested; no response | 2026-04-11 | Arno |
| 3 | 48V relay state is readable | Technical | CRITICAL | UNKNOWN | UNKNOWN | Question sent to Profection; awaiting answer | 2026-04-11 | Arno |
| 4 | Profection delivers on time | Dependency | CRITICAL | LOW | LOW | Documents sent; no response | 2026-04-11 | Arno |
| 5 | First MB on network for testing | Dependency | CRITICAL | LOW | LOW | No commissioning schedule received | 2026-04-11 | Arno |
| 6 | pymodbus stable 24/7 | Technical | IMPORTANT | MODERATE | MODERATE | No stress test run | 2026-04-11 | Claude |
| 7 | 250ms polling achievable | Technical | IMPORTANT | MODERATE | MODERATE | Designed but not benchmarked | 2026-04-11 | Claude |
| 8 | Mock data representative | Technical | IMPORTANT | LOW | LOW | No real device comparison | 2026-04-11 | Arno |
| 9 | <20ms VPN latency SA cloud | Infrastructure | SUPPORTING | MODERATE | MODERATE | Not measured | 2026-04-11 | Claude |
| 10 | Internet at Kingswalk | Infrastructure | CRITICAL | LOW | LOW | Not confirmed | 2026-04-11 | Arno |
| 11 | WireGuard through mall network | Infrastructure | IMPORTANT | LOW | LOW | Not tested | 2026-04-11 | Claude |
| 12 | 14 weeks achievable | Timing | CRITICAL | MODERATE | MODERATE | No baseline; well-planned phases | 2026-04-11 | Arno |
| 13 | AI code generation sufficient | Resource | CRITICAL | MODERATE | MODERATE | Strong spec work; no code yet | 2026-04-11 | Arno |
| 14 | Arno not a bottleneck | Resource | IMPORTANT | LOW | LOW | Single domain expert; pre-mortem flagged | 2026-04-11 | Arno |
| 20 | Essential supply data exists | Technical | IMPORTANT | LOW | LOW | Schema ready; no data source confirmed | 2026-04-11 | Arno |
| 22 | IEC 61850 + Modbus coexist | Technical | IMPORTANT | MODERATE | MODERATE | Dual-stack designed; not tested | 2026-04-11 | Arno |
| 23 | M4M 30 register → schema mapping | Technical | IMPORTANT | MODERATE | MODERATE | Designed from datasheets; not verified | 2026-04-11 | Arno |
| 24 | Edge gateway hardware specified | Resource | CRITICAL | LOW | LOW | Not specified or ordered | 2026-04-11 | Arno |
| 28 | VLAN plan implemented as specified | Infrastructure | IMPORTANT | MODERATE | MODERATE | Plan delivered; implementation is Profection's scope | 2026-04-11 | Arno |
| 30 | 4G coverage at site | Infrastructure | SUPPORTING | LOW | LOW | Not verified | 2026-04-11 | Arno |

**Review cadence:** Update at each build phase milestone (Weeks 3, 8, 12, 14) and whenever Profection responds to any request.

---

## ASSUMPTION MAP SUMMARY

**Total assumptions identified:** 30
**Critical + Low confidence / Unknown (must test immediately):** 5 (#3, #4, #5, #10, #24)
**Critical + Moderate confidence (test urgently):** 3 (#1, #12, #13)
**The single most dangerous assumption in this plan:** **#3 — 48V relay command state is readable.** If it isn't, the core business case (bypass detection) needs a fundamentally different approach. This question has been sent to Profection but has not been flagged as existential-priority by anyone yet.
**The assumption most likely to be wrong that hasn't been tested:** **#24 — Edge gateway hardware exists.** Nobody has specified, budgeted, or ordered it. It's the kind of thing that falls through the cracks because it's "someone else's job" — but it's not clear whose job it is.
**Overall assumption risk level:** HIGH

**Assessment:** This project has a well-designed spec and thorough pre-build analysis, but it rests on a foundation of untested critical assumptions — most of which depend on a single external party (Profection Switchboards) that has not yet responded. The 5 CRITICAL + LOW confidence assumptions (#3, #4, #5, #10, #24) are all answerable within 2 weeks with phone calls and emails — none require building anything. The highest-leverage action before writing a single line of code is to get answers to these 5 questions. If all 5 come back positive, the project is well-positioned. If #3 (relay state) comes back negative, a fundamental design change is needed before the build starts. Sprint 0 — the week before the build clock starts — is the most important week of the entire project.
