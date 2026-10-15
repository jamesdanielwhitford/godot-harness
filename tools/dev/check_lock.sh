#!/usr/bin/env bash
# Fail if any file under tests/ or selftest/ changed, was added or was removed since lock_tests.sh.
# Exit: 0 ok, 1 violation, 3 no lock file (distinct so ci.sh can report it as SKIPPED, not pass).
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
lock="$ROOT/tests/LOCK.sha256"
if [ ! -f "$lock" ]; then echo "check_lock: NO LOCK (tests/LOCK.sha256 missing)"; exit 3; fi
cur="$(mktemp)"; trap 'rm -f "$cur"' EXIT
lock_manifest > "$cur"
bad="$(python3 -I - "$lock" "$cur" <<'PY'
import sys
def load(p):
    d = {}
    for line in open(p, encoding="utf-8", errors="surrogateescape"):
        line = line.rstrip("\n")
        if line:
            h, _, path = line.partition("  ")
            d[path] = h
    return d
old, new = load(sys.argv[1]), load(sys.argv[2])
for p in sorted(set(old) | set(new)):
    if p not in new: print("REMOVED " + p)
    elif p not in old: print("ADDED   " + p)
    elif old[p] != new[p]: print("CHANGED " + p)
PY
)"
if [ -n "$bad" ]; then
  echo "check_lock: FAIL, locked tests differ from tests/LOCK.sha256:"; echo "$bad"; exit 1
fi
echo "check_lock: OK ($(wc -l < "$lock") files)"
