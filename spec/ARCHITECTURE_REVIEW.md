# Architecture Review: Kingswalk SCADA GUI

**Reviewed:** 2026-04-11
**Source:** SPEC.md v3.0, DB_SCHEMA.md, BUILD_STRATEGY.md
**Reviewer:** Claude (architecture-review skill)

## Assumptions

- **Scale target:** 28 concurrent users (5 admin + 3 operator + 20 viewer), ~150 Modbus devices, 104 breakers, 9 main boards
- **Team:** 1 domain expert (Arno, part-time) + AI code generation. No dedicated DevOps or DBA
- **Budget:** Not formally defined. Assumed modest — cloud hosting should stay under R10,000/month
- **Traffic pattern:** Low user concurrency but high telemetry throughput. Breaker state at 250ms polling × 104 breakers = ~416 state reads/second. M4M 30 at 1s × 18 analysers = 18 PQ reads/second. Total: ~450 device reads/second sustained, 24/7/365
- **Data volume:** PQ samples at 1s × 18 devices × 86,400 seconds/day = ~1.55M rows/day in `telemetry.pq_sample`. Breaker state at 250ms × 104 = ~35.9M state reads/day (logged on change only, estimated ~5,000–50,000 state change rows/day depending on activity)
- **Deployment:** Cloud-hosted (provider TBD) with on-site edge gateway connected via VPN
- **This is a monitoring-only system — no control commands to field devices**

## Architecture Summary

The system is a three-tier SCADA monitoring application: an on-site Python edge gateway polls ~150 ABB field devices via Modbus TCP across 9 VLANs, pushes telemetry through a VPN tunnel to a cloud-hosted FastAPI backend, which stores data in PostgreSQL 16 + TimescaleDB 2.x and publishes state changes to connected browsers via Redis 7 pub/sub and WebSocket. A React 19 SPA on Vercel renders live dashboards, floor plan/SLD canvases, and historical PQ trends. Authentication uses argon2id + TOTP MFA with JWT tokens.

---

## Critical Findings

### TIER 1 — Fix Before Launch

#### 1.1 Edge Gateway Is a Single Point of Failure with No Watchdog

**Component:** Edge gateway (on-site Python process)
**Problem:** The edge gateway is the sole bridge between ~150 field devices and the cloud. If the Python process crashes, hangs, or the host OS reboots, all telemetry stops flowing. The spec mentions a "local buffer for connectivity loss" (VPN outage), but there is no mention of process supervision, automatic restart, health monitoring, or a secondary gateway.
**Failure Condition:** Any edge gateway process crash, unhandled exception in pymodbus, OOM on a constrained edge device, or OS-level reboot without auto-start configured.
**Impact:** Total monitoring blindspot. No breaker states, no PQ data, no bypass detection. Operators see "COMMS LOSS" on every asset. The system's primary purpose — detecting relay bypass during mains failure — is defeated at exactly the moment it's needed most.
**Recommendation:**
1. Run the edge gateway under `systemd` with `Restart=always` and `WatchdogSec=30`. The poller must send a periodic heartbeat via `sd_notify`.
2. Add a `/health` endpoint on the edge gateway (HTTP on localhost) that reports: last successful poll timestamp per MB, VPN tunnel status, local buffer depth.
3. The cloud backend must monitor edge gateway health — if no telemetry arrives for >30 seconds, raise a CRITICAL alarm ("Edge gateway unresponsive — all monitoring offline").
4. For R2 or R3: consider a hot-standby edge gateway (second device, passive until primary fails) for the 99.9% uptime target. For R1, the systemd watchdog is sufficient.
**Effort:** Small (1 day for systemd + health endpoint + cloud-side watchdog alarm)

#### 1.2 VPN Tunnel Has No Defined Failover or Keepalive

**Component:** Site-to-cloud VPN/WireGuard tunnel
**Problem:** The architecture shows a single VPN tunnel between the edge gateway and the cloud. VPN tunnels drop — ISP outages, router reboots, NAT traversal failures. There is no mention of keepalive, automatic reconnection, failover to a secondary ISP, or alerting on tunnel state.
**Failure Condition:** ISP outage, router reboot, NAT table expiry, WireGuard key rotation, or cloud-side VPN endpoint restart.
**Impact:** Same as 1.1 — total monitoring blindspot. The local buffer mitigates data loss (telemetry is queued for sync), but real-time monitoring and alarm generation are unavailable for the duration of the outage.
**Recommendation:**
1. Use WireGuard with `PersistentKeepalive=25` to prevent NAT traversal failures.
2. Implement a dual-path failover: primary fibre + secondary 4G/LTE dongle on the edge gateway. If the primary path drops for >60 seconds, the edge gateway switches to the secondary.
3. The edge gateway must log tunnel state transitions and push them as events when connectivity resumes.
4. Budget for a 4G SIM with ~10GB/month as backup — telemetry volume at ~450 reads/second with compact payloads is roughly 2–5 GB/month.
**Effort:** Medium (2–3 days for WireGuard config + dual-path failover logic + monitoring)

#### 1.3 No Connection Pooling Strategy Defined for PostgreSQL

**Component:** FastAPI backend → PostgreSQL
**Problem:** The spec names SQLAlchemy 2.0 async but doesn't define connection pool parameters. With the edge gateway pushing ~450 inserts/second for telemetry plus API reads from 28 users, connection pool exhaustion is a real risk. Managed PostgreSQL instances typically have a connection limit of 100–500 depending on plan. Without PgBouncer or explicit pool sizing, peak telemetry write bursts can starve API read connections.
**Failure Condition:** Edge gateway reconnects after a VPN outage and flushes its local buffer (potentially thousands of queued rows) while users are actively querying dashboards. All connections are consumed by bulk inserts.
**Impact:** API timeouts for dashboard users. WebSocket connections may drop. Users see stale data or "connection error" states.
**Recommendation:**
1. Deploy PgBouncer in transaction mode between the FastAPI backend and PostgreSQL. Set pool size to 20 for the API process and 10 for the edge gateway writer, with a maximum of 50 total connections to PostgreSQL.
2. Separate the write path (edge gateway → PG) from the read path (API → PG) using distinct PgBouncer pools with priority. API reads should never be starved by bulk telemetry writes.
3. For the edge gateway buffer flush: implement rate-limited batch inserts (e.g., 500 rows per batch, 100ms delay between batches) to prevent connection stampede after reconnection.
4. In SQLAlchemy, configure: `pool_size=15, max_overflow=5, pool_timeout=10, pool_recycle=3600`.
**Effort:** Medium (2 days for PgBouncer setup + pool configuration + buffer flush rate limiting)

#### 1.4 Edge Gateway Polling Architecture — Single-Threaded Risk

**Component:** Edge gateway Modbus poller (pymodbus)
**Problem:** Polling 104 breakers at 250ms and 18 M4M 30s at 1s across 9 separate VLANs is a tight timing budget. If the poller is single-threaded and sequential (poll MB 1.1, then MB 2.1, etc.), a single slow or unresponsive device on one VLAN blocks the entire polling loop. With 9 VLANs × ~17 devices average = ~150 sequential Modbus reads, each with a 200ms timeout, worst-case single-loop time is 30 seconds — far exceeding the 250ms target.
**Failure Condition:** Any single Modbus device is slow to respond (degraded firmware, network congestion, device reboot). The polling loop stalls, breaker state updates for all other boards are delayed.
**Impact:** Bypass detection latency degrades from <1 second to potentially 30+ seconds. A bypass event during a generator failover could go undetected for half a minute.
**Recommendation:**
1. Implement per-VLAN polling threads (or asyncio tasks). Each of the 9 VLANs runs its own independent polling loop. A stalled device on MB 2.1 does not affect polling on MB 5.3.
2. Use `asyncio` with `pymodbus.client.AsyncModbusTcpClient` — one client per VLAN, running concurrently.
3. Set Modbus TCP socket timeout to 500ms per request. After 3 consecutive timeouts, mark the device as "COMMS LOSS" and skip to the next device — do not block the loop.
4. Implement a polling scheduler that prioritises breaker state (250ms) over PQ (1s) over energy (30s) per VLAN.
**Effort:** Medium (3–4 days for async per-VLAN architecture + timeout handling + priority scheduling)

---

### TIER 2 — Fix Before Growth

#### 2.1 TimescaleDB Continuous Aggregate Materialisation Lag

**Component:** `telemetry.pq_sample` → continuous aggregates (pq_1min, pq_15min, pq_hourly, pq_daily)
**Problem:** TimescaleDB continuous aggregates are materialised on a schedule (default: on each chunk close, or via `timescaledb.refresh_lag`). During a VPN outage + buffer flush, thousands of back-dated rows are inserted into a chunk that may have already been materialised. The continuous aggregates won't update unless refresh is explicitly triggered for that time range.
**Failure Condition:** Edge gateway reconnects after a 2-hour VPN outage, flushes 2 hours of buffered PQ samples. The 1-minute and 15-minute aggregates for that period are never materialised because the chunk refresh window has passed.
**Impact:** Historical PQ charts show gaps in aggregated views even though raw data exists. Forensic analysis using the aggregate views misses the outage recovery period.
**Recommendation:**
1. After every buffer flush, the edge gateway must send a "flush_completed" event to the backend, including the time range of the flushed data.
2. The backend must then explicitly call `CALL refresh_continuous_aggregate('telemetry.pq_1min', start, end)` for the affected time range.
3. Set `timescaledb.materialized_only = false` on aggregate views used by the API, so they fall through to raw data when aggregates are stale.
**Effort:** Small (1 day)

#### 2.2 WebSocket Reconnection Storm After Backend Restart

**Component:** React SPA ↔ FastAPI WebSocket
**Problem:** All 28 users maintain persistent WebSocket connections. If the FastAPI backend restarts (deployment, crash, OOM), all connections drop simultaneously. Every browser client immediately attempts to reconnect. With exponential backoff absent, 28 clients hit the WebSocket endpoint within 1–2 seconds.
**Failure Condition:** Backend deployment or crash while users are connected.
**Impact:** For 28 users this is manageable, but without jitter the reconnection burst adds unnecessary load during the most vulnerable moment (post-restart). More importantly, Zustand state stores on the client side may hold stale data from before the restart. If the client doesn't request a full state snapshot on reconnection, it displays outdated breaker states.
**Recommendation:**
1. Implement reconnection with exponential backoff + jitter: initial delay 1s, max delay 30s, jitter ±50%.
2. On WebSocket reconnection, the client must send a `sync_request` message. The backend responds with a full state snapshot (all 104 breaker states, active alarms). The client replaces its Zustand store, not merges — a clean reset prevents stale state.
3. Display a "Reconnecting..." banner in the UI during the backoff period so operators know the system is recovering, not silently stale.
**Effort:** Small (1 day for client-side reconnection logic + sync protocol)

#### 2.3 Report Generation Blocks the API Worker

**Component:** FastAPI report generation engine
**Problem:** The spec mentions "on-demand reports: generated async (queued via Redis)" — good. But monthly automated reports querying 90 days of PQ data across 18 analysers could produce queries that run for 30–60 seconds, consuming a PostgreSQL connection and a FastAPI worker for the duration. If the FastAPI process has 4 workers and 2 are blocked by report queries, API throughput halves.
**Failure Condition:** Monthly report cron fires at midnight. Two reports start simultaneously. Two of four FastAPI workers are blocked for 60 seconds each.
**Impact:** Dashboard API responses slow to 2–5 seconds. WebSocket broadcast latency increases. Not catastrophic for 28 users, but degrades the monitoring experience.
**Recommendation:**
1. Run report generation in a separate worker process (not the API process). Use a Redis queue (e.g., `arq` or `rq`) with a dedicated worker pool. The API process only enqueues the job and returns a ticket.
2. Report queries should target the continuous aggregates (pq_15min, pq_daily), not raw pq_sample. This reduces query time from minutes to seconds.
3. Set `statement_timeout = 120s` on the report worker's database connection to prevent runaway queries.
**Effort:** Medium (2 days for worker separation + queue integration)

#### 2.4 No Telemetry Data Deduplication After Buffer Flush

**Component:** Edge gateway → PostgreSQL telemetry tables
**Problem:** The local buffer stores telemetry during VPN outages. When connectivity resumes, the buffer is flushed. But what if the VPN drops mid-flush? The edge gateway doesn't know which rows were successfully committed. On the next reconnection, it re-sends the entire buffer, producing duplicate rows in the hypertables.
**Failure Condition:** VPN drops during buffer flush, reconnects, re-flushes.
**Impact:** Duplicate PQ samples inflate energy calculations, distort aggregate views, and waste storage.
**Recommendation:**
1. The primary key on `telemetry.pq_sample` is `(device_id, ts)`. Use `INSERT ... ON CONFLICT (device_id, ts) DO NOTHING` for all telemetry writes. This makes re-flush idempotent at zero extra cost.
2. Apply the same pattern to `telemetry.breaker_state`, `telemetry.energy_register`, and `telemetry.lighting_state`.
3. The edge gateway should track the last confirmed flush offset (acknowledged by the cloud), so partial re-sends only re-transmit the unacknowledged tail.
**Effort:** Small (0.5 days for upsert pattern + offset tracking)

#### 2.5 No Read Replica for Dashboard Queries

**Component:** PostgreSQL
**Problem:** A single PostgreSQL instance handles both telemetry writes (~450 inserts/second sustained) and dashboard reads (28 users querying live state, historical trends, asset info). Write-heavy hypertable inserts create WAL pressure that can slow read queries, particularly the PQ trend charts that scan large time ranges.
**Failure Condition:** 28 users simultaneously load PQ trend charts (each querying pq_15min over 30 days for a specific device) while telemetry writes continue. I/O contention on the single instance.
**Impact:** Dashboard queries slow from <100ms to 500ms–2s. Not an outage, but degrades the real-time feel.
**Recommendation:**
1. For R1 with 28 users, this is likely tolerable. Monitor `pg_stat_statements` for queries exceeding 200ms.
2. For R2: add a read replica. Route all dashboard read queries to the replica. Telemetry writes go to the primary only. This eliminates read/write contention.
3. Ensure TimescaleDB continuous aggregates are created on the replica (or use logical replication that replicates the materialised views).
**Effort:** Medium (2 days for replica setup + query routing) — defer to R2.

---

### TIER 3 — Fix for Long-Term

#### 3.1 Monolithic Backend — Acceptable Now, Watch for Growth

**Component:** FastAPI backend
**Problem:** The FastAPI backend handles REST API, WebSocket connections, RBAC, report generation, and email/SMS dispatch all in one process. For 28 users and ~150 devices, this is fine. If Kingswalk is the first of multiple sites, this monolith will strain.
**Failure Condition:** Watson Mattheus rolls out to a second shopping centre. The backend now handles 300 devices and 56 users. The WebSocket connection count doubles, report generation queue depth doubles.
**Impact:** Deployment complexity increases. A bug in the report generator takes down the WebSocket connections.
**Recommendation:** No action for R1. If multi-site deployment is planned (R4+), extract the edge gateway communication layer, the WebSocket broadcast service, and the report generator into separate services. The REST API + auth remains the core service.
**Effort:** Large (2 weeks) — defer to multi-site expansion.

#### 3.2 No Structured Observability Stack Defined

**Component:** Cross-cutting
**Problem:** The spec mentions logging and monitoring-alert-system as a skill but doesn't define the observability stack. No mention of structured logging format, distributed tracing, metrics collection (Prometheus), or dashboards (Grafana).
**Failure Condition:** An intermittent Modbus polling failure on one device causes subtle data gaps. Without structured telemetry on the edge gateway itself, debugging requires SSH and log file grep.
**Impact:** Debugging takes hours instead of minutes. Intermittent issues go undetected until a forensic PQ analysis reveals missing data.
**Recommendation:**
1. Structured JSON logging on all components (edge gateway, FastAPI backend). Use Python `structlog`.
2. For R1: send structured logs to the cloud via the VPN tunnel. A simple solution: `loki` + `grafana` (lightweight, OSS, runs alongside the backend).
3. For R2: add Prometheus metrics export from the edge gateway (poll success rate per MB, average poll duration, buffer depth) and the backend (request latency, WebSocket connection count, active alarms).
**Effort:** Medium (3 days for structured logging + basic Grafana/Loki setup)

#### 3.3 Session Store in Redis — No Persistence Configuration

**Component:** Redis 7 (session store)
**Problem:** Redis is used for session storage (JWT refresh tokens). Default Redis configuration uses RDB snapshots (every 5 minutes). If Redis crashes between snapshots, all active sessions are lost — every user is force-logged-out.
**Failure Condition:** Redis OOM or process crash.
**Impact:** All 28 users must re-authenticate. Annoying for admins/viewers, disruptive for operators monitoring a live incident.
**Recommendation:** Enable Redis AOF (appendfsync=everysec) for session persistence. This adds <1ms write overhead and ensures sessions survive a Redis restart with at most 1 second of data loss.
**Effort:** Small (0.5 days — configuration change)

---

## Scalability Analysis

### What Breaks First

**The edge gateway polling loop.** At 150 devices across 9 VLANs with 250ms breaker state polling, a sequential polling architecture physically cannot meet the timing requirements. This is the first and most important thing to get right. A per-VLAN concurrent polling design (TIER 1, Finding 1.4) solves this. Everything else in the system has comfortable headroom at 28 users.

### Database Layer

**Write throughput:** ~450 device reads/second from the edge gateway, but only state *changes* are written to `telemetry.breaker_state` (estimated ~5K–50K rows/day). PQ samples at 1s × 18 M4M 30s = 18 inserts/second into the hypertable — well within PostgreSQL's capability. No write bottleneck at current scale.

**Read throughput:** 28 users querying dashboards. The heaviest query is PQ trend charts scanning `pq_15min` over 30 days for one device — approximately 2,880 rows. With a btree index on `(device_id, ts)`, this completes in <50ms. No read bottleneck at current scale.

**Index gaps identified:**
- `telemetry.pq_sample` needs `(device_id, ts)` — already the PK, good.
- `events.event` partial index on `(ts DESC, severity) WHERE acknowledged_at IS NULL` — specified, good.
- **Missing:** `events.event` needs an index on `(asset_id, ts DESC)` for the asset detail panel's event history query.
- **Missing:** `telemetry.breaker_state` needs an index on `(breaker_id, ts DESC)` for "last known state" lookups. Without this, every dashboard load scans the full hypertable.

**Connection pool:** See TIER 1, Finding 1.3. Must be configured explicitly.

**TimescaleDB retention:** Raw PQ data at 90 days, 15min aggregates at 5 years, daily indefinite — well-designed retention policy. Storage estimate: 1.55M rows/day × 90 days × ~200 bytes/row ≈ 28 GB for raw PQ. Comfortable for managed PostgreSQL.

### Application Layer

**FastAPI workers:** Default uvicorn with 4 workers can handle 28 concurrent users and ~18 API requests/second comfortably. The WebSocket connections (28 persistent) consume 28 file descriptors — trivial. No application-layer bottleneck at current scale.

**Memory:** The Zustand store on the client holds 104 breaker states + active alarms — perhaps 50KB of state. No memory concern on the client. The FastAPI backend holds no per-user state in memory (stateless with JWT) — correct design.

**GIL risk:** The edge gateway is I/O-bound (Modbus TCP reads, database writes). The GIL is not a concern for I/O-bound async Python. If report generation involves CPU-heavy Pandas aggregation, it should run in a separate process (see TIER 2, Finding 2.3).

### Network & Service Boundaries

**Latency chain:** Device → Modbus TCP (LAN, <5ms) → Edge gateway → VPN tunnel (~20–50ms to cloud) → PostgreSQL insert (~5ms) → Redis pub/sub (~1ms) → WebSocket push (~10ms) → Browser render (~50ms). **Total estimated: 90–120ms.** Well within the <1 second target.

**Risk:** VPN latency to a geographically distant cloud DC. If the cloud is hosted in Europe (e.g., Railway EU) and the site is in South Africa, VPN round trip could be 150–200ms. This pushes the total toward 250–300ms — still within budget, but with less margin.

**Recommendation:** Host the cloud infrastructure in a South African or nearby region (AWS Cape Town `af-south-1`, Azure South Africa North, or a local VPS provider). This keeps VPN latency to <20ms.

---

## Security Surface

| # | Risk | Severity | Component | Recommendation |
|---|------|----------|-----------|----------------|
| S1 | No rate limiting on login endpoint | HIGH | FastAPI auth | Add rate limiter: 5 attempts per IP per 15 minutes (spec mentions lockout but not IP-based rate limit). Use `slowapi` or custom middleware |
| S2 | Edge gateway → cloud connection authenticated only by VPN | MEDIUM | VPN tunnel | Add mutual TLS or API key authentication on the telemetry ingestion endpoint as defence-in-depth. VPN alone is a single layer |
| S3 | SMS/email credentials for BulkSMS and Resend | MEDIUM | Secrets | Use a secrets manager (AWS Secrets Manager, Doppler, or Infisical). Rotate API keys quarterly. Never in environment variables on the edge gateway |
| S4 | No CORS configuration specified | MEDIUM | FastAPI | Explicitly set CORS origins to the Vercel deployment domain only. Reject all others |
| S5 | RLS not specified for telemetry tables | LOW | PostgreSQL | Viewers should not be able to query raw telemetry for assets outside their assigned scope (if multi-tenant viewer access is planned). Add RLS policies on telemetry tables gated by user role |
| S6 | Audit log has no tamper protection | LOW | `core.audit_log` | The spec says append-only with no UPDATE/DELETE — good. For forensic integrity, add a sequential hash chain: each row includes `prev_hash = SHA-256(prev_row)`. This makes retroactive tampering detectable |

---

## Operational Readiness

| Dimension | Current State (Spec) | Target State (Recommended) |
|-----------|---------------------|---------------------------|
| **Observability** | Logging mentioned but no stack defined | Structured JSON logging (`structlog`) + Loki + Grafana. Prometheus metrics for edge gateway + backend |
| **Disaster Recovery** | Local buffer on edge gateway for VPN outage | Documented RTO/RPO: RTO <5 min (systemd restart), RPO <1 min (local buffer). Tested quarterly |
| **Deployment** | GitHub Actions → Vercel (FE) + Docker (BE) | Add health check endpoint on backend. Blue-green deployment for zero-downtime backend updates |
| **Backup** | Not specified | Daily PostgreSQL base backup + continuous WAL archiving. 30-day retention. Monthly restore test |
| **Alerting** | Threshold-based on telemetry data | Add infrastructure alerts: edge gateway health, VPN state, PostgreSQL replication lag, disk space, certificate expiry |
| **Runbook** | Not specified | Document: edge gateway restart procedure, VPN recovery, database failover, certificate renewal, report generation failure recovery |

---

## Redesign Roadmap

### Phase 1 (Weeks 1–2): Foundation Hardening — Build These Into R1

1. **Edge gateway architecture:** Implement per-VLAN async polling with `AsyncModbusTcpClient`. Systemd service with watchdog. Health endpoint. (Finding 1.1 + 1.4)
2. **VPN configuration:** WireGuard with PersistentKeepalive. Dual-path failover design (primary fibre + 4G backup). (Finding 1.2)
3. **Database connection pooling:** PgBouncer in transaction mode. Separate read and write pools. SQLAlchemy pool parameters. (Finding 1.3)
4. **Idempotent telemetry writes:** `ON CONFLICT DO NOTHING` on all telemetry inserts. (Finding 2.4)
5. **Missing indexes:** Add `(asset_id, ts DESC)` on `events.event` and `(breaker_id, ts DESC)` on `telemetry.breaker_state`.
6. **Cloud region selection:** Confirm hosting in AWS `af-south-1` or Azure South Africa North for <20ms VPN latency.

### Phase 2 (Weeks 4–6): Operational Resilience — Build Into R1

7. **WebSocket reconnection protocol:** Exponential backoff + jitter + full state sync on reconnect. (Finding 2.2)
8. **Structured logging:** `structlog` on edge gateway + backend. JSON format. Ship to Loki. (Finding 3.2)
9. **Report worker separation:** Extract report generation to a dedicated `arq` worker process. (Finding 2.3)
10. **Redis AOF:** Enable appendfsync=everysec for session persistence. (Finding 3.3)

### Phase 3 (R2 — Month 2–3): Scale Preparation

11. **PostgreSQL read replica:** Route dashboard queries to replica. (Finding 2.5)
12. **Continuous aggregate refresh after buffer flush.** (Finding 2.1)
13. **Prometheus metrics + Grafana dashboards** for infrastructure monitoring.
14. **Backup automation:** Daily base backup + continuous WAL archiving with tested restore.

### Phase 4 (R3+ — Quarter 2): Long-Term

15. **Infrastructure alerting:** Edge health, VPN state, DB replication lag, disk, certs.
16. **Runbook documentation** for all failure scenarios.
17. **Service extraction** if multi-site deployment is planned.

---

## CAP Theorem Trade-off Summary

**PostgreSQL (primary data store):** CP — strong consistency, partitioned during network failure (edge gateway disconnected = no writes, but local buffer preserves data for later sync). This is the correct trade-off for a monitoring system where data accuracy is more important than continuous availability. Stale-but-wrong data is worse than a visible "COMMS LOSS" state.

**Redis (state cache + pub/sub):** AP — eventual consistency for the breaker state cache (a missed pub/sub message means the dashboard is 1 poll cycle behind). This is acceptable — the next poll cycle corrects it. Session storage uses Redis with AOF, making it effectively CP.

**TimescaleDB continuous aggregates:** Eventual consistency with a defined lag. The aggregates trail raw data by the materialisation interval. For real-time dashboards, queries should target raw data or use `materialized_only = false` to fall through to raw when aggregates are stale.

**Assessment:** The trade-offs are correct for this domain. Strong consistency where it matters (breaker state, event log, audit trail), eventual consistency where it's tolerable (aggregated PQ views, cache).

---

## Cost Efficiency Notes

1. **Cloud hosting estimate:** Managed PostgreSQL (4 vCPU, 8GB RAM, 100GB SSD) ≈ R2,500–R4,000/month on AWS af-south-1 or Azure SA North. Managed Redis (1GB) ≈ R500/month. Backend container (2 vCPU, 4GB) ≈ R1,000/month. **Total ≈ R4,000–R5,500/month.** Within assumed budget.

2. **Over-provisioning risk:** The spec targets 99.9% uptime with streaming replication + auto-failover. For 28 users and a monitoring-only system, this is arguably over-engineered. A single PostgreSQL instance with daily backups and a documented manual failover procedure achieves ~99.5% uptime at half the cost. Consider whether 99.9% is a contractual requirement or an aspiration — the answer determines whether you need a standby replica from day one.

3. **TimescaleDB licensing:** TimescaleDB Community Edition is free and includes hypertables + continuous aggregates. The paid "Timescale" platform adds compression, tiered storage, and managed service. For R1, Community Edition on a managed PostgreSQL instance is sufficient. Evaluate paid tier if storage exceeds 500GB (unlikely before year 3).

4. **Vercel free tier:** The React SPA with 28 users and low traffic can likely run on Vercel's free or Hobby plan (R0–R300/month). No need for Vercel Pro until traffic or build frequency justifies it.

5. **SMS cost:** BulkSMS South Africa at ~R0.30 per SMS. With 3 critical-only SMS recipients and estimated 5–20 critical events/month, SMS cost is negligible (<R20/month). Budget for R50/month to be safe.
