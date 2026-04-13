# Platform Design Addendum — Multi-User, Multi-Project, Document Management

**Version:** 1.0 (2026-04-13)
**Parent document:** SPEC.md v5.0
**Purpose:** Extend the Kingswalk SCADA GUI specification from a single-site monitoring tool to a multi-project platform that supports multiple users across multiple sites with document management and clean operational workflows. This document does not replace SPEC.md — it adds the platform layer that sits above the existing single-site monitoring architecture.

**Context:** The competitive analysis (COMPETITIVE_ANALYSIS.md) identified multi-site/portfolio scale as Kingswalk's largest capability gap versus platforms like KODE Labs. This addendum designs the architectural foundations for multi-project support while preserving Kingswalk's strengths: electrical distribution depth, bypass detection, PQ monitoring, and SA-specific context.

---

## 1. AUTHENTICATION SYSTEM DESIGN

### 1.1 Build vs Buy Decision

| Option | Fit | Verdict |
|---|---|---|
| **Supabase Auth** | Excellent — the spec already uses PostgreSQL, and Supabase Auth integrates natively with RLS via `auth.uid()`. Handles email/password, MFA (TOTP), magic links, password reset, session management. Eliminates custom JWT implementation risk. | **RECOMMENDED** |
| **Custom JWT (current spec)** | The existing C.1 lifecycle is well-designed but represents significant custom security surface area (argon2id hashing, token rotation, recovery codes, lockout logic). Every line is a potential vulnerability. | FALLBACK — only if Supabase Auth cannot meet a specific SCADA requirement |
| **Clerk** | Excellent DX but adds external dependency and cost. No SA data residency. | NOT RECOMMENDED |
| **Auth0** | Enterprise-grade but expensive for <30 users. Overkill for current scale. | NOT RECOMMENDED |

**Recommendation: Supabase Auth** with the following customisations:

- **MFA enforcement:** Supabase Auth supports TOTP MFA. Enforce at application level for Admin and Operator roles (middleware checks `amr` claim in JWT for `totp` factor).
- **Role storage:** Use Supabase Auth `app_metadata.role` for the global role, and a custom `project_memberships` table for per-project roles.
- **Invite flow:** Use Supabase Auth's `inviteUserByEmail()` admin function. Pre-assign role in `app_metadata`.
- **Recovery codes:** Supabase Auth does not provide recovery codes natively. Implement as a thin custom layer: generate and hash codes during MFA enrollment, store in `core.recovery_code` (already in schema).
- **Audit logging:** Supabase Auth emits webhook events for all auth actions. Pipe these to `core.audit_log` via a webhook handler.

> **Security note:** Using Supabase Auth means delegating password hashing, session management, and token rotation to a battle-tested implementation. The current spec's custom argon2id + JWT rotation design is sound but carries higher risk. Supabase Auth uses bcrypt for password hashing and handles refresh token rotation internally.

### 1.2 Multi-Project RBAC Model

The current spec defines three roles: `admin`, `operator`, `viewer`. For multi-project support, roles become **per-project** rather than global:

```
Global Level:
  └── platform_admin    — can create projects, manage all users, see all projects
  └── user              — standard user, access determined by project memberships

Project Level (per project_membership):
  └── project_admin     — full control within this project (asset CRUD, user invites, config)
  └── operator          — monitoring, acknowledge alarms, run reports within this project
  └── viewer            — read-only access to dashboards and reports within this project
```

**Key design decisions:**

1. A user can have different roles in different projects (e.g., admin on Kingswalk, viewer on another site).
2. `platform_admin` is a superuser role — limited to Watson Mattheus principals. Bypasses project-level checks.
3. Project-level roles map 1:1 to the existing SPEC.md RBAC permissions (C.1) — the permission set doesn't change, only the scope does.
4. A user with no project memberships sees an empty dashboard after login (no default access).

### 1.3 Authentication Flow (Supabase Auth)

```
┌──────────────────────────────────────────────────────────────┐
│  1. INVITE                                                    │
│     platform_admin or project_admin invites user by email     │
│     Supabase Auth sends magic-link email                      │
│     On first login: user sets password, enrolls MFA           │
│                                                               │
│  2. LOGIN                                                     │
│     Email + password → Supabase Auth                          │
│     → MFA challenge (TOTP) if Admin or Operator on any project│
│     → JWT issued (access: 15 min, refresh: 7 days)           │
│     → JWT contains: sub, email, app_metadata.global_role      │
│                                                               │
│  3. PROJECT SELECTION                                         │
│     After auth, frontend fetches project_memberships           │
│     If 1 project → auto-select and redirect to dashboard      │
│     If N projects → show project picker                       │
│     Selected project_id stored in session context              │
│                                                               │
│  4. AUTHORISATION (every API request)                         │
│     Middleware reads JWT (sub) + project_id from request       │
│     → Looks up project_membership for (user_id, project_id)   │
│     → Applies role-based permission check                     │
│     → RLS policies filter data to selected project            │
│                                                               │
│  5. WebSocket                                                 │
│     JWT passed via cookie during upgrade handshake             │
│     project_id included in subscription message                │
│     Server validates membership before streaming data          │
│     Periodic revalidation every 60s (existing spec)           │
└──────────────────────────────────────────────────────────────┘
```

### 1.4 Security Checklist (Auth Skill Compliance)

- [x] Provider solution evaluated and recommended (Supabase Auth)
- [x] Access tokens expire in 15 minutes
- [x] Refresh token rotation handled by Supabase Auth internally
- [x] Tokens stored in httpOnly cookies (Supabase SSR package)
- [x] Cookies use SameSite=Strict + Secure + httpOnly
- [x] Account lockout: Supabase Auth rate limits + custom lockout logic
- [x] User enumeration prevention: Supabase Auth default behaviour
- [x] Email verification flow: Supabase Auth handles this
- [x] Session invalidation on password change: Supabase Auth handles this
- [x] All auth events logged: webhook → core.audit_log
- [x] CSRF protection: SameSite=Strict cookies + double-submit pattern (existing spec)
- [x] No secrets hardcoded: all in Doppler (existing spec)
- [x] MFA: TOTP via Supabase Auth MFA, recovery codes via custom layer

---

## 2. MULTI-PROJECT DATABASE SCHEMA

### 2.1 Schema Strategy: Shared Database, Project-Scoped Tables

Three options were evaluated:

| Strategy | Pros | Cons | Verdict |
|---|---|---|---|
| **Database per project** | Complete isolation | Expensive, complex migrations, no cross-site queries | NO |
| **Schema per project** | Good isolation, PostgreSQL-native | Migration complexity, dynamic schema creation | NO |
| **Shared database with `project_id` FK** | Simple, enables cross-site analytics, single migration path | Must enforce isolation via RLS | **YES** |

The shared database approach aligns with the existing architecture (PostgreSQL + TimescaleDB + RLS) and enables the portfolio-scale analytics that KODE Labs offers as a differentiator.

### 2.2 New Tables

```sql
-- ============================================================
-- PLATFORM SCHEMA — Multi-project support
-- ============================================================

CREATE SCHEMA IF NOT EXISTS platform;

-- Projects (sites)
CREATE TABLE platform.project (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code            text UNIQUE NOT NULL,          -- e.g. 'kingswalk', 'mall-of-africa'
    name            text NOT NULL,                 -- Display name: 'Kingswalk Shopping Centre'
    address         text,
    city            text,
    province        text,
    country         text DEFAULT 'ZA',
    timezone        text NOT NULL DEFAULT 'Africa/Johannesburg',
    currency        text NOT NULL DEFAULT 'ZAR',
    logo_path       text,                          -- Path in object storage
    is_active       boolean DEFAULT true,
    config          jsonb DEFAULT '{}',            -- Project-specific settings
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    deleted_at      timestamptz
);

-- Project memberships (user ↔ project ↔ role)
CREATE TABLE platform.project_membership (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL,                 -- FK to auth.users (Supabase)
    project_id      uuid NOT NULL REFERENCES platform.project(id),
    role            text NOT NULL CHECK (role IN ('project_admin', 'operator', 'viewer')),
    invited_by      uuid,                          -- FK to auth.users
    accepted_at     timestamptz,
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (user_id, project_id)
);

CREATE INDEX CONCURRENTLY idx_membership_user ON platform.project_membership(user_id) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_membership_project ON platform.project_membership(project_id) WHERE is_active = true;

-- updated_at triggers for all platform tables
CREATE OR REPLACE FUNCTION platform.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_project_updated_at
    BEFORE UPDATE ON platform.project
    FOR EACH ROW EXECUTE FUNCTION platform.update_updated_at();

CREATE TRIGGER set_membership_updated_at
    BEFORE UPDATE ON platform.project_membership
    FOR EACH ROW EXECUTE FUNCTION platform.update_updated_at();

CREATE TRIGGER set_profile_updated_at
    BEFORE UPDATE ON platform.user_profile
    FOR EACH ROW EXECUTE FUNCTION platform.update_updated_at();

-- Platform-level user profiles (extends Supabase auth.users)
CREATE TABLE platform.user_profile (
    id              uuid PRIMARY KEY,              -- Same as auth.users.id
    full_name       text NOT NULL,
    phone           text,
    company         text,
    global_role     text NOT NULL DEFAULT 'user' CHECK (global_role IN ('platform_admin', 'user')),
    avatar_path     text,
    preferences     jsonb DEFAULT '{}',            -- UI preferences, notification settings
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- Auto-create profile on signup (Supabase trigger)
CREATE OR REPLACE FUNCTION platform.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO platform.user_profile (id, full_name)
    VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'full_name', 'New User'));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION platform.handle_new_user();
```

### 2.3 Adding `project_id` to Existing Tables

Every table that holds project-specific data gets a `project_id` column:

```sql
-- Add project_id to all existing asset and telemetry tables
ALTER TABLE assets.main_board       ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.breaker          ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.measuring_device ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.distribution_board ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.tenant_feed      ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.lighting_circuit ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.canvas           ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.canvas_layer     ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE assets.canvas_hotspot   ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);

ALTER TABLE telemetry.breaker_state ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE telemetry.pq_snapshot   ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE telemetry.energy_reading ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);
ALTER TABLE telemetry.alarm         ADD COLUMN project_id uuid NOT NULL REFERENCES platform.project(id);

ALTER TABLE core.audit_log          ADD COLUMN project_id uuid REFERENCES platform.project(id);
ALTER TABLE core.config             ADD COLUMN project_id uuid REFERENCES platform.project(id);

-- Add indexes for project-scoped queries (CONCURRENTLY for live DB safety)
CREATE INDEX CONCURRENTLY idx_main_board_project ON assets.main_board(project_id);
CREATE INDEX CONCURRENTLY idx_breaker_project ON assets.breaker(project_id);
CREATE INDEX CONCURRENTLY idx_measuring_device_project ON assets.measuring_device(project_id);
CREATE INDEX CONCURRENTLY idx_distribution_board_project ON assets.distribution_board(project_id);
CREATE INDEX CONCURRENTLY idx_tenant_feed_project ON assets.tenant_feed(project_id);
CREATE INDEX CONCURRENTLY idx_lighting_circuit_project ON assets.lighting_circuit(project_id);
CREATE INDEX CONCURRENTLY idx_canvas_project ON assets.canvas(project_id);
CREATE INDEX CONCURRENTLY idx_alarm_project ON telemetry.alarm(project_id);
CREATE INDEX CONCURRENTLY idx_pq_snapshot_project ON telemetry.pq_snapshot(project_id);
CREATE INDEX CONCURRENTLY idx_energy_reading_project ON telemetry.energy_reading(project_id);
CREATE INDEX CONCURRENTLY idx_breaker_state_project ON telemetry.breaker_state(project_id);
CREATE INDEX CONCURRENTLY idx_audit_log_project ON core.audit_log(project_id);
```

### 2.4 Row-Level Security Policies

```sql
-- RLS policy pattern: user can only see data for projects they are a member of
-- This function checks membership efficiently
CREATE OR REPLACE FUNCTION platform.user_has_project_access(p_project_id uuid)
RETURNS boolean AS $$
BEGIN
    -- Platform admins see everything
    IF EXISTS (
        SELECT 1 FROM platform.user_profile
        WHERE id = auth.uid() AND global_role = 'platform_admin'
    ) THEN
        RETURN true;
    END IF;

    -- Check active membership
    RETURN EXISTS (
        SELECT 1 FROM platform.project_membership
        WHERE user_id = auth.uid()
          AND project_id = p_project_id
          AND is_active = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- Apply to all asset tables (example for main_board)
ALTER TABLE assets.main_board ENABLE ROW LEVEL SECURITY;

CREATE POLICY project_isolation_select ON assets.main_board
    FOR SELECT USING (platform.user_has_project_access(project_id));

CREATE POLICY project_isolation_insert ON assets.main_board
    FOR INSERT WITH CHECK (platform.user_has_project_access(project_id));

CREATE POLICY project_isolation_update ON assets.main_board
    FOR UPDATE USING (platform.user_has_project_access(project_id));

-- Repeat for all project-scoped tables...
-- (In practice, generate these with a migration script that iterates over all tables with project_id)

-- Role-specific policies (example: only project_admin can modify assets)
CREATE OR REPLACE FUNCTION platform.user_has_project_role(p_project_id uuid, p_roles text[])
RETURNS boolean AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM platform.user_profile
        WHERE id = auth.uid() AND global_role = 'platform_admin'
    ) THEN
        RETURN true;
    END IF;

    RETURN EXISTS (
        SELECT 1 FROM platform.project_membership
        WHERE user_id = auth.uid()
          AND project_id = p_project_id
          AND role = ANY(p_roles)
          AND is_active = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- Only project_admin can INSERT/UPDATE/DELETE assets
CREATE POLICY admin_modify_assets ON assets.main_board
    FOR ALL USING (platform.user_has_project_role(project_id, ARRAY['project_admin']));
```

### 2.5 Migration Strategy

For the existing Kingswalk data (which has no `project_id`), the migration creates a default project and backfills:

```sql
-- Step 1: Create the Kingswalk project
INSERT INTO platform.project (id, code, name, city, province, timezone)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'kingswalk',
    'Kingswalk Shopping Centre',
    'Savannah',
    'Gauteng',
    'Africa/Johannesburg'
);

-- Step 2: Backfill all existing records
UPDATE assets.main_board SET project_id = '00000000-0000-0000-0000-000000000001';
UPDATE assets.breaker SET project_id = '00000000-0000-0000-0000-000000000001';
-- ... repeat for all tables

-- Step 3: Migrate existing core.users to platform model
-- Map existing users to project memberships
INSERT INTO platform.project_membership (user_id, project_id, role, accepted_at)
SELECT id, '00000000-0000-0000-0000-000000000001',
       CASE role
           WHEN 'admin' THEN 'project_admin'
           WHEN 'operator' THEN 'operator'
           WHEN 'viewer' THEN 'viewer'
       END,
       now()
FROM core.users WHERE is_active = true;
```

---

## 3. DOCUMENT MANAGEMENT SYSTEM

### 3.1 Document Categories

| Category | Examples | Access | Versioning |
|---|---|---|---|
| **Asset documents** | Datasheets, test certificates, commissioning photos, maintenance records | Per-project, all roles can view, project_admin can upload | Yes — keep all versions |
| **Project documents** | SLD drawings, floor plans, specifications, as-built drawings | Per-project, all roles can view, project_admin can upload | Yes — keep all versions |
| **Report outputs** | Monthly PQ reports, energy reports, alarm summaries | Per-project, generated by system, all roles can download | No — generated fresh each time |
| **Compliance documents** | POPIA records, audit certificates, safety compliance | Per-project, project_admin only for upload, platform_admin for cross-project view | Yes — regulatory retention |
| **User uploads** | Incident photos, field notes, maintenance logs | Per-project, operator and above can upload | No — append-only |

### 3.2 Storage Architecture

```
Object Storage (Supabase Storage or S3-compatible)
├── projects/
│   ├── {project_id}/
│   │   ├── assets/
│   │   │   ├── {asset_id}/
│   │   │   │   ├── datasheets/
│   │   │   │   ├── certificates/
│   │   │   │   ├── photos/
│   │   │   │   └── maintenance/
│   │   ├── drawings/
│   │   │   ├── sld/
│   │   │   └── floor-plans/
│   │   ├── reports/
│   │   │   ├── 2026-04/
│   │   │   └── 2026-05/
│   │   ├── compliance/
│   │   └── uploads/
│   │       ├── 2026-04-13/
│   │       └── ...
```

### 3.3 Database Schema for Documents

```sql
-- Document metadata table
CREATE TABLE platform.document (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES platform.project(id),
    category        text NOT NULL CHECK (category IN (
                        'asset_datasheet', 'asset_certificate', 'asset_photo',
                        'asset_maintenance', 'project_drawing', 'project_spec',
                        'report_output', 'compliance', 'user_upload'
                    )),
    title           text NOT NULL,
    description     text,
    file_name       text NOT NULL,                 -- Original filename
    file_path       text NOT NULL,                 -- Path in object storage
    file_size       bigint NOT NULL,               -- Bytes
    mime_type       text NOT NULL,                 -- e.g. 'application/pdf'
    checksum_sha256 text NOT NULL,                 -- Integrity verification

    -- Linkage
    asset_id        uuid,                          -- FK to relevant asset (NULL for project-level docs)
    asset_type      text,                          -- 'main_board', 'breaker', etc.

    -- Versioning
    version         int NOT NULL DEFAULT 1,
    previous_version_id uuid REFERENCES platform.document(id),
    is_current      boolean DEFAULT true,          -- Only one version is "current"

    -- Metadata
    tags            text[] DEFAULT '{}',           -- Searchable tags
    uploaded_by     uuid NOT NULL,                 -- FK to auth.users
    approved_by     uuid,                          -- FK to auth.users (for compliance docs)
    approved_at     timestamptz,

    -- Retention
    retention_policy text DEFAULT 'standard',      -- 'standard' (5 years), 'regulatory' (7 years), 'permanent'
    expires_at      timestamptz,                   -- Auto-calculated from retention_policy

    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    deleted_at      timestamptz                    -- Soft delete
);

CREATE INDEX CONCURRENTLY idx_document_project ON platform.document(project_id) WHERE deleted_at IS NULL;
CREATE INDEX CONCURRENTLY idx_document_asset ON platform.document(asset_id, asset_type) WHERE deleted_at IS NULL;
CREATE INDEX CONCURRENTLY idx_document_category ON platform.document(project_id, category) WHERE is_current = true;
CREATE INDEX CONCURRENTLY idx_document_tags ON platform.document USING GIN(tags);
CREATE INDEX CONCURRENTLY idx_document_uploaded_by ON platform.document(uploaded_by);

-- updated_at trigger
CREATE TRIGGER set_document_updated_at
    BEFORE UPDATE ON platform.document
    FOR EACH ROW EXECUTE FUNCTION platform.update_updated_at();

-- RLS
ALTER TABLE platform.document ENABLE ROW LEVEL SECURITY;

CREATE POLICY document_read ON platform.document
    FOR SELECT USING (platform.user_has_project_access(project_id));

CREATE POLICY document_upload ON platform.document
    FOR INSERT WITH CHECK (
        platform.user_has_project_role(project_id, ARRAY['project_admin', 'operator'])
    );

-- Only project_admin can soft-delete documents
CREATE POLICY document_delete ON platform.document
    FOR UPDATE USING (
        platform.user_has_project_role(project_id, ARRAY['project_admin'])
    );
```

### 3.4 Upload Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. User selects file + fills metadata (title, category,    │
│     optional asset link, tags)                               │
│                                                              │
│  2. Frontend validates:                                      │
│     - File size ≤ 50 MB                                     │
│     - Allowed MIME types: pdf, png, jpg, xlsx, docx, dwg    │
│     - File name sanitised (no path traversal)               │
│                                                              │
│  3. Frontend requests signed upload URL from API             │
│     → API checks: user has upload permission for project     │
│     → API generates pre-signed URL for object storage        │
│     → API returns: { uploadUrl, documentId }                 │
│                                                              │
│  4. Frontend uploads directly to object storage              │
│     (bypasses API server — no memory pressure)               │
│                                                              │
│  5. Frontend confirms upload complete to API                 │
│     → API verifies file exists in storage                    │
│     → API calculates SHA-256 checksum                        │
│     → API creates platform.document record                   │
│     → API logs to core.audit_log                             │
│                                                              │
│  6. If replacing existing document:                          │
│     → Previous version: is_current = false                   │
│     → New version: previous_version_id set, version = N+1   │
│     → Both versions retained in storage                      │
└─────────────────────────────────────────────────────────────┘
```

### 3.5 Download & Access

- All downloads go through the API (not direct object storage URLs) — this ensures RLS is checked.
- API generates short-lived (5-minute) signed URLs for the actual file download.
- Downloads are logged in `core.audit_log` with action `'document.download'`.
- Compliance documents require `approved_by` to be set before they are visible to non-admin users.

### 3.6 Allowed File Types

| MIME Type | Extension | Max Size | Category |
|---|---|---|---|
| `application/pdf` | .pdf | 50 MB | All |
| `image/png` | .png | 20 MB | Photos, drawings |
| `image/jpeg` | .jpg, .jpeg | 20 MB | Photos |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | .xlsx | 20 MB | Reports, schedules |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | .docx | 20 MB | Specs, reports |
| `image/vnd.dwg` | .dwg | 100 MB | CAD drawings |
| `application/zip` | .zip | 100 MB | Drawing packages |

### 3.7 Pending Uploads Table (Orphan Tracking)

```sql
-- Track uploads between presign and confirm to clean up orphans
CREATE TABLE platform.pending_upload (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES platform.project(id),
    user_id         uuid NOT NULL,                 -- FK to auth.users
    storage_key     text NOT NULL,
    filename        text NOT NULL,                 -- Sanitised filename
    content_type    text NOT NULL,                 -- Client-declared (not trusted)
    size_bytes      bigint NOT NULL,
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'expired')),
    expires_at      timestamptz NOT NULL,          -- 5 minutes from creation
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX CONCURRENTLY idx_pending_upload_expires ON platform.pending_upload(expires_at)
    WHERE status = 'pending';
```

### 3.8 Server-Side MIME Validation (Magic Bytes)

The client's `Content-Type` header is **never trusted**. After upload confirmation, the server reads the first 4KB of the file and validates using magic bytes:

```python
# Python implementation (FastAPI backend)
import magic  # python-magic library

MAGIC_BYTE_ALLOWED = {
    'application/pdf', 'image/png', 'image/jpeg',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/zip', 'image/vnd.dwg'
}

async def validate_uploaded_file(storage_key: str) -> str:
    """Read first 4KB, detect real MIME type from magic bytes. Returns detected MIME."""
    head_bytes = await storage.download_range(storage_key, start=0, end=4095)
    detected_mime = magic.from_buffer(head_bytes, mime=True)

    if detected_mime not in MAGIC_BYTE_ALLOWED:
        await storage.delete(storage_key)
        raise HTTPException(422, f"File type not allowed. Detected: {detected_mime}")

    return detected_mime
```

### 3.9 Filename Sanitisation

```python
import re
import unicodedata

def sanitise_filename(filename: str) -> str:
    """Remove path separators, special chars, normalise unicode."""
    # Normalise unicode
    filename = unicodedata.normalize('NFKD', filename)
    # Remove path separators and null bytes
    filename = filename.replace('/', '_').replace('\\', '_').replace('\x00', '')
    # Keep only safe characters
    filename = re.sub(r'[^\w\s\-.]', '', filename)
    # Collapse whitespace
    filename = re.sub(r'\s+', '_', filename.strip())
    # Limit length
    return filename[:200] if filename else 'unnamed'
```

### 3.10 Storage Quota Enforcement

| Scope | Quota | Enforcement Point |
|---|---|---|
| Per project | 10 GB (configurable in platform.project.config) | Presign endpoint checks sum(size_bytes) for project |
| Per user per project | 2 GB (configurable) | Presign endpoint checks sum(size_bytes) for user+project |
| Single file | 100 MB maximum (50 MB for images) | Presign endpoint rejects before URL generation |

### 3.11 Orphaned Upload Cleanup

A scheduled job runs hourly to clean up uploads that were presigned but never confirmed:

```python
# Cron job: every hour
async def cleanup_orphaned_uploads():
    expired = await db.fetch_all("""
        SELECT id, storage_key FROM platform.pending_upload
        WHERE status = 'pending' AND expires_at < now()
    """)
    for upload in expired:
        await storage.delete(upload['storage_key'])
        await db.execute("""
            UPDATE platform.pending_upload SET status = 'expired'
            WHERE id = :id
        """, {'id': upload['id']})
        logger.info('Cleaned orphaned upload', storage_key=upload['storage_key'])
```

### 3.12 Image Optimisation (for photos)

When an upload is confirmed and the detected MIME is `image/png` or `image/jpeg`:

1. Generate a thumbnail (300×300, webp, quality 70) — stored at `projects/{id}/thumbnails/{doc_id}.webp`
2. Optimise the original if >2MB (resize to max 2048px wide, convert to webp quality 85)
3. Store both the original and optimised version; `platform.document.file_path` points to the optimised version, with `metadata.original_path` preserving the raw upload

### 3.13 Virus Scanning

All uploads scanned with ClamAV before being made available. Files in quarantine are visible only to `platform_admin`. The scan runs as part of the confirm endpoint — if the file fails, it is deleted from storage and the pending_upload record is marked as `expired`.

---

## 4. OPERATIONAL WORKFLOW DESIGN

### 4.1 Project Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│  CREATE PROJECT                                              │
│  platform_admin creates project with:                        │
│  - Code, name, address, timezone                            │
│  - Upload site drawings (SLD, floor plan)                   │
│  - Configure edge gateway connection details                 │
│  - Assign initial project_admin                              │
│                                                              │
│  CONFIGURE ASSETS                                            │
│  project_admin populates the asset registry:                 │
│  - Import from SLD field map (xlsx) or manual entry          │
│  - Configure Modbus register maps per device                 │
│  - Set up canvas layers and hotspot positions                │
│  - Upload asset datasheets and certificates                  │
│                                                              │
│  COMMISSION                                                   │
│  project_admin verifies:                                     │
│  - Edge gateway is connected and polling                     │
│  - All Modbus registers returning expected values            │
│  - Alarms fire correctly (test mode)                         │
│  - Floor plan and SLD canvases render correctly              │
│                                                              │
│  OPERATE                                                     │
│  Invite operators and viewers.                               │
│  System enters normal monitoring mode.                       │
│  Monthly reports auto-generate.                              │
│  Document repository grows over time.                        │
│                                                              │
│  DECOMMISSION (if needed)                                    │
│  platform_admin sets project.is_active = false               │
│  Data retained per retention policy.                         │
│  Users lose access but audit trail preserved.                │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 User Workflow — Daily Operations

| Actor | Primary Workflow | Key Screens |
|---|---|---|
| **Platform Admin** | Create projects, manage cross-site users, view portfolio dashboard | Project list → Project settings → User management |
| **Project Admin** | Configure assets, manage project users, review alarms, approve compliance docs | Project dashboard → Asset registry → Documents → User management |
| **Operator** | Monitor live state, acknowledge alarms, upload field notes/photos, run reports | Dashboard → SLD canvas → Floor plan → Alarm list → Reports |
| **Viewer** | View dashboards, review reports, download documents | Dashboard → Reports → Documents (read-only) |

### 4.3 Project Picker & Navigation

After login, the user experience branches:

- **1 project:** Auto-redirect to that project's dashboard. No project picker shown.
- **Multiple projects:** Show project picker with cards showing: project name, location, active alarm count (red badge), last data timestamp. Click to enter.
- **Platform admin:** Additional "All Projects" option showing portfolio-level dashboard.

Within a project, the navigation stays exactly as specified in SPEC.md — SLD canvas, floor plan, alarm list, reports, settings. The `project_id` is embedded in the URL path: `/p/{project_code}/dashboard`, `/p/{project_code}/sld`, etc.

### 4.4 Notification Workflow

```
Event occurs (e.g. breaker trip, bypass alarm, comms loss)
    │
    ├─→ WebSocket broadcast to all connected clients for this project
    │
    ├─→ In-app notification badge (bell icon, count)
    │
    ├─→ Check notification preferences per user:
    │       - Email: immediate for CRITICAL, digest for WARNING
    │       - Push (PWA): immediate for CRITICAL
    │       - SMS: CRITICAL only (optional, configurable)
    │
    └─→ Audit log entry
```

### 4.5 Report Workflow

Reports are generated per-project on a configurable schedule (default: monthly on the 1st):

1. Cron job triggers report generation for each active project.
2. Report worker (using `scada_reader` DB role) queries project-scoped data.
3. PDF/CSV generated and stored in `projects/{project_id}/reports/{yyyy-mm}/`.
4. `platform.document` record created (category: `report_output`).
5. Notification sent to all project members with Operator+ role.
6. Report visible in the project's Reports section.

### 4.6 Cross-Project Analytics (Portfolio View)

Available to `platform_admin` only:

| Metric | Description |
|---|---|
| Active alarms by project | Bar chart showing alarm count per project, colour-coded by severity |
| Power quality summary | Table showing average PF, max THD, voltage deviation per project |
| Energy consumption comparison | Stacked bar chart: kWh per project per month |
| Uptime / comms reliability | Percentage of successful polls per project |
| Document compliance status | Which projects have up-to-date certificates, which are expiring |

---

## 5. API DESIGN PATTERNS

### 5.1 URL Structure

```
/api/v1/auth/...                          — Authentication (Supabase handles most)
/api/v1/platform/projects                  — List user's projects
/api/v1/platform/projects/{code}           — Project details
/api/v1/platform/projects/{code}/members   — Project membership management

/api/v1/p/{project_code}/assets/...        — Asset CRUD (project-scoped)
/api/v1/p/{project_code}/telemetry/...     — Telemetry queries (project-scoped)
/api/v1/p/{project_code}/alarms/...        — Alarm management (project-scoped)
/api/v1/p/{project_code}/documents/...     — Document management (project-scoped)
/api/v1/p/{project_code}/reports/...       — Report generation & download (project-scoped)
/api/v1/p/{project_code}/config/...        — Project configuration (project-scoped)

/api/v1/portfolio/...                      — Cross-project analytics (platform_admin only)
```

### 5.2 Middleware Stack

```
Request
  → Rate limiter (per IP + per user)
  → JWT validation (Supabase Auth)
  → Extract user_id from JWT
  → Extract project_code from URL path
  → Lookup project_membership(user_id, project_id)
  → Set request context: { user, project, role }
  → Route handler (uses context for authorisation decisions)
  → Audit log (async, non-blocking)
Response
```

### 5.3 Permission Matrix

| Action | platform_admin | project_admin | operator | viewer |
|---|---|---|---|---|
| Create project | ✅ | ❌ | ❌ | ❌ |
| Delete project | ✅ | ❌ | ❌ | ❌ |
| Invite users to project | ✅ | ✅ | ❌ | ❌ |
| Change user role in project | ✅ | ✅ | ❌ | ❌ |
| View dashboard | ✅ | ✅ | ✅ | ✅ |
| View SLD / floor plan | ✅ | ✅ | ✅ | ✅ |
| View alarms | ✅ | ✅ | ✅ | ✅ |
| Acknowledge alarms | ✅ | ✅ | ✅ | ❌ |
| CRUD assets | ✅ | ✅ | ❌ | ❌ |
| Upload documents | ✅ | ✅ | ✅ | ❌ |
| Delete documents | ✅ | ✅ | ❌ | ❌ |
| Download documents | ✅ | ✅ | ✅ | ✅ |
| Approve compliance docs | ✅ | ✅ | ❌ | ❌ |
| Generate reports | ✅ | ✅ | ✅ | ❌ |
| Download reports | ✅ | ✅ | ✅ | ✅ |
| Configure project settings | ✅ | ✅ | ❌ | ❌ |
| View portfolio analytics | ✅ | ❌ | ❌ | ❌ |
| Configure alarm thresholds | ✅ | ✅ | ❌ | ❌ |
| Force-logout users | ✅ | ✅ (own project) | ❌ | ❌ |

---

## 6. IMPLEMENTATION PHASING

This platform layer does NOT need to ship with R1. The recommended approach:

| Phase | What Ships | Multi-Project Status |
|---|---|---|
| **R1 (current build)** | Single-site Kingswalk monitoring | `project_id` column present but hardcoded to Kingswalk. No project picker. No document upload UI (backend ready). |
| **R1.5 (post-launch)** | Document upload UI, Supabase Auth migration | Migrate from custom JWT to Supabase Auth. Add document upload/download for the single project. |
| **R2** | Multi-project foundations | Project picker, project CRUD, membership management. Second site onboarded. |
| **R3** | Portfolio analytics, full document management | Cross-project dashboards, compliance workflow, retention automation. |

**Key R1 preparation:** Even though multi-project UI doesn't ship in R1, the database schema should include `project_id` on all tables from day one. Adding it later requires a data migration across all tables — doing it now costs nothing.

---

## 7. RELATIONSHIP TO EXISTING SPEC

| SPEC.md Section | Impact of This Addendum |
|---|---|
| C.1 (Auth lifecycle) | **Replaced** by Supabase Auth flow (§1.3 above). Recovery codes remain custom. |
| B.4 (Database schema) | **Extended** with `platform` schema and `project_id` columns on all existing tables. |
| C.2 (Asset management) | **Extended** with document upload/versioning (§3). Asset CRUD now project-scoped. |
| C.3-C.5 (Monitoring, logging, reporting) | **Scoped** to project_id. No functional changes. |
| C.6 (Alerting) | **Scoped** to project_id. Notification preferences now per-user-per-project. |
| D.1 (Deployment) | **Extended** with Supabase project setup. Object storage bucket configuration. |
| Security (A.5) | **Simplified** by delegating auth to Supabase. RLS policies more robust with project isolation. |

---

---

## 8. ARCHITECTURE REVIEW — PLATFORM LAYER

### Assumptions
- Tech stack: FastAPI (Python) + PostgreSQL/TimescaleDB + Supabase Auth + Redis + Railway hosting
- Scale target: 5 projects, 50 users, 500 assets within 12 months. Long-term: 50 projects, 500 users
- Team size: 1 developer (Claude Code) + 1 engineer (Arno) — monolith is appropriate, microservices are not
- Edge gateways: 1 per project, polling Modbus devices and pushing to cloud

### TIER 1 — Fix Before Launch

#### F1: RLS Subquery Performance on Telemetry Tables
**Component:** PostgreSQL RLS / `platform.user_has_project_access()`
**Problem:** The RLS function performs a subquery against `platform.project_membership` for every row evaluated. On telemetry tables with millions of rows (pq_snapshot, breaker_state), this creates a nested loop — effectively a full table scan risk.
**Failure Condition:** ~1M rows in pq_snapshot with 5+ concurrent dashboard users.
**Impact:** Dashboard timeouts, slow page loads, database CPU spikes.
**Recommendation:** Cache the user's accessible project_ids in the JWT claims (`app_metadata.project_ids`) via a Supabase Auth hook. RLS policy becomes a simple array-contains check: `USING (project_id = ANY(string_to_array(current_setting('app.project_ids'), ',')::uuid[]))`. Set the session variable in middleware before each request. This avoids the subquery entirely.
**Effort:** Medium (2-3 days)

#### F2: Supabase Auth as Single Point of Failure
**Component:** Authentication
**Problem:** If Supabase Auth is unreachable, no user can log in, refresh tokens, or authenticate API requests. All WebSocket connections will fail revalidation within 60 seconds.
**Failure Condition:** Supabase outage (has occurred historically) or network partition between Railway and Supabase.
**Impact:** Complete system lockout for all users across all projects.
**Recommendation:** (a) Cache validated JWT public keys locally — even if Supabase is down, existing access tokens (up to 15 min) continue working. (b) Implement a circuit breaker on auth validation — if Supabase is unreachable for >30s, extend existing session validity by 15 minutes (degraded mode). (c) Monitor Supabase status endpoint in health check.
**Effort:** Medium (2-3 days)

### TIER 2 — Fix Before Growth

#### F3: Object Storage Download Without CDN
**Component:** Document management / file downloads
**Problem:** All document downloads go through the API for RLS checking, then redirect to signed URLs. Without a CDN, every download hits the origin object storage directly. For large files (100MB CAD drawings), this creates bandwidth pressure on the storage origin.
**Failure Condition:** 10+ concurrent downloads of large files.
**Impact:** Slow downloads, potential storage throttling.
**Recommendation:** Put Cloudflare CDN (already in spec for the web app) in front of signed storage URLs. Signed URLs with short TTL (5 min) ensure CDN caching is bounded. Cloudflare caches on the signed URL including the expiry parameter.
**Effort:** Small (1 day)

#### F4: No Connection Pool Sizing for Multi-Project
**Component:** PostgreSQL / PgBouncer
**Problem:** With Supabase's PgBouncer in transaction mode, the connection pool is shared across all projects. A burst of activity on one project (e.g., edge gateway pushing 104 asset readings simultaneously) could exhaust the pool for all projects.
**Failure Condition:** 3+ edge gateways pushing telemetry concurrently + 10+ dashboard users.
**Impact:** Database connection timeouts, failed API requests.
**Recommendation:** (a) Set `pool_size` in FastAPI's async database driver to match Supabase's plan limit (typically 50-60 connections on Pro). (b) Edge gateway writes should batch inserts (INSERT ... VALUES (...), (...), ...) to minimise connection hold time. (c) Use a separate connection pool for read-only report queries (via the `scada_reader` role).
**Effort:** Small (1 day)

#### F5: Missing Rate Limiting on Document Upload
**Component:** File upload endpoints
**Problem:** A malicious or misconfigured client could flood the presign endpoint, creating thousands of pending uploads and filling object storage.
**Failure Condition:** Automated script hitting /uploads/presign at high rate.
**Impact:** Storage quota exhaustion, orphan cleanup job overwhelmed.
**Recommendation:** Rate limit presign endpoint: 10 requests per user per minute, 50 per project per minute. Separate from general API rate limits.
**Effort:** Small (<1 day)

### TIER 3 — Fix for Long-Term

#### F6: No Read Replica for Reporting
**Component:** Database
**Problem:** Monthly report generation queries large time ranges of telemetry data. On a single-writer database, heavy report queries compete with real-time telemetry writes and dashboard reads.
**Failure Condition:** Monthly report generation for 10+ projects running simultaneously.
**Impact:** Dashboard latency increases during report generation window.
**Recommendation:** When project count exceeds 10, add a PostgreSQL read replica for the report worker (`scada_reader` role). Railway supports read replicas. Route all reporting queries to the replica.
**Effort:** Medium (3-5 days when needed)

#### F7: WebSocket Fan-Out for Multi-Project
**Component:** Real-time updates
**Problem:** Current spec uses a single WebSocket server broadcasting to all connected clients. With multi-project, the server must filter broadcasts by project_id. At scale, a single server becomes a bottleneck.
**Failure Condition:** 50+ concurrent WebSocket connections across 10+ projects.
**Impact:** Broadcast latency increases, server memory grows with connection count.
**Recommendation:** Use Redis pub/sub as the WebSocket broadcast backbone. Each project gets a Redis channel (`ws:project:{id}`). WebSocket servers subscribe only to channels for connected clients. This enables horizontal scaling of WebSocket servers behind a load balancer.
**Effort:** Large (1-2 weeks when needed)

### CAP Theorem Trade-Off Summary

| Data Store | Trade-off | Appropriate? |
|---|---|---|
| PostgreSQL (primary) | CP — consistent and partition-tolerant, sacrifices availability during failover | **Yes** — SCADA monitoring data must be consistent. A brief unavailability during failover is acceptable vs serving stale/incorrect breaker states. |
| Redis (sessions + cache) | AP — available and partition-tolerant, eventual consistency | **Yes** — session cache can be eventually consistent. Worst case: a session is valid for up to 60 seconds after revocation (existing spec). |
| TimescaleDB (telemetry) | CP — same as PostgreSQL (it's an extension) | **Yes** — telemetry must be consistent. Missing data is preferable to incorrect data (data truth chain). |
| Object Storage (documents) | AP — highly available, eventually consistent reads | **Yes** — documents are immutable once uploaded. Eventual consistency is fine. |

### Cost Efficiency Notes

- **Supabase Auth free tier** covers up to 50,000 monthly active users — more than sufficient for the foreseeable scale (50-500 users). No additional auth cost.
- **Object storage**: Supabase Storage on Pro plan includes 100GB. At projected usage (10 projects × ~2GB documents each), this fits within plan limits for the first 1-2 years.
- **Railway compute**: A single Railway service handles API + WebSocket for up to ~50 concurrent users. Only split into separate services when WebSocket connections exceed ~200.
- **Avoid premature scaling**: Do not add read replicas, Redis pub/sub fan-out, or separate WebSocket servers until the specific failure conditions above are observed in monitoring.

---

## 9. SCHEMA DESIGN DECISIONS

### Decision 1: Shared Database with project_id (not schema-per-tenant)
**What:** All projects share a single set of tables, isolated by `project_id` + RLS.
**Why:** Enables cross-project analytics (portfolio view), single migration path, no dynamic schema creation. Aligns with existing PostgreSQL + TimescaleDB architecture.
**Alternative considered:** Schema-per-tenant (PostgreSQL schemas) — stronger isolation but migration complexity grows linearly with project count. Database-per-tenant — maximum isolation but no cross-site queries and expensive infrastructure.
**Trade-off:** Relies entirely on RLS for data isolation. A misconfigured policy could leak data across projects. Mitigation: comprehensive RLS test suite as part of CI.

### Decision 2: Supabase Auth over custom JWT
**What:** Delegate authentication to Supabase Auth, extending with custom recovery codes and audit webhook.
**Why:** Reduces custom security surface area. The existing SPEC.md C.1 auth lifecycle is well-designed but every line is a potential vulnerability. Supabase Auth handles password hashing, token rotation, session management, and MFA out of the box.
**Alternative considered:** Keep custom argon2id + JWT rotation as specified in SPEC.md v5.0.
**Trade-off:** Dependency on Supabase. If Supabase is abandoned or pricing changes, auth must be migrated. Mitigation: Supabase is open-source — self-hosting is possible.

### Decision 3: text with CHECK for roles (not PostgreSQL ENUM)
**What:** `role text NOT NULL CHECK (role IN ('project_admin', 'operator', 'viewer'))` instead of `CREATE TYPE role_enum AS ENUM(...)`.
**Why:** Roles will evolve as the platform matures (e.g., adding 'maintenance_tech', 'auditor'). Adding values to a CHECK constraint is a simple ALTER, while ENUM changes require type manipulation.
**Alternative considered:** PostgreSQL ENUM — more type-safe, slightly more storage-efficient.
**Trade-off:** Less type safety in application code. Mitigated by TypeScript/Python type definitions generated from the schema.

### Decision 4: UUID PKs everywhere (including platform tables)
**What:** All primary keys are `uuid DEFAULT gen_random_uuid()`.
**Why:** Safe to generate client-side (offline-capable edge gateways), globally unique across projects, don't reveal row counts or creation order.
**Alternative considered:** bigserial for high-volume telemetry tables (pq_snapshot, breaker_state) where sequential IDs are more index-efficient.
**Trade-off:** UUIDs use 16 bytes vs 8 for bigint. For telemetry tables with millions of rows, this adds ~8 bytes per row overhead. Acceptable at current scale; revisit if a single project exceeds 100M telemetry rows.

### Decision 5: Soft delete on projects and documents (hard delete on telemetry)
**What:** `deleted_at timestamptz` on platform.project, platform.document, and all asset tables. No soft delete on telemetry tables.
**Why:** Projects and documents must be recoverable (regulatory retention). Telemetry is append-only with time-based retention managed by TimescaleDB retention policies.
**Alternative considered:** Soft delete on everything — simpler model but wastes storage on immutable telemetry.
**Trade-off:** Two deletion patterns in the codebase. Mitigated by clear documentation: "if table has `deleted_at`, use soft delete; if not, data is managed by retention policy."

---

## 9. SCHEMA EVOLUTION NOTES

**Easy to add (no table rewrite):**
- New columns on any table (ADD COLUMN ... DEFAULT NULL is instant)
- New tables in the platform schema
- New role values (ALTER table CHECK constraint)
- New document categories (ALTER table CHECK constraint)
- New indexes (CREATE INDEX CONCURRENTLY)
- New RLS policies

**Requires careful migration:**
- Changing `project_id` from nullable to NOT NULL on existing tables with data (must backfill first)
- Adding composite unique constraints on tables with duplicate data
- Changing column types (e.g., text → jsonb) — requires table rewrite on large tables

**Would require significant refactoring:**
- Moving from shared-database to schema-per-tenant isolation — effectively a new architecture
- Replacing Supabase Auth with a different provider — all JWT claims, RLS functions, and middleware change
- Adding hierarchical projects (project → sub-project) — the flat project model assumes one level

**Planned extensions (designed to be easy):**
- Adding `project_group` or `portfolio` table for grouping projects — just a new FK on platform.project
- Adding notification preferences per user per project — new table with (user_id, project_id) composite key
- Adding project-level config overrides — platform.project.config JSONB field already exists
- Adding document approval workflows — extend platform.document with workflow state columns

---

*This document should be reviewed alongside SPEC.md v5.0, COMPETITIVE_ANALYSIS.md, and the auth-system-builder, data-schema-designer, and file-upload-handler skill best practices.*
