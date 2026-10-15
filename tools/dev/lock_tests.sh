#!/usr/bin/env bash
# Write tests/LOCK.sha256: one "sha256  path" line per file under tests/ and selftest/.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
mkdir -p "$ROOT/tests"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
lock_manifest > "$tmp"
mv "$tmp" "$ROOT/tests/LOCK.sha256"; trap - EXIT
echo "lock_tests: wrote tests/LOCK.sha256 ($(wc -l < "$ROOT/tests/LOCK.sha256") files, sha $(sha256sum "$ROOT/tests/LOCK.sha256" | cut -c1-12))"
