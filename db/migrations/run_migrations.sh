#!/usr/bin/env bash
# Run Kingswalk SCADA migrations in the correct order.
#
# 0001_initial.sql wraps everything in BEGIN/COMMIT, but
# CREATE MATERIALIZED VIEW WITH (timescaledb.continuous) cannot run inside a
# transaction block.  This script:
#   1. Runs 0001_initial.sql with the continuous-aggregate block skipped.
#   2. Runs 0001_cont_agg.sql (continuous aggregate, no transaction wrapper).
#   3. Runs 0001a_schema_review_fixes.sql.
#
# Usage:
#   export DOCKER_HOST=unix://$HOME/.rd/docker.sock
#   DBNAME=kingswalk_scada       ./db/migrations/run_migrations.sh
#   DBNAME=kingswalk_scada_test  ./db/migrations/run_migrations.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../../docker-compose.yml"
DBNAME="${DBNAME:-kingswalk_scada}"
DBUSER="${DBUSER:-scada}"

psql_exec() {
    docker compose -f "${COMPOSE_FILE}" exec -T db \
        psql -U "${DBUSER}" -d "${DBNAME}" -v ON_ERROR_STOP=1 "$@"
}

echo "==> [1/3] 0001_initial.sql (minus continuous aggregates) → ${DBNAME}"
# Strip the CREATE MATERIALIZED VIEW block (lines between the two comments)
# by excluding lines 223-234 using sed ranges keyed on unique strings.
INITIAL_NO_CAGG=$(sed '/^CREATE MATERIALIZED VIEW telemetry\.pq_1min/,/^GROUP BY device_id, bucket;$/d' \
    "${SCRIPT_DIR}/0001_initial.sql")

psql_exec -f /dev/stdin <<< "${INITIAL_NO_CAGG}"
echo "    done."

echo "==> [2/3] 0001_cont_agg.sql (continuous aggregate) → ${DBNAME}"
psql_exec -f /dev/stdin < "${SCRIPT_DIR}/0001_cont_agg.sql"
echo "    done."

echo "==> [3/3] 0001a_schema_review_fixes.sql → ${DBNAME}"
psql_exec -f /dev/stdin < "${SCRIPT_DIR}/0001a_schema_review_fixes.sql"
echo "    done."

echo ""
echo "All migrations applied successfully to ${DBNAME}."
