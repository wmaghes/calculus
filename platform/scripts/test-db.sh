#!/usr/bin/env bash
# Applies every migration to a throwaway local Postgres and runs the RLS tests.
# Needs Postgres server binaries (initdb, pg_ctl) and psql on the machine.
set -euo pipefail

cd "$(dirname "$0")/.."
PG_BIN="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)}"
PG_BIN="${PG_BIN:-$(dirname "$(command -v initdb)")}"
DATA="$(mktemp -d)"
PORT="${PORT:-54329}"
RUN_AS=()
if [ "$(id -u)" = "0" ]; then
  chown -R postgres "$DATA"
  RUN_AS=(runuser -u postgres --)
fi

cleanup() { "${RUN_AS[@]}" "$PG_BIN/pg_ctl" -D "$DATA" stop -m fast >/dev/null 2>&1 || true; rm -rf "$DATA"; }
trap cleanup EXIT

"${RUN_AS[@]}" "$PG_BIN/initdb" -D "$DATA" -U postgres >/dev/null
"${RUN_AS[@]}" "$PG_BIN/pg_ctl" -D "$DATA" -o "-p $PORT -k /tmp" -l "$DATA/log" start >/dev/null

PSQL=(psql -h /tmp -p "$PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 -q)
"${PSQL[@]}" -f supabase/tests/local/auth_stub.sql
for f in supabase/migrations/*.sql; do
  echo "apply $f"
  "${PSQL[@]}" -f "$f"
done
"${PSQL[@]}" -f supabase/tests/local/rls_test.sql 2>&1 | sed 's/^psql:[^ ]* NOTICE:  //'
