# Security Audit Report — Pre-Build Architecture & Design Review

**Audited:** Kingswalk SCADA Monitoring System — full architecture, database schema, auth design, deployment model, edge gateway security
**Date:** 2026-04-11
**Auditor:** security-audit skill (pre-build pass)
**Stack:** Python 3.12 (FastAPI) + TypeScript (React 19) + PostgreSQL 16 + TimescaleDB + Redis 7 + WireGuard VPN + Vercel + Docker
**Audit Standard:** OWASP Top 10 (2021), SANS Top 25, IEC 62443 (SCADA-specific)
**Scope:** This is a **pre-build architecture and design audit**. No application code exists yet. Findings are against the specified architecture in SPEC.md v4.0, BUILD_STRATEGY.md v3, DB_SCHEMA.md, and the two migration files (0001_initial.sql, 0001a_schema_review_fixes.sql).

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 7 |
| LOW | 5 |
| INFORMATIONAL | 4 |

**Overall Risk Rating:** HIGH
**Ship Readiness:** DO NOT BUILD WITHOUT ADDRESSING — CRITICAL and HIGH issues present in the design that must be resolved before or during Phase 1 implementation.

**Note:** Because this is a pre-build audit (no code to inspect), findings target architectural decisions, schema design, and specified security controls. The purpose is to ensure the build session implements these correctly from day one, rather than retrofitting security post-build.

---

## Findings

### [CRITICAL] — F1: MFA Secret Stored Without Application-Layer Encryption

**Severity:** CRITICAL
**CVSS Score:** 8.7
**CVSS Vector:** `AV:N/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:N`
**CWE:** CWE-312: Cleartext Storage of Sensitive Information
**OWASP Category:** A02 — Cryptographic Failures
**Location:** SPEC.md §B.4 `core.users.mfa_secret`, 0001_initial.sql line 28

**Description:**
The SPEC states that `mfa_secret` should be "AES-256 encrypted at rest" (SPEC B.4 notes column). However, the database column is defined as `text` with no CHECK constraint or application-layer encryption specification. The column stores the TOTP shared secret — if an attacker gains database read access (SQL injection, backup theft, compromised DB credentials), they can clone every user's MFA token generator, completely defeating MFA.

The SPEC mentions encryption at rest but does not specify:
- Where the AES-256 encryption key is stored (it MUST NOT be in the database or application code)
- What encryption mode (must be AES-256-GCM, not ECB or CBC without HMAC)
- How key rotation works
- Whether the IV/nonce is stored alongside the ciphertext

**Database stores the raw TOTP seed as `text`:**
```sql
-- 0001_initial.sql, line 28
mfa_secret      text,           -- TOTP secret, no encryption enforced at DB level
```

**Required architecture specification (add to SPEC.md A.5 or BUILD_HANDOFF.md):**
```
MFA Secret Encryption:
1. TOTP secrets MUST be encrypted with AES-256-GCM before storage.
2. The encryption key MUST reside in the secrets manager (AWS Secrets Manager / Doppler / Infisical),
   NOT in environment variables, NOT in code, NOT in the database.
3. The stored value format: base64(nonce || ciphertext || tag).
4. Key rotation: when the encryption key is rotated, a background job must re-encrypt all
   mfa_secret values. Store a key_version integer alongside the ciphertext.
5. The decrypted TOTP secret must NEVER be logged, returned in API responses, or cached in Redis.
```

**Why This Is CRITICAL:**
MFA is the final authentication barrier for Admin and Operator accounts. If an attacker can extract TOTP seeds, they can generate valid TOTP codes indefinitely without possessing the user's phone. Combined with a stolen password hash (crackable offline with argon2id at ~10 attempts/sec on GPU), this allows full account takeover of Admin accounts with control over all system configuration.

---

### [HIGH] — F2: RLS Policies Not Defined — Enabled Tables Have No Access Rules

**Severity:** HIGH
**CVSS Score:** 7.5
**CVSS Vector:** `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N`
**CWE:** CWE-862: Missing Authorization
**OWASP Category:** A01 — Broken Access Control
**Location:** 0001a_schema_review_fixes.sql lines 220–233, DB_SCHEMA.md §10

**Description:**
RLS is enabled on 10 tables (telemetry.pq_sample, telemetry.energy_register, telemetry.breaker_state, telemetry.lighting_state, events.event, core.audit_log, core.users, core.session, core.invite, core.password_reset). However, **no RLS policies are defined**. The migration contains a comment: "Placeholder policies — allow the application role (scada_app) full access until Phase 1 RBAC middleware is built."

The danger is twofold:
1. If the application connects as the table owner (common during early development), RLS is bypassed entirely — the `ENABLE ROW LEVEL SECURITY` has no effect on the table owner.
2. If the application connects as a non-owner role without policies defined, **all access is denied by default** — the application breaks silently.

Neither state provides actual row-level security.

**Current state (no policies):**
```sql
ALTER TABLE core.users ENABLE ROW LEVEL SECURITY;
-- No CREATE POLICY statements exist anywhere in the migrations
```

**Required implementation (Phase 1 auth build):**
```sql
-- Example: core.users — users can read own record, admins read all
CREATE POLICY users_self_read ON core.users
    FOR SELECT
    USING (
        id::text = current_setting('app.current_user_id', true)
        OR current_setting('app.current_user_role', true) = 'admin'
    );

-- Example: telemetry — all authenticated users can read (monitoring system)
CREATE POLICY telemetry_read ON telemetry.pq_sample
    FOR SELECT
    USING (current_setting('app.current_user_id', true) IS NOT NULL);

-- Telemetry write restricted to edge gateway service role
CREATE POLICY telemetry_write ON telemetry.pq_sample
    FOR INSERT
    WITH CHECK (current_user = 'scada_writer');
```

**Why This Matters:**
RLS without policies is security theatre. The build session MUST create concrete policies during Phase 1, not defer to "later." The BUILD_HANDOFF.md should specify minimum RLS policies as a Phase 1 gate.

---

### [HIGH] — F3: No CSRF Protection Specified for Cookie-Based Auth

**Severity:** HIGH
**CVSS Score:** 7.1
**CVSS Vector:** `AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N`
**CWE:** CWE-352: Cross-Site Request Forgery
**OWASP Category:** A01 — Broken Access Control
**Location:** SPEC.md §C.1 (auth flow)

**Description:**
The SPEC defines JWT access tokens (15 min) + refresh tokens (7 days, rotated on use). It does not specify WHERE these tokens are stored on the client. There are two patterns, each with distinct security implications:

- **Pattern A — `localStorage`:** Vulnerable to XSS (any injected script can steal the token). Immune to CSRF.
- **Pattern B — `HttpOnly` cookies:** Immune to XSS token theft. Vulnerable to CSRF unless mitigated.

The SPEC does not specify which pattern is used, and does not mention CSRF protection at all. If the build session chooses HttpOnly cookies (the more secure pattern for token storage), CSRF protection becomes mandatory for all state-changing endpoints.

**Required specification (add to SPEC.md A.5 or C.1):**
```
Token Storage & CSRF:
1. Access token: HttpOnly, Secure, SameSite=Strict cookie. NOT in localStorage.
2. Refresh token: HttpOnly, Secure, SameSite=Strict cookie on /api/auth/refresh path only.
3. CSRF mitigation: SameSite=Strict provides primary CSRF protection.
   Double-submit cookie pattern as defence-in-depth for non-GET requests.
4. API endpoints called by the edge gateway use mTLS/API key auth (not cookies) — exempt from CSRF.
```

**Why This Matters:**
Without explicit CSRF specification, the build session may inadvertently create state-changing endpoints (acknowledge alarm, disable user, change threshold) that can be triggered by a malicious link in an email to an authenticated operator.

---

### [HIGH] — F4: Invite Token in JWT — Algorithm and Validation Not Specified

**Severity:** HIGH
**CVSS Score:** 7.5
**CVSS Vector:** `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N`
**CWE:** CWE-347: Improper Verification of Cryptographic Signature
**OWASP Category:** A02 — Cryptographic Failures
**Location:** SPEC.md §C.1 step 1

**Description:**
The invite flow states: "Link contains signed JWT with role pre-assignment." This JWT is sent via email (untrusted channel). The SPEC does not specify:

1. **Algorithm:** Must be `HS256` with ≥256-bit secret, or `RS256`/`EdDSA` with asymmetric keys. The `alg: none` attack and HS256/RS256 confusion attack must be prevented.
2. **Claims validation:** `exp` (expiry), `iss` (issuer), `aud` (audience), `sub` (invite ID) must all be validated. The 48-hour expiry is specified but not the other claims.
3. **One-time use:** The invite JWT must be invalidated after first use. Without this, a link intercepted from an email relay/log could be used repeatedly to create accounts.
4. **Role escalation:** The JWT contains "role pre-assignment." If the JWT payload is not integrity-checked, an attacker could modify `role: "viewer"` to `role: "admin"` before submitting.

**Required specification:**
```
JWT Standards (all JWTs — access, refresh, invite):
1. Algorithm: HS256 with 256-bit secret from secrets manager. Reject alg:none.
2. Validate: exp, iss (must be "kingswalk-scada"), aud (must match token type).
3. Access token aud: "access". Refresh token aud: "refresh". Invite token aud: "invite".
4. Invite tokens: one-time use — mark invite record as accepted on first use. Reject reuse.
5. Library: python-jose or PyJWT with algorithm whitelist. NEVER decode without verification.
```

---

### [HIGH] — F5: Password Reset Flow Lacks Rate Limiting and Enumeration Protection

**Severity:** HIGH
**CVSS Score:** 7.3
**CVSS Vector:** `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:H/A:N`
**CWE:** CWE-640: Weak Password Recovery Mechanism for Forgotten Password
**OWASP Category:** A07 — Identification & Authentication Failures
**Location:** SPEC.md §C.1 step 5

**Description:**
The password reset specification states: "Self-service via email link (Resend). Link expires 1 hour." This is insufficient. The following attack vectors are not addressed:

1. **User enumeration:** If the reset endpoint returns different responses for "email found" vs "email not found," an attacker can enumerate valid email addresses. The endpoint must return a uniform response regardless of whether the email exists.
2. **Rate limiting:** The login rate limit (5 attempts/15 min) is specified, but no rate limit is specified for password reset requests. An attacker could flood reset requests to: (a) fill the user's inbox (email bombing), (b) generate thousands of valid reset tokens hoping to guess one.
3. **Token entropy:** The `core.password_reset` table stores `token_hash text` — good (tokens are hashed, not stored in plaintext). But the token generation method is not specified. Must be ≥256 bits from `secrets.token_urlsafe(32)`.
4. **Concurrent tokens:** No specification on whether requesting a new reset invalidates previous tokens. Without this, multiple valid tokens can coexist.

**Required specification (add to C.1):**
```
Password Reset Security:
1. Response: Always return "If that email exists, a reset link has been sent." — no enumeration.
2. Rate limit: 3 reset requests per email per hour. 10 reset requests per IP per hour.
3. Token: secrets.token_urlsafe(32), SHA-256 hashed before storage.
4. Supersession: New reset request invalidates all previous unused tokens for that user.
5. Post-reset: Invalidate ALL active sessions for the user (already specified).
```

---

### [HIGH] — F6: Edge Gateway Telemetry Endpoint — mTLS vs API Key Decision Deferred

**Severity:** HIGH
**CVSS Score:** 7.4
**CVSS Vector:** `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N`
**CWE:** CWE-306: Missing Authentication for Critical Function
**OWASP Category:** A07 — Identification & Authentication Failures
**Location:** SPEC.md §A.5 deployment section, §B.3.3

**Description:**
The SPEC states: "Mutual TLS or API key authentication on the telemetry ingestion endpoint as defence-in-depth (VPN alone is a single layer)." The "or" is the problem — the decision is not made.

This endpoint accepts telemetry data that drives the entire monitoring system. If an attacker can inject fabricated telemetry (e.g., breakers all reporting "closed" when they're tripped), operators will make incorrect decisions based on false data. In a SCADA context, this is a safety concern.

**Recommendation:** Choose mTLS now. API keys are static secrets that can be leaked via logs, environment dumps, or config mismanagement. mTLS provides mutual authentication, is rotation-friendly (certificate renewal), and is standard for SCADA/OT telemetry ingestion.

**Required specification:**
```
Edge-to-Cloud Authentication:
1. Transport: WireGuard VPN (primary layer).
2. Application auth: mTLS on the /api/v1/telemetry endpoint.
3. Edge gateway client certificate: generated during provisioning, signed by a project-specific CA.
4. Certificate stored on edge gateway in /etc/scada/certs/ with 600 permissions.
5. Certificate rotation: annual, automated via ACME or manual renewal process.
6. The backend MUST reject any telemetry POST without a valid client certificate,
   even from within the VPN — defence in depth.
7. API key authentication is NOT acceptable for this endpoint.
```

---

### [MEDIUM] — F7: No Content Security Policy Specified

**Severity:** MEDIUM
**CVSS Score:** 5.3
**CWE:** CWE-1021: Improper Restriction of Rendered UI Layers
**OWASP Category:** A05 — Security Misconfiguration
**Location:** SPEC.md §A.5 (no mention of CSP)

**Description:**
The SPEC specifies CORS (explicitly set to Vercel domain only) but does not specify a Content Security Policy. CSP is the primary defence against XSS in modern browsers. For a SCADA monitoring dashboard where operators make safety decisions based on displayed data, preventing script injection is critical.

**Required specification:**
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';  -- required for Tailwind
  img-src 'self' data: blob:;        -- for canvas SVG rendering
  connect-src 'self' wss://{domain}; -- WebSocket
  font-src 'self';
  frame-ancestors 'none';            -- prevent clickjacking (replaces X-Frame-Options)
  base-uri 'self';
  form-action 'self';
```

---

### [MEDIUM] — F8: Modbus Write Function Code Prohibition — Enforcement Point Not Specified

**Severity:** MEDIUM
**CVSS Score:** 6.5
**CWE:** CWE-284: Improper Access Control
**OWASP Category:** A01 — Broken Access Control
**Location:** SPEC.md §2.1, BUILD_STRATEGY.md §2.1

**Description:**
The SPEC is explicit: "Monitoring only, no write function codes (FC06/FC16) permitted." The BUILD_STRATEGY §2.1 states: "Modbus: FC03 (read holding registers), FC04 (read input registers) — monitoring only." However, **the enforcement point is not specified.** This prohibition must be enforced at the code level, not just as a policy statement.

If a bug, misconfiguration, or compromised edge gateway sends a Modbus FC06 (Write Single Register) or FC16 (Write Multiple Registers) to an Ekip Com, it could change breaker trip settings, disable protection relays, or alter measurement calibration. This is a safety-critical concern.

**Required specification:**
```
Modbus Write Prevention (SCADA Safety):
1. The pymodbus client wrapper MUST only expose read_holding_registers() and read_input_registers().
2. Write methods (write_register, write_registers, write_coil, write_coils) MUST NOT be imported
   or callable from the polling code.
3. Implementation: create a ReadOnlyModbusClient wrapper class that delegates only FC03/FC04.
4. Unit test: verify that calling any write method raises a RuntimeError.
5. CI gate: ruff rule or grep check that fc06/fc16/write_register never appears in edge/ code.
```

---

### [MEDIUM] — F9: Session Fixation — Session Regeneration Not Specified

**Severity:** MEDIUM
**CVSS Score:** 5.4
**CWE:** CWE-384: Session Fixation
**OWASP Category:** A07 — Identification & Authentication Failures
**Location:** SPEC.md §C.1

**Description:**
The auth flow specifies login produces a JWT access token + refresh token. The `core.session` table tracks active sessions. However, the spec does not state that:

1. A new session ID must be generated on every successful login (preventing session fixation).
2. The refresh token must be rotated on every use (preventing replay attacks). The spec says "rotated on use" — good, but must also specify that the old refresh token is invalidated immediately, not after a grace period.
3. All sessions must be invalidated on password change (specified) and on role change (NOT specified — if an admin demotes a user, existing sessions retain the old role in the JWT).

**Required specification addition:**
```
Session Security:
1. New session record + new refresh token on every login — never reuse session IDs.
2. Refresh rotation: old refresh_hash is overwritten atomically. No grace period.
3. Role change: all sessions for the affected user are invalidated immediately.
4. JWT claims refresh: access token must be re-issued (not just refreshed) after any role change.
```

---

### [MEDIUM] — F10: Recovery Codes — Insufficient Specification

**Severity:** MEDIUM
**CVSS Score:** 5.9
**CWE:** CWE-330: Use of Insufficiently Random Values
**OWASP Category:** A02 — Cryptographic Failures
**Location:** SPEC.md §C.1 step 2

**Description:**
The SPEC states: "Generates recovery codes (10, single-use, hashed)." This is a good start but insufficient:

1. **Code format:** Not specified. Must be cryptographically random, ≥128 bits entropy. Common format: 8 groups of 4 alphanumeric characters.
2. **Hash algorithm:** "Hashed" is vague. Recovery codes must be hashed with bcrypt or argon2id (not SHA-256, because recovery codes are short and SHA-256 is fast to brute-force).
3. **Display once:** Codes must be shown exactly once during enrollment and never retrievable again.
4. **Regeneration:** When new codes are generated, all old codes must be invalidated.
5. **Storage:** No table is defined for recovery codes in the schema. They need their own table or a column on core.users.

**Required schema addition:**
```sql
CREATE TABLE IF NOT EXISTS core.recovery_code (
    id          serial PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES core.users(id),
    code_hash   text NOT NULL,      -- argon2id hash of the recovery code
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON core.recovery_code (user_id);
```

---

### [MEDIUM] — F11: Audit Log Integrity — No Tamper Protection

**Severity:** MEDIUM
**CVSS Score:** 5.5
**CWE:** CWE-117: Improper Output Neutralization for Logs
**OWASP Category:** A09 — Security Logging & Monitoring Failures
**Location:** 0001_initial.sql lines 34–45, SPEC.md §B.4

**Description:**
The audit log is append-only with 7-year retention and is critical for POPIA compliance and incident investigation. However:

1. **No DELETE protection at the DB level:** While the SPEC says "no UPDATE or DELETE permitted," this is a policy, not an enforcement. A compromised admin account or a SQL injection could DELETE audit records.
2. **No integrity chain:** For forensic trustworthiness, audit logs in safety-critical systems should include a hash chain (each entry includes the hash of the previous entry) or use write-once storage.
3. **Log injection:** The `payload jsonb` column accepts arbitrary JSON. If user-controlled data (asset names, search queries) is logged without sanitization, an attacker could inject misleading log entries.

**Required specification:**
```
Audit Log Integrity:
1. REVOKE DELETE, UPDATE ON core.audit_log FROM scada_app;
   Only the DBA role (not used by the application) can modify audit records.
2. INSERT-only grant for the application role on core.audit_log.
3. Consider: hash chain column (hash of previous row) for tamper evidence — evaluate during Phase 1.
4. All user-supplied values in audit payload must be JSON-escaped (Pydantic handles this natively).
```

---

### [MEDIUM] — F12: WebSocket Authentication — Token Validation on Connection and During Session

**Severity:** MEDIUM
**CVSS Score:** 5.3
**CWE:** CWE-613: Insufficient Session Expiration
**OWASP Category:** A07 — Identification & Authentication Failures
**Location:** SPEC.md §B.3.5

**Description:**
The SPEC describes WebSocket reconnection protocol but not WebSocket authentication. Key questions unaddressed:

1. How is the JWT passed during WebSocket handshake? (Query parameter is visible in logs; cookie is preferred.)
2. Is the JWT validated on every WebSocket message, or only on connection? If only on connection, a revoked user retains their WebSocket connection until the next reconnect.
3. What happens when the access token expires (15 min) but the WebSocket is still open?

**Required specification:**
```
WebSocket Authentication:
1. JWT passed via cookie (not query parameter — query params appear in access logs).
2. JWT validated during WebSocket upgrade handshake.
3. Server-side periodic check (every 60s): verify session is still valid. If revoked, close with 4001 code.
4. On access token expiry: client-side refresh cycle continues independently of WebSocket.
5. On forced logout (admin action): server closes WebSocket immediately with 4003 code.
```

---

### [MEDIUM] — F13: Database Connection — Edge Gateway Uses Same Pool as API

**Severity:** MEDIUM
**CVSS Score:** 4.9
**CWE:** CWE-400: Uncontrolled Resource Consumption
**OWASP Category:** A05 — Security Misconfiguration
**Location:** SPEC.md §B.3.4

**Description:**
The SPEC specifies separate connection pools (20 API reads, 10 edge gateway writes) via PgBouncer. However, it does not specify separate database ROLES. If the edge gateway and the API use the same PostgreSQL role, the edge gateway has the same permissions as the API — including read access to core.users (password hashes), core.session (refresh token hashes), and the ability to INSERT into any table.

**Required specification:**
```
Database Roles (Principle of Least Privilege):
1. scada_app — used by FastAPI. SELECT/INSERT/UPDATE on all tables. No DELETE on audit_log.
2. scada_writer — used by edge gateway. INSERT-only on telemetry.* tables. SELECT on assets.* (for device lookups). No access to core.* or events.* or reports.*.
3. scada_reader — used by report worker. SELECT-only on all tables except core.password_reset and core.session.
4. All three roles are non-superuser, non-createdb, non-createrole.
```

---

### [LOW] — F14: uuid-ossp Extension Unnecessary

**Severity:** LOW
**CWE:** CWE-1104: Use of Unmaintained Third Party Components
**OWASP Category:** A06 — Vulnerable & Outdated Components
**Location:** 0001_initial.sql line 5

**Description:**
The migration loads `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`. PostgreSQL 13+ includes `gen_random_uuid()` natively (via pgcrypto). The uuid-ossp extension is maintained but adds unnecessary attack surface. New tables in 0001a already use `gen_random_uuid()`. The old tables still reference `uuid_generate_v4()` (functionally identical).

**Recommendation:** During Phase 1 setup, change existing table defaults to `gen_random_uuid()` and remove the uuid-ossp extension. Low priority — no security vulnerability, just unnecessary surface area.

---

### [LOW] — F15: No Specification for Security Headers Beyond CORS

**Severity:** LOW
**CWE:** CWE-693: Protection Mechanism Failure
**OWASP Category:** A05 — Security Misconfiguration
**Location:** SPEC.md §A.5

**Description:**
CORS is specified. The following security headers are not mentioned:

| Header | Required Value | Status |
|--------|---------------|--------|
| Content-Security-Policy | See F7 | NOT SPECIFIED |
| Strict-Transport-Security | max-age=63072000; includeSubDomains; preload | NOT SPECIFIED |
| X-Content-Type-Options | nosniff | NOT SPECIFIED |
| X-Frame-Options | DENY | NOT SPECIFIED (CSP frame-ancestors supersedes) |
| Referrer-Policy | strict-origin-when-cross-origin | NOT SPECIFIED |
| Permissions-Policy | camera=(), microphone=(), geolocation=() | NOT SPECIFIED |

**Recommendation:** Add a "Security Headers" section to SPEC.md A.5. These are single-line middleware configurations in FastAPI.

---

### [LOW] — F16: No Dependency Pinning or SBOM Requirement Specified

**Severity:** LOW
**CWE:** CWE-1395: Dependency on Vulnerable Third-Party Component
**OWASP Category:** A06 — Vulnerable & Outdated Components
**Location:** SPEC.md (not mentioned)

**Description:**
The SPEC specifies major versions (Python 3.12+, React 19, PostgreSQL 16) but does not require:
1. Lock files committed to repo (`poetry.lock`, `package-lock.json`)
2. Dependency audit in CI (`pip-audit`, `npm audit`)
3. Software Bill of Materials (SBOM) generation

**Recommendation:** Add to CI pipeline specification:
```
CI Security Gates:
1. pip-audit --require-hashes (Python dependencies)
2. npm audit --audit-level=high (Node dependencies)
3. Lock files (poetry.lock, package-lock.json) MUST be committed.
4. Renovate or Dependabot for automated dependency updates.
```

---

### [LOW] — F17: POPIA Compliance — Data Subject Rights Not Specified

**Severity:** LOW
**CWE:** CWE-359: Exposure of Private Personal Information to an Unauthorized Actor
**OWASP Category:** A01 — Broken Access Control
**Location:** SPEC.md Part E

**Description:**
The SPEC states "POPIA, GDPR-ready, 7-year audit retention." POPIA (Protection of Personal Information Act, South Africa) requires:

1. **Right of access:** Data subjects can request a copy of their personal data.
2. **Right to correction:** Data subjects can request correction of inaccurate data.
3. **Right to deletion:** Data subjects can request deletion (with exceptions for legal obligations).
4. **Data breach notification:** The Information Regulator must be notified within 72 hours of a breach.
5. **Purpose limitation:** Personal data collected for one purpose cannot be used for another.

The system stores personal data (email, full name, IP address, user agent, login timestamps) in `core.users` and `core.audit_log`. The 7-year audit retention conflicts with right-to-deletion unless justified by legal obligation (which it likely is for a safety-critical monitoring system, but this must be documented).

**Recommendation:** Add a POPIA compliance section to SPEC.md or a separate COMPLIANCE.md documenting: what personal data is collected, the legal basis for processing (legitimate interest — safety monitoring), the retention justification, and the process for data subject access requests. This is documentation, not code — but it should exist before the system goes live.

---

### [LOW] — F18: No Account Lockout Notification

**Severity:** LOW
**CWE:** CWE-307: Improper Restriction of Excessive Authentication Attempts
**OWASP Category:** A07 — Identification & Authentication Failures
**Location:** SPEC.md §C.1 step 3

**Description:**
The SPEC specifies "5 attempts → 15 min lock → audit log entry." It does not specify whether the locked-out user is notified (via email or in-app notification) that their account was locked due to failed attempts. Without notification, a legitimate user whose credentials are being brute-forced has no awareness of the attack.

**Recommendation:** Send an email notification on account lockout: "Your Kingswalk SCADA account was temporarily locked after multiple failed login attempts. If this wasn't you, contact your system administrator."

---

### [INFORMATIONAL] — F19: Argon2id Parameters Not Specified

**CWE:** CWE-916: Use of Password Hash With Insufficient Computational Effort
**OWASP Category:** A02 — Cryptographic Failures
**Location:** SPEC.md §C.1

**Description:**
The SPEC correctly specifies argon2id for password hashing (OWASP-recommended). It does not specify the parameters: memory cost, time cost, and parallelism. OWASP recommends: `m=19456 (19 MiB), t=2, p=1` as a minimum for argon2id.

**Recommendation:** Specify in SPEC.md or document in an ADR:
```
argon2id parameters: memory=65536 (64 MiB), time=3, parallelism=4
Rationale: higher than OWASP minimum; system has <30 users, so login latency is not a concern.
```

---

### [INFORMATIONAL] — F20: Redis Session Store — Persistence and Encryption at Rest

**CWE:** CWE-311: Missing Encryption of Sensitive Data
**OWASP Category:** A02 — Cryptographic Failures
**Location:** SPEC.md §B.3.6

**Description:**
Redis is used for session caching and real-time state. The SPEC specifies `appendfsync=everysec`. Redis stores data in memory and optionally on disk (AOF file). If Redis is managed (Railway Redis, AWS ElastiCache), encryption at rest and in transit is typically configurable but must be enabled explicitly.

**Recommendation:** Ensure the managed Redis instance has:
1. TLS for client connections (Redis 6+ supports TLS natively)
2. Encryption at rest enabled
3. AUTH password set (not default/no-password)

---

### [INFORMATIONAL] — F21: No Rate Limiting on API Endpoints Beyond Login

**CWE:** CWE-770: Allocation of Resources Without Limits or Throttling
**OWASP Category:** A04 — Insecure Design
**Location:** SPEC.md §A.5

**Description:**
Rate limiting is specified for login (5/15min) and implicitly for password reset (see F5). No rate limiting is specified for:
- Alarm acknowledgment endpoints
- Asset CRUD endpoints
- Report generation requests
- WebSocket message rate
- Telemetry ingestion rate (from edge gateway)

**Recommendation:** Add global API rate limiting (e.g., 100 requests/minute per authenticated user for REST, 1000 requests/minute for the edge gateway writer role) via FastAPI middleware or nginx.

---

### [INFORMATIONAL] — F22: TimescaleDB Retention Policy — Telemetry Deletion Without Archive

**CWE:** CWE-404: Improper Resource Shutdown or Release
**OWASP Category:** A09 — Security Logging & Monitoring Failures
**Location:** 0001_initial.sql lines 218–220

**Description:**
The migration sets retention policies: pq_sample at 90 days, breaker_state and lighting_state at 5 years. When chunks exceed the retention period, TimescaleDB drops them. The continuous aggregates (pq_1min, pq_15min, pq_hourly, pq_daily) survive, providing rolled-up data. However, raw pq_sample data is permanently lost after 90 days.

For a safety-critical system, consider whether 90-day raw PQ data is sufficient for incident investigation (e.g., a power quality event that is investigated 6 months later). The aggregates lose individual sample resolution.

**Recommendation:** Evaluate during commissioning whether 90-day raw retention is sufficient. If not, increase to 1 year (storage cost: ~50GB/year at the specified polling rate). This is a business decision, not a security vulnerability.

---

## Secrets Audit

**Status: No hardcoded secrets detected.**

All migrations contain only schema DDL and seed data (IP addresses for main boards, which are internal network addresses within the SCADA VLAN — not externally routable). No passwords, API keys, tokens, or connection strings appear in any specification or migration file.

The SPEC correctly mandates:
- Secrets in environment variables, never in code (A.5)
- Secrets manager for SMS/email API keys (A.5)
- Quarterly rotation (A.5)
- token_hash stored instead of raw tokens (core.password_reset, core.invite, core.session)
- argon2id for password hashing (C.1)

**Positive observation:** The schema stores only hashes of tokens and passwords, never raw values. This is correct.

---

## Security Headers Assessment

| Header | Specified | Value | Status |
|--------|-----------|-------|--------|
| CORS | Yes | "Vercel deployment domain only" | PASS |
| Content-Security-Policy | No | — | **FAIL** (see F7) |
| Strict-Transport-Security | No | — | **FAIL** (see F15) |
| X-Content-Type-Options | No | — | **FAIL** (see F15) |
| X-Frame-Options | No | — | **FAIL** (see F15) |
| Referrer-Policy | No | — | **FAIL** (see F15) |
| Permissions-Policy | No | — | **FAIL** (see F15) |

---

## SCADA-Specific Security Assessment

| Check | Status | Detail |
|--------|--------|--------|
| Modbus write prohibition | **SPECIFIED, NOT ENFORCED** | Policy stated in SPEC; code-level enforcement not specified (F8) |
| VPN as primary transport | **PASS** | WireGuard with keepalive and dual-path failover specified |
| Defence in depth (mTLS/API key) | **INCOMPLETE** | "or" decision not made (F6) |
| Edge gateway as trust boundary | **PASS** | Edge gateway is sole bridge; no direct field device access from cloud |
| Telemetry integrity | **PASS** | Idempotent writes, ON CONFLICT DO NOTHING, timestamp-based dedup |
| COMMS LOSS detection | **PASS** | 30-second watchdog, stale data warning at 2× poll interval |
| Data truth chain | **PASS** | Fully specified from register → edge → cloud → browser |
| Physical access separation | **PASS** | Monitoring only — no remote control capability exists in the system |

---

## Positive Security Observations

1. **Monitoring-only architecture:** The system's most important security property is correct by design — it cannot control physical equipment. No Modbus write function codes, no remote switching capability. This eliminates the highest-impact SCADA attack vector (unauthorized physical actuation).

2. **Defence-in-depth transport:** WireGuard VPN + mTLS/API key (when specified) + HTTPS provides three layers of transport security. Even if one layer is compromised, the others remain.

3. **Token hashing pattern:** All sensitive tokens (invite, password reset, session refresh) are stored as hashes, not plaintext. This is correct and consistently applied across all three lifecycle tables.

4. **Append-only audit log:** 7-year retention with no-delete policy provides forensic traceability. The audit log captures user_id, action, asset_id, payload, IP, and user_agent — comprehensive coverage.

5. **Argon2id for passwords:** OWASP-recommended algorithm, correct choice for 2026.

6. **RLS enabled on sensitive tables:** While policies are not yet defined (F2), the infrastructure (RLS enablement) is in place, which is the correct starting point.

7. **TimescaleDB retention policies:** Automated data lifecycle management prevents unbounded storage growth while preserving aggregated historical data.

8. **Separate schemas:** The 5-schema architecture (core, assets, telemetry, events, reports) provides logical separation that supports the principle of least privilege (F13) when combined with per-schema grants.

---

## Remediation Roadmap

### Immediate — Before Build Starts (Add to SPEC.md / BUILD_HANDOFF.md)

These are **specification clarifications** that the build session needs from day one:

| # | Finding | Action |
|---|---------|--------|
| F1 | MFA secret encryption | Add encryption specification to SPEC.md §B.4 and BUILD_HANDOFF.md §7 |
| F4 | JWT algorithm/validation | Add JWT standards section to SPEC.md §C.1 |
| F5 | Password reset security | Add rate limiting and enumeration protection to SPEC.md §C.1 |
| F6 | mTLS decision | Choose mTLS (not "or API key") in SPEC.md §A.5 |
| F8 | Modbus write enforcement | Add code-level enforcement specification to SPEC.md §2.1 |

### Phase 1 — During Auth Build (Week 1–3)

| # | Finding | Action |
|---|---------|--------|
| F2 | RLS policies | Define and implement concrete policies for all 10 RLS-enabled tables |
| F3 | CSRF protection | Specify token storage pattern and implement CSRF defence |
| F9 | Session fixation | Implement session regeneration, refresh rotation, role-change invalidation |
| F10 | Recovery codes | Add recovery_code table to migration; implement code generation and hashing |
| F11 | Audit log integrity | REVOKE DELETE/UPDATE on audit_log from scada_app role |
| F13 | DB role separation | Create scada_app, scada_writer, scada_reader roles with least-privilege grants |

### Phase 2 — During Edge Gateway Build (Week 4–8)

| # | Finding | Action |
|---|---------|--------|
| F6 | mTLS implementation | Generate CA, issue edge gateway client cert, configure FastAPI mTLS endpoint |
| F8 | ReadOnlyModbusClient | Implement wrapper, add unit tests, add CI grep check |
| F12 | WebSocket auth | Implement cookie-based WS auth with periodic session validation |

### Phase 7 — Hardening Sprint (Week 18)

| # | Finding | Action |
|---|---------|--------|
| F7 | CSP header | Configure CSP middleware in FastAPI |
| F15 | Security headers | Add all 6 security headers via middleware |
| F16 | Dependency pinning | Lock files, pip-audit, npm audit in CI |
| F17 | POPIA documentation | Create COMPLIANCE.md with data processing register |
| F14 | uuid-ossp cleanup | Migrate defaults, remove extension |

### Backlog — Track & Monitor

| # | Finding | Action |
|---|---------|--------|
| F18 | Lockout notification | Email on account lockout (nice-to-have) |
| F19 | Argon2id params | Document chosen parameters in ADR |
| F20 | Redis TLS | Confirm managed Redis config at deployment |
| F21 | Global rate limiting | Configure nginx/FastAPI rate limits |
| F22 | Retention review | Evaluate 90-day raw PQ retention during commissioning |

---

**END OF SECURITY AUDIT**
