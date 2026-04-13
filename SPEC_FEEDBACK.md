# SPEC_FEEDBACK — Build → Arno Communication

This file is the build session's channel back to Arno (spec owner).
Any spec gaps, ambiguities, or blocking questions are recorded here.

Format:
## [DATE] — [TOPIC]
**Status:** BLOCKING / QUESTION / SUGGESTION
**Phase:** [Which phase]
**Detail:** [What you need]
**Workaround:** [What you're doing in the meantime]

## 2026-04-13 — 0001_initial.sql: CREATE MATERIALIZED VIEW inside transaction
**Status:** SUGGESTION
**Phase:** Phase 1 — Database
**Detail:** `db/migrations/0001_initial.sql` wraps everything in `BEGIN/COMMIT`, but `CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` cannot run inside a transaction block. The migration rolls back entirely when reached.
**Workaround:** Created `db/migrations/run_migrations.sh` helper that splits the migration at the continuous-aggregate boundary — running the core DDL in a transaction and the continuous aggregate + seed INSERTs outside it. The spec migration files are not modified.
