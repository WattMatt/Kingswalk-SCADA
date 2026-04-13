# SPEC_FEEDBACK — Build → Arno Communication

This file is the build session's channel back to Arno (spec owner).
Any spec gaps, ambiguities, or blocking questions are recorded here.

Format:
## [DATE] — [TOPIC]
**Status:** BLOCKING / QUESTION / SUGGESTION
**Phase:** [Which phase]
**Detail:** [What you need]
**Workaround:** [What you're doing in the meantime]


## 2026-04-13 — Vercel Deployment (Task 8)
**Status:** READY TO DEPLOY
**Phase:** Sprint 0 PoC

**Local build verified:** Yes — `npm run build` produces clean output in `web/dist/`
**vercel.json:** Configured with `outputDirectory: web/dist`, SPA rewrite, `framework: null`

**To deploy (requires GitHub remote + Vercel account):**
1. Push the repo to GitHub: `git remote add origin https://github.com/YOUR_ORG/kingswalk-scada.git && git push -u origin main`
2. Import the repo at vercel.com → New Project → select `kingswalk-scada`
3. Vercel will detect `vercel.json` and use the configured build command
4. Set environment variables in Vercel dashboard (none required for frontend-only PoC)
5. Preview URL will be assigned automatically on each push to `main`

**API rewrite placeholder:** The `/api/(.*)` rewrite in `vercel.json` points to `https://api.placeholder.kingswalk.scada/api/$1` — update this to the real Railway/VPS API URL when backend is deployed.

**Sprint 0 gate status:**
- ✅ Working auth (26 backend tests passing)
- ✅ CI pipeline configured (GitHub Actions)
- ✅ Vercel config ready (pending GitHub push)
- ⏳ Vercel preview URL — pending GitHub remote setup and project import

## 2026-04-13 — 0001_initial.sql: CREATE MATERIALIZED VIEW inside transaction
**Status:** SUGGESTION
**Phase:** Phase 1 — Database
**Detail:** `db/migrations/0001_initial.sql` wraps everything in `BEGIN/COMMIT`, but `CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` cannot run inside a transaction block. The migration rolls back entirely when reached.
**Workaround:** Created `db/migrations/run_migrations.sh` helper that splits the migration at the continuous-aggregate boundary — running the core DDL in a transaction and the continuous aggregate + seed INSERTs outside it. The spec migration files are not modified.
