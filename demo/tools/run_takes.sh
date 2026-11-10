#!/usr/bin/env bash
# Records the three app takes in story order on the demo server (port 8002).
# A take is retried if the recommendation did not come from Gemini; the junk proposal from the failed
# attempt is removed from the demo database so the recorded history stays clean.
set -u
cd "$(dirname "$0")"
PY=../../backend/venv/Scripts/python

cleanup() {
  $PY - <<'PYEOF'
import sqlite3
c = sqlite3.connect("pact-demo.db", timeout=20)
ids = [r[0] for r in c.execute(
    "SELECT id FROM proposals WHERE status IN ('AWAITING_HUMAN_APPROVAL','HUMAN_APPROVED','APPROVAL_EXPIRED') "
    "AND created_at >= datetime('now','-10 minutes')")]
for i in ids:
    c.execute("DELETE FROM audit_logs WHERE entity_id = ?", (i,))
    c.execute("DELETE FROM proposals WHERE id = ?", (i,))
c.commit()
print(f"  removed {len(ids)} unfinished proposal(s) from the failed attempt")
PYEOF
}

record() {  # record <take> <done-marker> [extra args]
  local take=$1 marker=$2; shift 2
  for attempt in 1 2 3 4 5 6; do
    echo "=== $take attempt $attempt"
    node record.mjs "$take" "$@" 2>&1 | tail -4
    if grep -q "\"name\": \"$marker\"" "frames/$take/frames.json" 2>/dev/null; then return 0; fi
    cleanup
    sleep 25
  done
  echo "!!! $take failed after 6 attempts"; return 1
}

record app1 blocked_end || exit 1
sleep 20
record app2 captured_end --headed || exit 1
sleep 20
record app3 end || exit 1
echo "ALL TAKES RECORDED"
