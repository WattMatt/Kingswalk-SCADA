# Kingswalk SCADA GUI — Skills Reference

**Purpose:** This document catalogues all 50 skills available for building and maintaining the Kingswalk Mall SCADA web interface. Each skill is a self-contained set of best practices invoked during development. Skills are stored in `/skills/<name>/SKILL.md`.

**How skills work:** When a coding session encounters a task matching a skill's trigger condition, it reads the skill's SKILL.md file BEFORE writing any code. The skill provides constraints, patterns, anti-patterns, and quality gates specific to that task type.

---

## Skill Categories

### Category 1: API & Backend (8 skills)

#### api-endpoint-generator
**Context:** Used for all FastAPI REST endpoints serving the SCADA web interface (asset CRUD, report triggers, user management, control actions, telemetry queries).

**When to use:** Whenever implementing a new HTTP endpoint, whether it's for asset management, breaker control, or report generation.

**Steps the skill follows:**
1. Define route signature and HTTP method based on RESTful conventions
2. Create Pydantic v2 request/response models with proper validation and OpenAPI field descriptions
3. Implement route handler with error handling and business logic
4. Add RBAC decorator to enforce role-based access control
5. Generate OpenAPI documentation via docstrings
6. Write unit tests covering success, validation error, and authorization failure paths
7. Add integration test with real PostgreSQL database connection

**Quality gates:** Must have ≥1 test per endpoint path, OpenAPI documentation auto-generated, RBAC enforced on all non-public endpoints, request/response models in SKILLS.md follow Pydantic conventions.

---

#### auth-system-builder
**Context:** Used for implementing JWT + TOTP multi-factor authentication system for Kingswalk operators.

**When to use:** When building authentication infrastructure, adding SSO support, or modifying session/token logic.

**Steps the skill follows:**
1. Implement argon2id password hashing for password storage (never plaintext or MD5)
2. Design JWT structure: short-lived access tokens (15min) + long-lived refresh tokens (30day) with rotation
3. Implement TOTP enrollment flow with backup codes
4. Create RBAC middleware that validates JWT and enriches request context with user permissions
5. Build session management: concurrent session limits, device tracking, logout cascade
6. Implement token revocation list for immediate logout
7. Add audit logging for all auth events

**Quality gates:** All passwords stored with argon2id, JWT validation happens on every request, TOTP verified before operations, refresh token rotation on every use, no plaintext secrets in logs.

---

#### middleware-creator
**Context:** Used for FastAPI middleware handling cross-cutting concerns (audit logging, RBAC enforcement, request ID injection, rate limiting, CORS).

**When to use:** When adding a new cross-request concern that applies to multiple endpoints.

**Steps the skill follows:**
1. Identify the cross-cutting concern and which endpoints must enforce it
2. Write middleware factory function with dependency injection support
3. Add configuration validation at startup (fail fast on missing settings)
4. Implement request/response processing with error handling
5. Add integration tests verifying middleware behavior with real HTTP requests
6. Document middleware ordering (critical for CORS, auth, logging chain)
7. Monitor middleware performance (add per-middleware duration metrics)

**Quality gates:** Middleware applied uniformly across all targeted endpoints, configuration validated at startup, no silent failures, latency impact <5ms per middleware.

---

#### data-validation-layer
**Context:** Used for Pydantic v2 request/response models on backend, Zod schemas on frontend (TypeScript), ensuring type safety and early validation.

**When to use:** Before implementing any endpoint handler or component that accepts external data.

**Steps the skill follows:**
1. Define schema at the system boundary (HTTP request/response, WebSocket message)
2. Include comprehensive validation: type checks, length constraints, enum constraints, custom validators
3. Aggregate all validation errors in response (not fail-fast)
4. Return structured error responses with field-level detail
5. Write schema tests covering valid/invalid inputs, edge cases, boundary values
6. Document schema constraints in OpenAPI/JSDoc

**Quality gates:** No raw request data used before validation, all string inputs length-checked, enum values validated, error responses include field-level detail, schemas documented.

---

#### rate-limiter
**Context:** Used for API rate limiting, especially on breaker control endpoints to prevent rapid switching that damages equipment.

**When to use:** When protecting sensitive endpoints (control actions, expensive queries, external API calls).

**Steps the skill follows:**
1. Choose sliding window rate limiting strategy (preferred over token bucket for operational clarity)
2. Implement per-user limits (e.g., 10 control actions/minute) + per-IP limits (e.g., 100 requests/minute to prevent bot floods)
3. Add X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers to responses
4. Handle rate limit exceeded gracefully: return 429 with retry-after header
5. Log rate limit violations for security monitoring
6. Allow admin users to bypass limits if necessary

**Quality gates:** Breaker control endpoints limited to ≤1 action/second, API endpoints limited to ≤100 requests/minute/user, 429 responses include retry-after, no silent drops.

---

#### error-handler
**Context:** Used for global FastAPI exception handlers and frontend error boundaries to provide safe, informative error responses.

**When to use:** During endpoint implementation for consistent error classification and response formatting.

**Steps the skill follows:**
1. Classify errors into categories: validation errors (400), authentication errors (401), authorization errors (403), business logic errors (422), system errors (500)
2. Map exception types to HTTP status codes with specific error codes
3. Log error context (request ID, user, action, stack trace) with appropriate severity
4. Return safe error messages to client (no internal implementation details, database names, or stack traces)
5. Track error rates by type for monitoring
6. Test error paths explicitly (not just happy path)

**Quality gates:** No stack traces in API responses, all errors logged with context, error codes match HTTP semantics, client receives actionable error messages.

---

#### health-check-endpoint
**Context:** Used for /health, /ready, and /live endpoints required by Kubernetes/container orchestrators and monitoring systems.

**When to use:** During deployment infrastructure setup and when adding critical dependencies.

**Steps the skill follows:**
1. Implement /live endpoint: returns 200 if process is running (minimal check)
2. Implement /ready endpoint: checks all critical dependencies (PostgreSQL, Redis, external APIs) are reachable
3. Implement /health endpoint: includes detailed status of all components
4. For each dependency, implement a timeout and fallback (don't hang on slow dependencies)
5. Return structured JSON with component status and timestamps
6. Add liveness/readiness probes to Kubernetes manifests

**Quality gates:** /live responds <10ms, /ready checks all dependencies with <5s timeout total, /health includes version and timestamp, probes fail deployment on missing checks.

---

#### webhook-handler
**Context:** Used for receiving asynchronous callbacks from external services (Resend email, BulkSMS SMS gateway, Slack notifications, external integrations).

**When to use:** When integrating with webhook-based services or implementing callback-driven workflows.

**Steps the skill follows:**
1. Validate webhook signature (verify sender authenticity using HMAC-SHA256)
2. Respond to client with 200 immediately (before processing)
3. Queue webhook event for async processing (don't process in request handler)
4. Implement idempotency key handling (prevent duplicate processing if webhook resent)
5. Retry failed webhook processing with exponential backoff
6. Log all webhook events for audit trail
7. Monitor webhook latency and failure rates

**Quality gates:** All webhooks verified by signature, client receives 200 within 1 second, processing is async, duplicate events detected, failed webhooks retried.

---

### Category 2: Data & Database (8 skills)

#### data-schema-designer
**Context:** Used for PostgreSQL schema design across 5 logical schemas (core, assets, telemetry, events, reports).

**When to use:** During initial database design and before any schema changes.

**Steps the skill follows:**
1. Normalize schema to 3rd normal form (eliminate redundancy, avoid update anomalies)
2. Design Row-Level Security (RLS) policies to enforce multi-tenancy isolation
3. Plan indexes: cover all query predicates, consider covering indexes for point lookups
4. Include audit columns on all tables: created_at, updated_at, created_by, updated_by
5. For high-volume tables (telemetry), design TimescaleDB hypertables for compression and retention policies
6. Document schema relationships and constraints in ER diagram
7. Plan for future partitioning if table will exceed 100M rows

**Quality gates:** All tables have primary keys, foreign keys enforce referential integrity, RLS policies documented, indexes added for all query patterns, audit columns present.

---

#### data-migration-script
**Context:** Used for all schema changes after initial deployment (add columns, rename tables, add constraints, migrate data).

**When to use:** Whenever modifying database schema in production.

**Steps the skill follows:**
1. Write idempotent migrations: up/down scripts can run multiple times safely
2. Batch large data changes (e.g., UPDATE millions of rows) into chunks to avoid long-running locks
3. Add explicit locks only when necessary, use minimal holding time
4. Never hold locks during external API calls
5. Test on staging database with production-like data volume first
6. Include rollback plan and document rollback trigger conditions
7. Verify data integrity after migration (row counts, checksums)
8. Log migration start/end times and row counts affected

**Quality gates:** Migrations are reversible, tested on staging first, no schema locks held >1 second, large batches processed in <10k row chunks, rollback procedure documented.

---

#### database-query-optimizer
**Context:** Used for optimizing telemetry queries (millions of PQ samples), event log queries, and dashboard aggregations.

**When to use:** When dashboard queries exceed performance thresholds or when adding heavy reporting features.

**Steps the skill follows:**
1. Run EXPLAIN ANALYZE on slow queries to identify bottlenecks
2. Add covering indexes (indexes that include all required columns) for common queries
3. Use TimescaleDB continuous aggregates for pre-computed rollups (hourly PQ averages, daily energy totals)
4. Batch read operations when possible (SELECT IN (1,2,3,4,5) instead of 5 separate queries)
5. Implement query result caching with Redis for immutable date ranges
6. Monitor query latency with application-level instrumentation
7. Profile and test optimization on representative data volume

**Quality gates:** Dashboard queries return <500ms, telemetry queries use aggregates for >1-day ranges, all query plans use index scans (no seq scans), query latency monitored continuously.

---

#### data-pipeline-builder
**Context:** Used for ETL pipelines: edge gateway → TimescaleDB telemetry pipeline, Modbus poll → Redis → PostgreSQL flow.

**When to use:** When implementing data ingestion, transformation, and loading workflows.

**Steps the skill follows:**
1. Define source (Modbus gateway, MQTT broker, HTTP API) and sink (PostgreSQL, Redis, S3)
2. Implement transformation logic: parse Modbus register values, apply calibration, unit conversion
3. Handle errors: malformed data, missing values, source unavailable (retry with backoff)
4. Ensure idempotent processing (same input always produces same output)
5. Implement exactly-once delivery semantics using idempotency keys
6. Monitor pipeline latency (time from source to sink) and error rates
7. Log all transformations for auditing and debugging

**Quality gates:** Pipeline delivers data within SLA (e.g., <5 seconds from gateway to dashboard), duplicate prevention works, source/sink failures trigger alerts, transformation logic tested with edge cases.

---

#### data-quality-monitor
**Context:** Used for monitoring telemetry data completeness (are all 104 breakers reporting?), detecting stale readings, and flagging anomalous PQ values.

**When to use:** During real-time monitoring implementation and when adding data quality requirements.

**Steps the skill follows:**
1. Define quality dimensions: completeness (all sensors reporting), freshness (readings <5min old), validity (values within expected range)
2. Implement automated checks running every minute: query last reading timestamp for each sensor, count null values, detect outliers
3. Aggregate quality metrics: X% sensors online, Y% readings within range, Z% recent
4. Set thresholds with hysteresis (avoid flapping): alert if completeness <95% for >2 checks
5. Store quality history for trend analysis
6. Escalate alerts based on severity: missing single sensor = info, >10% offline = critical
7. Include quality metrics in dashboard and reports

**Quality gates:** Completeness alerts triggered within 5 minutes of data loss, quality metrics logged continuously, trend data available for 30 days, quality thresholds based on operational requirements.

---

#### caching-strategy
**Context:** Used for Redis caching of hot data: asset registry, latest breaker states, dashboard aggregations.

**When to use:** When query latency is insufficient or database load is too high.

**Steps the skill follows:**
1. Identify hot data: asset registry (read-heavy, changes rarely), breaker states (written frequently, read on every dashboard refresh)
2. Choose TTL based on data freshness requirements: asset registry 1-day, breaker states 5-minutes, PQ aggregates 1-hour
3. Implement cache invalidation: on-write invalidation for asset registry, TTL-based expiry for temporal data
4. Use cache keys with version prefixes to support cache busts without coordination
5. Implement cache-aside pattern: check cache first, fall back to database
6. Measure hit rates (target ≥80% for hot data) and optimize based on metrics
7. Handle cache misses gracefully (don't cascade failures)

**Quality gates:** Cache hit rate ≥80% for hot data, cache invalidation happens within 100ms of writes, cache misses don't degrade performance, cache layer transparent to business logic.

---

#### mock-data-generator
**Context:** Used for development/testing without live field devices (Modbus gateways, PQ analyzers, breakers).

**When to use:** During development sprints and for integration testing.

**Steps the skill follows:**
1. Generate realistic telemetry data: breaker load follows sinusoidal pattern with daily peak, PQ values vary with load, energy accumulates linearly
2. Implement breaker state sequences: closed for random duration, trip on overload, automatic reclose after delay
3. Add realistic noise: sensor readings vary ±0.5%, occasional spike transients
4. Generate tenant data: realistic asset counts, distribution across breaker circuits
5. Support seeding for reproducible test runs
6. Implement time acceleration (simulate days of data in minutes) for testing
7. Document data generation parameters

**Quality gates:** Generated data matches real field characteristics, test runs are reproducible, data generation <1 minute for 1 day of simulation, edge cases (zero load, max capacity) covered.

---

#### search-implementer
**Context:** Used for asset search, event log search, and audit log search with ranking and filtering.

**When to use:** When implementing any search UI for users to find assets or events.

**Steps the skill follows:**
1. Use PostgreSQL Full-Text Search (FTS) with tsvector for asset name/description/location searches
2. Implement weighted ranking: exact match > prefix match > substring match
3. Add pre/post filters: by asset type, severity level, date range
4. Implement pagination with cursor-based pagination for large result sets (avoid offset/limit)
5. Optimize FTS indexes: update tsvector on INSERT/UPDATE via triggers
6. Test search performance with production-like data volume
7. Log all searches for usage analytics and abuse detection

**Quality gates:** Searches return results <500ms, filtering doesn't require re-indexing, pagination handles 100k+ results, search queries logged.

---

### Category 3: Frontend & UI (3 skills)

#### web-artifacts-builder
**Context:** Used for building React components: dashboard panels, floor plan overlay, breaker control dialogs, PQ trend charts.

**When to use:** When implementing any new UI screen or component.

**Steps the skill follows:**
1. Design component hierarchy: identify container vs. presentational components
2. Implement responsive layout using Tailwind CSS (mobile-first, breakpoints at 640px/1024px/1536px)
3. Use Radix UI primitives for accessible form controls, modals, dropdowns
4. Manage state with Zustand: define stores for global state (user, assets, WebSocket connection)
5. Implement proper error boundaries: catch React errors and display safe error UI
6. Test component in isolation with Storybook or similar
7. Write accessibility tests: keyboard navigation, screen reader support, color contrast
8. Add loading states and skeleton loaders for async data

**Quality gates:** Components pass WCAG 2.1 AA accessibility checks, responsive at all breakpoints, error boundaries prevent white-screen crashes, accessibility tests pass.

---

#### react-component-optimizer
**Context:** Used for optimizing SVG floor plan (100+ hotspots), real-time dashboard updating hundreds of times per second.

**When to use:** When component render performance is degraded (<30 FPS) or WebSocket updates cause jank.

**Steps the skill follows:**
1. Profile component renders using React DevTools Profiler: identify expensive renders
2. Use useMemo to memoize expensive computations (e.g., floor plan hotspot calculation)
3. Use useCallback to memoize event handlers preventing child re-renders
4. Implement virtualization for long lists: only render visible items
5. Lazy-load heavy components (floor plan SVG) with React.lazy and Suspense
6. Batch WebSocket updates to render once per animation frame (use requestAnimationFrame)
7. Measure FPS and ensure dashboard maintains >30 FPS during normal operation
8. Profile memory usage and identify memory leaks

**Quality gates:** Dashboard renders at ≥30 FPS during normal use, floor plan renders <200ms on initial load, WebSocket updates don't cause jank, memory usage stable over time.

---

#### performance-optimizer
**Context:** Used for frontend bundle optimization, backend query optimization, and WebSocket throughput optimization.

**When to use:** When performance metrics exceed targets or when scaling up system load.

**Steps the skill follows:**
1. Measure baseline performance: dashboard load time, API response time, WebSocket message throughput
2. Profile bottleneck: CPU-bound (use Profiler), I/O-bound (use Network tab), memory-bound (use Heap Snapshot)
3. Apply targeted fix: split code bundle, optimize query, reduce message size
4. Verify improvement: measure baseline before/after, ensure improvement >10%
5. Monitor to prevent regression: set performance budgets in CI/CD
6. Document performance decision for future reference

**Quality gates:** All performance optimizations measured and verified, frontend bundles <500KB gzipped, API response time <500ms for 95th percentile, WebSocket throughput sufficient for 100+ concurrent users.

---

### Category 4: Real-time & Events (4 skills)

#### dashboard-backend
**Context:** Used for WebSocket server pushing live breaker states, PQ readings, and alarm notifications to connected browsers.

**When to use:** When implementing real-time dashboard and live monitoring features.

**Steps the skill follows:**
1. Implement WebSocket endpoint: handle connect, disconnect, and subscribe to update streams
2. Manage WebSocket connections: track active connections, enforce connection limits per user
3. Broadcast state changes: when breaker state changes or PQ reading arrives, send to all subscribed clients
4. Enforce RBAC on subscriptions: user can only subscribe to assets they have access to
5. Implement message compression: compress large update batches before sending
6. Handle reconnection gracefully: resend recent state on reconnect (avoid missing updates)
7. Monitor WebSocket health: latency, message rates, connection stability

**Quality gates:** WebSocket messages deliver <200ms latency, RBAC enforced on subscriptions, reconnection resumes without data loss, ≥100 concurrent WebSocket connections supported.

---

#### event-system-designer
**Context:** Used for internal event bus: breaker state change → alarm check → notification dispatch → audit log.

**When to use:** When designing workflows that span multiple subsystems.

**Steps the skill follows:**
1. Define event catalog: list all event types (BreakOpenRequest, BreakTripped, AlarmStateChanged, etc.)
2. Design event schema: required/optional fields, version strategy for backward compatibility
3. Choose delivery guarantee: at-least-once (may duplicate) vs. exactly-once (complex, usually not needed)
4. Implement event handlers: register handlers for each event type, handle idempotency
5. Implement dead letter queue: route failed events for manual inspection
6. Add event sourcing: store all events in audit log, replay for state reconstruction
7. Monitor event latency: from occurrence to all handlers completing

**Quality gates:** All event types documented, handlers are idempotent, dead letters processed within 1 hour, event replay tested for 1-week period.

---

#### state-machine-builder
**Context:** Used for breaker state machine (open→closing→closed→opening→tripped), alarm lifecycle, user session states.

**When to use:** When implementing complex stateful workflows with specific valid transitions.

**Steps the skill follows:**
1. Enumerate all states: breaker states (open, closing, closed, opening, tripped, maintenance)
2. Define valid transitions with guard conditions: only allow open→closing if not in maintenance
3. Implement state actions: on entering closed state, check PQ, dispatch telemetry
4. Handle invalid transitions: log and alert if unexpected state change occurs
5. Implement timeout transitions: if breaker stuck in closing >30sec, trip with fault
6. Test all paths: happy path, timeouts, invalid transitions, edge cases
7. Monitor state transitions for unexpected patterns

**Quality gates:** All states reachable, no unreachable states, timeouts prevent stuck states, transitions logged with timestamps, invalid transitions trigger alerts.

---

#### notification-system-builder
**Context:** Used for multi-channel alerts: in-app WebSocket toast, email via Resend, SMS via BulkSMS, webhook to Slack/Teams.

**When to use:** When implementing alerting for alarms, errors, reports, and system events.

**Steps the skill follows:**
1. Route alerts by severity + user preference: critical → all channels, warning → email, info → in-app only
2. Respect user notification preferences: allow opt-in/out per channel
3. Implement throttling: prevent alert spam (e.g., max 1 alert/minute/user for same condition)
4. Never lose messages: store in queue if delivery fails, retry with exponential backoff
5. Add message deduplication: same alert within 5 minutes delivered once
6. Log all notifications: who received, when, via which channel
7. Monitor delivery success rates by channel

**Quality gates:** Critical alerts delivered <5 seconds, no alerts lost (queue-backed), throttling prevents spam, user preferences respected, delivery logged completely.

---

### Category 5: Infrastructure & DevOps (7 skills)

#### cicd-pipeline-writer
**Context:** Used for GitHub Actions CI/CD: lint → test → build → deploy to Vercel (frontend) and Railway (backend).

**When to use:** During initial deployment infrastructure setup and when modifying deployment process.

**Steps the skill follows:**
1. Define pipeline stages: lint (eslint, black), test (pytest, vitest), build (Next.js, Docker), deploy (staging → production)
2. Implement quality gates: tests must pass, coverage >70%, no dependency vulnerabilities
3. Cache dependencies between runs to avoid re-downloading (save minutes on each build)
4. Implement secret management: use GitHub encrypted secrets, never log secrets
5. Add preview deploys: auto-deploy PR branches to Vercel preview URLs
6. Implement staged rollouts: deploy to staging first, verify, then promote to production
7. Log deployment events for audit trail: who deployed, when, what version

**Quality gates:** CI/CD duration <15 minutes, tests must pass to deploy, deployment logs audit trail, secrets never logged, preview deploys available for all PRs.

---

#### configuration-system
**Context:** Used for environment configuration (dev/staging/prod), secrets management (DB password, JWT secret, MFA key, API keys).

**When to use:** When adding environment-dependent configuration or secrets.

**Steps the skill follows:**
1. Validate all configuration at startup: fail fast if required env vars missing
2. Load configuration from environment variables (12-factor app principles)
3. Use strong typing for configuration: TypeScript/dataclass validation
4. Never log configuration values (especially secrets)
5. Support configuration overrides for testing without modifying env vars
6. Document all configuration options: what it does, valid values, defaults
7. Implement secrets rotation: keys stored in Vault, rotated without redeployment

**Quality gates:** Configuration validated at startup, all secrets in environment variables, no hardcoded secrets, configuration documented, startup fails if required config missing.

---

#### logging-system
**Context:** Used for structured JSON logging across FastAPI backend and edge gateway, with request correlation and PII stripping.

**When to use:** During initial backend setup and when adding new subsystems.

**Steps the skill follows:**
1. Implement structured JSON logging: every log entry is parseable JSON (not plain text)
2. Add request ID correlation: inject unique ID into every request, include in all logs
3. Implement PII stripping: remove user emails, phone numbers, IP addresses from logs
4. Use appropriate severity levels: DEBUG (code flow), INFO (normal events), WARNING (unexpected but recoverable), ERROR (failures)
5. Log all operations: API calls, database queries, email sending, WebSocket events
6. Implement log aggregation: centralize logs from all services
7. Set retention policies: INFO logs 30 days, DEBUG logs 7 days

**Quality gates:** All logs structured JSON, request IDs present, no PII in logs, severity levels accurate, logs aggregated centrally, retention policies enforced.

---

#### monitoring-alert-system
**Context:** Used for system monitoring (CPU, memory, disk, DB connections) + application monitoring (WebSocket connections, poll latency, queue depth).

**When to use:** During deployment and when adding new services.

**Steps the skill follows:**
1. Define metrics: system metrics (CPU, memory, disk), application metrics (WebSocket count, API latency, queue depth)
2. Set thresholds with hysteresis (avoid flapping): alert if CPU >80% for 2 checks
3. Implement multi-level alerts: warning (CPU 75-80%), critical (CPU >80%), page-on-call (DB unreachable)
4. Route alerts to appropriate teams: infrastructure → ops, application → developers
5. Implement alert grouping: deduplicate identical alerts within 5 minutes
6. Add runbooks: each alert includes steps to diagnose/resolve
7. Monitor alert fatigue: track alert frequency, adjust thresholds to reduce noise

**Quality gates:** Critical alerts notify on-call <5 minutes, alert thresholds based on SLA requirements, all alerts have runbooks, alert fatigue <1 alert/hour for non-critical alerts.

---

#### cron-job-builder
**Context:** Used for scheduled tasks: monthly report generation, data retention cleanup, continuous aggregate refresh, certificate expiry checks.

**When to use:** When implementing recurring tasks that run on schedule.

**Steps the skill follows:**
1. Define job: what it does, how often it runs, how long it typically takes
2. Implement idempotent execution: same input always produces same state (not double-processing)
3. Use distributed locking: ensure only one instance runs at a time (important in multi-server deployment)
4. Implement failure alerting: if job fails, alert on-call immediately
5. Log job execution: start time, end time, success/failure, rows affected
6. Monitor job duration: if takes >2x typical time, investigate
7. Implement manual trigger: allow operators to run job on-demand

**Quality gates:** Jobs are idempotent, distributed locking prevents duplicate runs, failures alert within 5 minutes, job duration monitored, manual triggers available.

---

#### release-management-automation
**Context:** Used for staged rollouts (canary → regional → full), database migration coordination, and rollback procedures.

**When to use:** When deploying to production and when rolling back bad deployments.

**Steps the skill follows:**
1. Implement canary deploy: deploy to 5% of traffic, monitor error rates
2. If canary metrics healthy, rollout to 25% traffic, then 100%
3. Monitor key metrics during rollout: error rate, latency, database queries
4. Coordinate database migrations: apply before code deploy, verify revert procedure works
5. Implement quick rollback: if metrics degrade, automated rollback to previous version
6. Verify rollback succeeds: check metrics, database state after rollback
7. Document decisions: what was deployed, what metrics were monitored, what triggered rollback

**Quality gates:** Canary percentage configurable, metrics monitored continuously, rollback tested before deployment, database migrations reversible, all decisions logged.

---

#### feature-flag-system
**Context:** Used for gradual rollout of new features (e.g., IEC 61850 support, new dashboard widgets), experimentation, and quick kills if issues found.

**When to use:** When deploying significant features to production.

**Steps the skill follows:**
1. Define flags: feature name, description, targeting rules (% of users, specific users, regions)
2. Implement flag evaluation: check if flag enabled for current user/asset/context
3. Store flags in-memory cache (not hitting database on every evaluation)
4. Implement flag changes without code redeploy: support dynamic flag toggle
5. Audit all flag changes: who changed, when, from what value
6. Test flag cleanup: remove flags after feature stabilized (prevent flag explosion)
7. Monitor flag impact: compare metrics between flag-enabled and flag-disabled groups

**Quality gates:** Flag evaluation <1ms, flag changes take effect <30 seconds, all changes audited, old flags cleaned up, impact measurable.

---

### Category 6: Security & Compliance (3 skills)

#### security-audit
**Context:** Used for annual pen-test preparation, ongoing code security review, and hardening.

**When to use:** Before production deployment and quarterly thereafter.

**Steps the skill follows:**
1. OWASP Top 10 checklist: injection, broken auth, sensitive data exposure, broken access control, etc.
2. Dependency scanning: identify outdated/vulnerable libraries, automate updates
3. Secrets detection: scan code for hardcoded passwords/keys, prevent future commits
4. RBAC verification: confirm all endpoints enforce role-based access properly
5. SQL injection prevention: confirm all queries use parameterized statements (Pydantic models)
6. Cross-site scripting prevention: confirm React component escaping
7. Cryptography review: confirm TLS for all network communication, strong ciphers

**Quality gates:** All OWASP items addressed, zero high-severity vulnerabilities, secrets not stored in code, RBAC enforced everywhere, SQL injection prevented, TLS on all connections.

---

#### compliance-checking-ai
**Context:** Used for POPIA (Protection of Personal Information Act) compliance validation, GDPR readiness, and 7-year audit retention verification.

**When to use:** During system design and before deployment.

**Steps the skill follows:**
1. Map regulations to rules: POPIA requires consent before processing PII, GDPR requires right to deletion
2. Validate data handling: confirm user consent logged before processing
3. Verify audit trail completeness: all data modifications logged and retained 7 years
4. Check deletion capability: confirm data can be deleted on request
5. Implement data minimization: confirm only necessary data collected
6. Test compliance with data: can we prove audit trail for past 7 years?
7. Document compliance: attestation of compliance for auditors

**Quality gates:** User consent logged, audit trail complete, deletion capability verified, data minimization implemented, compliance documented.

---

#### code-review-ai
**Context:** Used for automated PR review (security, test coverage, coding standards, anti-patterns) via GitHub Actions.

**When to use:** On every pull request to ensure quality before merge.

**Steps the skill follows:**
1. GitHub Actions integration: run on every PR before approval
2. Security checks: no hardcoded secrets, no unsafe dependencies
3. Test coverage check: coverage >70%, new code covered
4. Coding standards: linting passes, naming conventions followed
5. Anti-pattern detection: no debug logging left, no TODO without issue, no SQL constructors
6. Severity classification: critical blocks merge, warning requests changes, info is informational
7. Inline comments: add comments on specific lines for context

**Quality gates:** All critical issues block merge, warnings require response, tests required before merge, coverage >70%, security checks pass.

---

### Category 7: Testing (3 skills)

#### unit-test-writer
**Context:** Used for all Python backend tests (pytest) and TypeScript frontend tests (Vitest).

**When to use:** When implementing any new function, component, or business logic.

**Steps the skill follows:**
1. Test all paths: happy path, error cases, edge cases, boundary values
2. Mock external dependencies: don't call real database/API in unit tests
3. Test one behavior per test: single assert when possible, group related asserts
4. Aim for ≥80% code coverage (track coverage, fail CI if drops)
5. Use descriptive test names: test_user_can_control_breaker_when_authorized
6. Parametrize tests: test multiple inputs with single test function
7. Test error messages: confirm error messages are helpful

**Quality gates:** Coverage ≥80% of unit code, all functions have ≥1 test, error cases tested, external dependencies mocked, test names descriptive.

---

#### integration-test-writer
**Context:** Used for API endpoint tests with real PostgreSQL, WebSocket connection tests, Modbus simulator tests.

**When to use:** When implementing endpoints, real-time features, or complex workflows.

**Steps the skill follows:**
1. Use real database: spin up test PostgreSQL with test schema
2. Authenticated requests: test with various user roles to verify RBAC
3. Cleanup between tests: delete test data to prevent interference
4. Test full workflows: request → database change → response
5. Test error paths: invalid input, auth failure, database error
6. Test async operations: verify WebSocket events, background jobs complete
7. Measure test execution time: integration tests slower than unit tests, target <5 seconds per test

**Quality gates:** All endpoints have ≥1 integration test, real database used, cleanup works, auth tested, error paths tested, test suite runs <30 minutes.

---

#### load-testing-script
**Context:** Used for validating ≥100 concurrent users, WebSocket broadcast performance, telemetry ingestion throughput.

**When to use:** Before production deployment and when scaling infrastructure.

**Steps the skill follows:**
1. Define realistic user journeys: login → view dashboard → control breaker → view report
2. Ramp-up pattern: start 1 user, add 10 users/second until reaching target
3. Measure latencies: p50, p95, p99 latencies for all operations
4. Set pass/fail thresholds: dashboard load <500ms for p99, control response <200ms
5. Monitor backend during test: CPU, memory, database connections, error rates
6. Run 3x to verify consistency: results should be reproducible
7. Document results: user count, throughput, latencies, any errors

**Quality gates:** Test validates ≥100 concurrent users, all operations meet latency SLAs, no errors under load, infrastructure can handle test load, results documented.

---

### Category 8: Reporting & Documents (6 skills)

#### report-generator
**Context:** Used for monthly automated reports (usage, errors, PQ summary), on-demand reports.

**When to use:** When implementing reporting features.

**Steps the skill follows:**
1. Define report structure: title, summary, sections, charts, tables
2. Query builder: efficiently fetch data for report (use aggregates for large datasets)
3. Template rendering: HTML template → PDF/CSV output
4. Async generation: reports may take minutes, generate in background job
5. Storage: store generated reports in S3/object storage, link expires after 30 days
6. Distribution: email links to recipients, track open rates
7. Scheduling: monthly reports auto-generate on first of month

**Quality gates:** Reports generate within SLA (e.g., <5 min), async processing prevents timeout, templates tested, storage accessible, distribution reliable.

---

#### report-generation-automator
**Context:** Used for scheduling and distributing reports automatically.

**When to use:** When implementing recurring report delivery.

**Steps the skill follows:**
1. Define schedule: cron expression (e.g., "0 8 1 * *" for first of month 8am)
2. Data pull: query database for report data
3. Metric calculation: aggregate data into KPIs
4. Template rendering: fill report template with metrics
5. Distribution: email to recipient list or upload to shared drive
6. Failure alerting: if report fails, alert administrator
7. Audit logging: record report generation and distribution

**Quality gates:** Reports generate on schedule, recipients receive within 1 hour, failures alert within 5 minutes, audit log complete, reports not lost.

---

#### pdf
**Context:** Used for generating PDF reports, reading uploaded asset documents (manuals, certificates).

**When to use:** When working with PDFs.

**Steps the skill follows:**
1. Create from HTML template: use HTML/CSS to design layout, convert to PDF
2. Merge pages: combine multiple documents into single PDF
3. Add headers/footers: page numbers, branding, timestamps
4. Compress: reduce file size for email (target <5MB)
5. Read/extract: parse uploaded PDFs to extract text/metadata
6. Security: encrypt sensitive PDFs with password

**Quality gates:** PDFs generated correctly, formatting preserved, images included, compression works, extraction accurate, security applied.

---

#### xlsx
**Context:** Used for SLD_FIELD_MAP.xlsx maintenance, export of PQ data, energy billing workbooks.

**When to use:** When working with Excel files.

**Steps the skill follows:**
1. Read/write with openpyxl: Python library for Excel manipulation
2. Formatting: font, colors, borders, cell alignment
3. Formulas: implement Excel formulas for calculations (don't compute in Python)
4. Charts: embed charts in spreadsheets
5. Data validation: drop-down lists, number ranges, data quality
6. Performance: don't load entire workbook if possible (streaming for large files)

**Quality gates:** Excel files readable in Excel/Google Sheets, formatting applied, formulas work, charts display, large files handle efficiently.

---

#### docx
**Context:** Used for generating Word documents (commissioning reports, maintenance logs).

**When to use:** When generating formatted documents.

**Steps the skill follows:**
1. Template-based generation: use Word template with placeholders, fill with data
2. Table of contents: auto-generated from headings
3. Headers/footers: page numbers, document title, date
4. Branded formatting: fonts, colors, logos consistent with Kingswalk branding
5. Page breaks: ensure proper section breaks
6. Signatures: add signature blocks for approvals

**Quality gates:** Documents generate correctly, formatting applied, TOC accurate, signatures printable, documents compatible with Word/Google Docs.

---

#### email-automation-sequence
**Context:** Used for alert email templates, report distribution emails, user onboarding emails.

**When to use:** When sending automated emails.

**Steps the skill follows:**
1. Template design: responsive HTML template for email clients
2. Trigger conditions: what event triggers email (alarm, report ready, user signup)
3. Variable substitution: personalize with user name, asset name, data values
4. Unsubscribe handling: include unsubscribe link, respect preferences
5. Tracking: track open rates, click rates (optional, respect privacy)
6. Testing: preview in different email clients
7. Fallback: plain text version for clients that don't support HTML

**Quality gates:** Emails render correctly, personalization works, unsubscribe respected, templates tested, delivery reliable.

---

### Category 9: Code Quality (3 skills)

#### code-review
**Context:** Used for manual code review of critical changes (breaker control logic, auth system, data integrity).

**When to use:** Before merging high-risk code.

**Steps the skill follows:**
1. Identify language/framework: Python/FastAPI, TypeScript/React, or other
2. Check security: no hardcoded secrets, proper input validation, access control enforced
3. Test coverage: new code covered by tests, error cases tested
4. Error handling: errors caught and handled gracefully, stack traces not exposed
5. Performance: no O(n) loops, queries optimized, memory leaks avoided
6. Code style: follows project conventions, readable naming, documented where complex
7. Anti-patterns: no TODO without issue, no debug logging, no dead code

**Quality gates:** All critical changes reviewed, security verified, tests present, error handling adequate, performance acceptable, code quality high.

---

#### write-documentation
**Context:** Used for API documentation (OpenAPI), component documentation (Storybook), system documentation (ADRs).

**When to use:** When implementing features that others need to understand.

**Steps the skill follows:**
1. API documentation: OpenAPI/Swagger, auto-generated from code
2. Component documentation: Storybook stories showing component use cases
3. System documentation: Architecture Decision Records (ADRs) explaining "why"
4. Code comments: document "why" not "what", explain non-obvious logic
5. README: setup instructions, project overview, key concepts
6. Examples: working code examples for common tasks
7. Keep updated: documentation must match implementation

**Quality gates:** API documented, components in Storybook, architecture decisions recorded, READMEs current, examples working, documentation updated with code.

---

#### file-upload-handler
**Context:** Used for asset document uploads (manuals, certificates, commissioning photos).

**When to use:** When implementing file uploads.

**Steps the skill follows:**
1. MIME validation: only allow PDF, PNG, JPEG (no executables)
2. File size limit: max 50MB per file, 1GB per asset
3. Virus scan: submit to antivirus service before storage
4. Storage: S3/object storage with unique key, not filesystem
5. Access control: only authorized users can access uploaded files
6. Orphan cleanup: delete files not referenced after 30 days
7. Audit logging: log all uploads, downloads, deletions

**Quality gates:** MIME validation works, file sizes limited, virus scanning active, storage secure, access controlled, orphans cleaned up, audit logged.

---

### Category 10: Architecture & Strategy (2 skills)

#### architecture-review
**Context:** Used for quarterly architecture review, pre-scaling assessment, technology upgrade planning.

**When to use:** Every quarter and before major scaling or technology changes.

**Steps the skill follows:**
1. Identify failure points: single points of failure, cascading failures
2. Load analysis: current load, projected growth, capacity headroom
3. Redesign roadmap: what needs changing over next 2 quarters
4. Technology assessment: is current tech stack suitable for future load?
5. Cost analysis: infrastructure costs, projected costs at 10x scale
6. Risk mitigation: what breaks at 10x load, how to prevent
7. Document decisions: record assessment, recommendations, decisions

**Quality gates:** Architecture reviewed quarterly, failure modes documented, load tested, scaling plan exists, risks mitigated, decisions recorded.

---

#### queue-system-builder
**Context:** Used for background job processing (report generation, email sending, data export, alarm processing).

**When to use:** When implementing background jobs that shouldn't block user requests.

**Steps the skill follows:**
1. Job definition: what it does, parameters, expected duration
2. Priority: critical jobs (alarms) processed before low-priority (reports)
3. Retry logic: exponential backoff on failure, max retries per job
4. Dead letter queue: failed jobs moved here after max retries for manual inspection
5. Monitoring: track job count, completion rates, failure rates
6. Idempotency: jobs can run multiple times safely without side effects
7. Documentation: how to enqueue jobs, how to monitor, failure recovery

**Quality gates:** Jobs enqueued reliably, priority respected, retries work, dead letters processed, monitoring active, idempotency verified.

---

### Category 11: Custom / Project-Specific (1 skill)

#### sld-extraction
**Context:** Used for extracting asset data from ABB Single Line Diagram PDFs when field drawings are updated.

**When to use:** When updating asset inventory from new SLD drawings (typically quarterly).

**Steps the skill follows:**
1. pdftotext: convert PDF to searchable text
2. parse_per_mb.py: custom parser extracts breaker name, voltage, capacity from text
3. JSON validation: parsed data validated against schema (breaker must have name, voltage, capacity)
4. Excel rebuild: update SLD_FIELD_MAP.xlsx with new assets
5. Delta migration: only update changed assets (don't recreate entire database)
6. Verification: confirm extracted count matches diagram, sample spot-check values
7. Audit trail: log extracted data, changes made, who approved update

**Quality gates:** All breakers extracted accurately, parsing >95% success rate, delta migration correct, Excel validated, audit trail complete, spot-check passed.

**See `skills/sld-extraction/SKILL.md` for full pipeline details.**

---

## Skill Chaining by Build Phase

Skills are not used in isolation. The following sequences show which skills are invoked together in each build phase (see BUILD_STRATEGY.md for phase definitions):

### Phase 1 — Foundation (Weeks 1-3)
Build core infrastructure: authentication, database, API server.

**Skill chain:** data-schema-designer → data-migration-script → auth-system-builder → configuration-system → api-endpoint-generator → health-check-endpoint → cicd-pipeline-writer → unit-test-writer

**Context:** Start with database schema design (data-schema-designer), apply initial migrations (data-migration-script), build auth system (auth-system-builder), configure environments (configuration-system), implement first endpoints (api-endpoint-generator), add health checks (health-check-endpoint), automate CI/CD (cicd-pipeline-writer), test everything (unit-test-writer).

**Quality gate:** All endpoints have ≥70% test coverage, health checks pass, CI/CD pipeline green, auth system validated.

---

### Phase 2 — Real-time Core (Weeks 4-6)
Build WebSocket server and event bus for live dashboard.

**Skill chain:** data-pipeline-builder → dashboard-backend → event-system-designer → state-machine-builder → web-artifacts-builder → integration-test-writer

**Context:** Implement data pipeline from field devices (data-pipeline-builder), build WebSocket server (dashboard-backend), define event taxonomy (event-system-designer), implement state machines for equipment (state-machine-builder), build frontend components (web-artifacts-builder), test full workflows (integration-test-writer).

**Quality gate:** WebSocket latency <200ms, all state transitions tested, dashboard renders real-time data.

---

### Phase 3 — Asset Management (Weeks 7-9)
Build asset registry and document upload system.

**Skill chain:** api-endpoint-generator → data-validation-layer → search-implementer → file-upload-handler → sld-extraction → write-documentation

**Context:** Create asset CRUD endpoints (api-endpoint-generator), validate all inputs (data-validation-layer), add full-text search (search-implementer), implement document uploads (file-upload-handler), extract assets from SLD PDFs (sld-extraction), document APIs (write-documentation).

**Quality gate:** Asset search returns <500ms, file uploads validated, SLD extraction >95% accurate, API documented.

---

### Phase 4 — Monitoring & Control (Weeks 10-12)
Build breaker control and alarm systems.

**Skill chain:** web-artifacts-builder → react-component-optimizer → notification-system-builder → middleware-creator → rate-limiter

**Context:** Build control panels UI (web-artifacts-builder), optimize for responsive updates (react-component-optimizer), implement alerting (notification-system-builder), add request ID middleware (middleware-creator), rate-limit control endpoints (rate-limiter).

**Quality gate:** Control actions respond <200ms, alerts deliver <5s, dashboard smooth at 30 FPS.

---

### Phase 5 — Power Quality (Weeks 13-15)
Build PQ analysis and dashboard.

**Skill chain:** database-query-optimizer → caching-strategy → data-quality-monitor → performance-optimizer → report-generator

**Context:** Optimize PQ queries (database-query-optimizer), cache aggregates (caching-strategy), monitor data completeness (data-quality-monitor), optimize dashboard performance (performance-optimizer), generate PQ reports (report-generator).

**Quality gate:** PQ dashboard loads <500ms, data quality >95%, reports generate <5min.

---

### Phase 6 — Reporting (Weeks 16-17)
Automate report generation and distribution.

**Skill chain:** report-generation-automator → pdf → xlsx → cron-job-builder → email-automation-sequence

**Context:** Automate report scheduling (report-generation-automator), generate PDFs (pdf), export to Excel (xlsx), schedule monthly runs (cron-job-builder), distribute via email (email-automation-sequence).

**Quality gate:** Monthly reports auto-generate, distribution reliable, formats correct.

---

### Phase 7 — Hardening (Weeks 18-20)
Security hardening and compliance.

**Skill chain:** security-audit → compliance-checking-ai → load-testing-script → error-handler → logging-system → monitoring-alert-system → code-review-ai

**Context:** Perform security review (security-audit), verify compliance (compliance-checking-ai), validate under load (load-testing-script), implement error handling (error-handler), add logging (logging-system), add monitoring (monitoring-alert-system), automate code review (code-review-ai).

**Quality gate:** All OWASP items addressed, POPIA compliant, load test passes, 100+ concurrent users supported.

---

### Phase 8 — Deployment (Weeks 21-22)
Final deployment infrastructure and rollout.

**Skill chain:** release-management-automation → feature-flag-system → architecture-review → code-review → write-documentation → docx

**Context:** Set up staged rollouts (release-management-automation), implement feature flags (feature-flag-system), review architecture pre-launch (architecture-review), review critical code (code-review), finalize documentation (write-documentation), generate commissioning docs (docx).

**Quality gate:** Canary deploy working, rollback tested, all docs complete, architecture assessed.

---

## Cross-Skill Dependencies

Some skills depend on output from other skills:

- **api-endpoint-generator** requires data-validation-layer (models) and auth-system-builder (RBAC)
- **dashboard-backend** requires event-system-designer (event types) and state-machine-builder (valid states)
- **report-generator** requires database-query-optimizer (efficient queries) and caching-strategy (pre-computed aggregates)
- **notification-system-builder** requires event-system-designer (event routing)
- **file-upload-handler** requires error-handler (validation errors) and logging-system (audit trail)
- **load-testing-script** requires performance-optimizer (understanding bottlenecks)

---

## How to Use This Document

1. **Before starting any coding task**, identify which skill(s) apply from the categories above
2. **Read the relevant SKILL.md file(s)** from `/skills/<name>/SKILL.md` in full before writing code
3. **Follow the skill's constraints and patterns** — they encode hard-won best practices and project standards
4. **Multiple skills may apply** to a single task — e.g., implementing a new endpoint requires:
   - api-endpoint-generator (endpoint structure)
   - data-validation-layer (request/response validation)
   - auth-system-builder (RBAC enforcement)
   - unit-test-writer (test coverage)
   - code-review (peer review of critical endpoints)
5. **After completing the task**, verify against the skill's quality gates before considering it done
6. **Update SPEC.md** if the task changes any requirement or architecture decision (e.g., if adding a new WebSocket message type, update the event schema in SPEC.md)

---

## Quick Reference Table

| Skill Name | Category | Primary Use | Key Output |
|---|---|---|---|
| api-endpoint-generator | API & Backend | REST endpoints | OpenAPI docs, endpoint code |
| auth-system-builder | API & Backend | JWT + TOTP auth | auth middleware, token endpoints |
| middleware-creator | API & Backend | Cross-cutting concerns | middleware factory, applied globally |
| data-validation-layer | API & Backend | Input validation | Pydantic models, error responses |
| rate-limiter | API & Backend | Rate limiting | 429 responses, header values |
| error-handler | API & Backend | Error classification | safe error responses, logged errors |
| health-check-endpoint | API & Backend | Deployment health | /health, /ready, /live endpoints |
| webhook-handler | API & Backend | Async callbacks | signature validation, queued events |
| data-schema-designer | Data & Database | Database design | schema DDL, RLS policies, indexes |
| data-migration-script | Data & Database | Schema changes | reversible migrations, tested |
| database-query-optimizer | Data & Database | Query performance | optimized queries, covering indexes |
| data-pipeline-builder | Data & Database | ETL workflows | pipeline code, telemetry ingestion |
| data-quality-monitor | Data & Database | Data completeness | quality checks, alerts |
| caching-strategy | Data & Database | Hot data caching | Redis keys, TTL strategy |
| mock-data-generator | Data & Database | Test data | realistic test datasets |
| search-implementer | Data & Database | Full-text search | tsvector indexes, ranking |
| web-artifacts-builder | Frontend & UI | React components | component code, styling |
| react-component-optimizer | Frontend & UI | Render performance | optimized components, memoization |
| performance-optimizer | Frontend & UI | Overall performance | measured improvements, benchmarks |
| dashboard-backend | Real-time & Events | WebSocket server | WS endpoint, broadcast logic |
| event-system-designer | Real-time & Events | Event bus | event catalog, schema |
| state-machine-builder | Real-time & Events | Equipment state | state transitions, guards |
| notification-system-builder | Real-time & Events | Multi-channel alerts | email/SMS/Slack templates, routing |
| cicd-pipeline-writer | Infrastructure & DevOps | CI/CD automation | GitHub Actions workflows |
| configuration-system | Infrastructure & DevOps | Config management | environment validation, secrets |
| logging-system | Infrastructure & DevOps | Structured logging | JSON logs, request correlation |
| monitoring-alert-system | Infrastructure & DevOps | System monitoring | metrics, thresholds, alerts |
| cron-job-builder | Infrastructure & DevOps | Scheduled tasks | cron expressions, idempotent jobs |
| release-management-automation | Infrastructure & DevOps | Staged rollouts | canary deploy, rollback |
| feature-flag-system | Infrastructure & DevOps | Feature toggles | flag definitions, evaluation |
| security-audit | Security & Compliance | Security review | audit findings, remediation |
| compliance-checking-ai | Security & Compliance | Compliance validation | compliance mapping, attestation |
| code-review-ai | Security & Compliance | Automated review | PR comments, severity classification |
| unit-test-writer | Testing | Python/TypeScript tests | test code, coverage reports |
| integration-test-writer | Testing | API/workflow tests | integration tests, real DB |
| load-testing-script | Testing | Load validation | load test results, latency metrics |
| report-generator | Reporting & Documents | Report generation | report code, template |
| report-generation-automator | Reporting & Documents | Report automation | scheduled reports, delivery |
| pdf | Reporting & Documents | PDF handling | generated PDFs, extraction |
| xlsx | Reporting & Documents | Excel handling | workbook code, formulas |
| docx | Reporting & Documents | Word handling | document generation |
| email-automation-sequence | Reporting & Documents | Email templates | email templates, triggers |
| code-review | Code Quality | Manual review | review comments, decisions |
| write-documentation | Code Quality | Documentation | API docs, READMEs, ADRs |
| file-upload-handler | Code Quality | File uploads | upload endpoint, validation |
| architecture-review | Architecture & Strategy | Architecture assessment | architecture decisions, roadmap |
| queue-system-builder | Architecture & Strategy | Background jobs | job queue, worker code |
| sld-extraction | Custom / Project-Specific | SLD parsing | extracted assets, Excel rebuild |

---

## Key Principles

**Skill-First Development:** Always read the relevant skill before coding. The skill encodes lessons learned and prevents common mistakes.

**Quality Gates Matter:** Each skill has quality gates. Code review must verify gates are met. Never merge code that fails quality gates.

**Chaining Skills:** Use the phase chains to understand how skills work together. Implement skills in the sequence recommended for your phase.

**Documentation is Code:** Skills themselves are living documentation. Update SKILL.md files when patterns change. Share lessons with the team.

**Measure Everything:** Most skills include measurement guidance. Measure baseline, apply optimization, verify improvement. Document results.

**Fail Safe:** When in doubt about which skill applies, consult this reference and the SKILL.md files. No question is too small.
