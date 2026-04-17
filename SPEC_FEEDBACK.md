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

## 2026-04-15 — Demo Case Available for Bench Testing
**Status:** INFO
**Phase:** Phase 2 — Real-time Core

Demo case confirmed available:
- 3 Tmax XT breakers, each with Ekip Com Modbus TCP module on its own IP
- Data logger + digital signalling modules enabled
- Nearly all protection functions active

**What changed in the build:**
- Register comment convention updated: `# TODO: BENCH_TEST` (from ABB docs, unconfirmed) vs `# VERIFIED_REGISTER` (confirmed on demo hardware)
- `DEMO_MODE=true` env var added to `edge/main.py` — switches poller from 9 production MBs to 3 demo case Tmax XT devices
- `edge/edge.env.demo` added — copy and fill in the 3 Ekip Com IPs for your bench network (default: 192.168.0.100–102)
- All existing register addresses remain `# TODO: BENCH_TEST` until register map PDFs arrive

**Still needed (not yet available):**
- Register map PDFs: `1SDH002031A1101` (Tmax XT) and `1SDH001140R0001` (Emax 2)
- Actual bench network IPs for the 3 Ekip Com modules — update `DEMO_XT{1,2,3}_HOST` in `edge.env.demo`
- Site VLAN/IP assignments from Profection

**48V relay (Action 1) — still open.** Bypass detection design remains on hold until Profection confirms whether the relay has a readable digital/Modbus output. Due 2026-04-25.

## 2026-04-13 — 0001_initial.sql: CREATE MATERIALIZED VIEW inside transaction
**Status:** SUGGESTION
**Phase:** Phase 1 — Database
**Detail:** `db/migrations/0001_initial.sql` wraps everything in `BEGIN/COMMIT`, but `CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` cannot run inside a transaction block. The migration rolls back entirely when reached.
**Workaround:** Created `db/migrations/run_migrations.sh` helper that splits the migration at the continuous-aggregate boundary — running the core DDL in a transaction and the continuous aggregate + seed INSERTs outside it. The spec migration files are not modified.

## 2026-04-16 — MP4 measuring package has no breakers in extract
**Status:** QUESTION
**Phase:** Phase 2
**Detail:** The seed migration seeds measuring_package code='MP4' but `sld_per_mb_extract.json` has zero breakers with mp_code='MP4'. Every one of the 104 breakers uses MP2. Is the extract incomplete, or is MP4 reserved for future devices (M4M 30 incomer meters)?
**Workaround:** MP2 used for all 104 breakers. MP4 row seeded but unreferenced.

## 2026-04-16 — essential_supply and generator_bank not in extract
**Status:** QUESTION
**Phase:** Phase 2
**Detail:** The `assets.distribution_board` schema has `essential_supply` (boolean) and `generator_bank` ('A'|'B') columns, but `sld_per_mb_extract.json` contains no such classification. All DBs seeded with essential_supply=false, generator_bank=NULL. Which DBs are on essential supply / generator bank A or B? This is important for bypass detection (B.3.1 says ~40 tenants per bank).
**Workaround:** All distribution boards seeded without essential supply classification.

## 2026-04-16 — assets.main_board missing device IP columns vs SPEC.md B.4
**Status:** QUESTION
**Phase:** Phase 2
**Detail:** SPEC.md B.4 schema describes columns ekip_com_ip, m4m_1_ip, m4m_2_ip, switch_ip on assets.main_board, but these are absent from 0001_initial.sql DDL. The ORM model follows the actual DDL (correct). A schema migration is needed to add these columns if they are required for Phase 2 device polling.
**Workaround:** Per-VLAN device IPs are implicit from the scheme 10.10.{VLAN}.{host}: Ekip Com=.10, M4M#1=.100, M4M#2=.101, edge switch=.2. Columns can be added in 0005_mb_device_ips.sql.
