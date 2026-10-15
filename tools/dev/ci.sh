#!/usr/bin/env bash
# ci.sh [--quick]  Local CI skeleton. Runs check_lock first, then whichever layers exist.
# A layer is PASS, FAIL or SKIPPED (with reason). SKIPPED is never counted as pass.
# Exit: 0 = no failures and at least one layer passed; 1 = a layer failed; 3 = nothing passed (all skipped).
# Env: CI_REQUIRE_LOCK=1 makes a missing tests/LOCK.sha256 a FAIL instead of SKIPPED.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
quick=0
for a in "$@"; do case "$a" in --quick) quick=1;; *) echo "usage: ci.sh [--quick]" >&2; exit 2;; esac; done

cd "$ROOT" || exit 2
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="$ROOT/.harness/out/ci/$ts"; mkdir -p "$out"
rows=(); fails=0; passes=0; skips=0

record() { # name status detail
  rows+=("| $1 | $2 | $3 |")
  case "$2" in PASS) passes=$((passes+1));; FAIL) fails=$((fails+1));; *) skips=$((skips+1));; esac
  echo "ci: $1: $2${3:+ ($3)}"
}
run_layer() { # name cmd...
  local name="$1"; shift
  local t0=$SECONDS
  "$@" > "$out/$name.log" 2>&1; local rc=$?
  local d="rc=$rc, $((SECONDS-t0))s, log $name.log"
  if [ $rc -eq 0 ]; then record "$name" PASS "$d"
  elif [ $rc -eq 5 ]; then record "$name" PASS "$d, rc 5 = pass with warnings"
  else record "$name" FAIL "$d"; fi
  return 0
}

# Pick a pytest runner.
pytest_cmd=()
if [ -x "$ROOT/.venv/bin/pytest" ]; then pytest_cmd=("$ROOT/.venv/bin/pytest")
elif python3 -c 'import pytest' 2>/dev/null; then pytest_cmd=(python3 -m pytest); fi

has_tests() { [ -d "$1" ] && [ -n "$(find "$1" -type f -name 'test_*.py' -print -quit 2>/dev/null)" ]; }

pytest_layer() { # name dir
  local name="$1" dir="$2"
  if ! has_tests "$dir"; then record "$name" SKIPPED "no test_*.py under $dir"; return; fi
  if [ ${#pytest_cmd[@]} -eq 0 ]; then record "$name" SKIPPED "pytest not available"; return; fi
  local t0=$SECONDS
  "${pytest_cmd[@]}" "$dir" -q > "$out/$name.log" 2>&1; local rc=$?
  local d="rc=$rc, $((SECONDS-t0))s, log $name.log"
  case $rc in
    0) record "$name" PASS "$d";;
    5) record "$name" SKIPPED "pytest collected no tests";;
    *) record "$name" FAIL "$d";;
  esac
}

# 1. Lock check (always first).
"$DEV_DIR/check_lock.sh" > "$out/check_lock.log" 2>&1; rc=$?
case $rc in
  0) record check_lock PASS "log check_lock.log";;
  3) if [ "${CI_REQUIRE_LOCK:-0}" = 1 ]; then record check_lock FAIL "no tests/LOCK.sha256"; else record check_lock SKIPPED "no tests/LOCK.sha256 yet"; fi;;
  *) record check_lock FAIL "rc=$rc, log check_lock.log";;
esac

# 2. Layers.
pytest_layer unit tests/unit
pytest_layer contract tests/contract
h="$ROOT/tools/harness/h"
if [ $quick -eq 1 ]; then
  record gd_host SKIPPED "--quick"; record e2e SKIPPED "--quick"; record selftest SKIPPED "--quick"
else
  if [ -x "$h" ] && [ -d tests/fixtures/projects/gd_host ] && [ -f tools/harness/harness/verbs/test.py ]; then
    gd_tmp="${HARNESS_TMP:-$ROOT/.harness/tmp}/gd_host_$ts"; rm -rf "$gd_tmp"; mkdir -p "$gd_tmp"
    cp -a tests/fixtures/projects/gd_host/. "$gd_tmp/"
    run_layer gd_host "$h" test --project "$gd_tmp"
  else record gd_host SKIPPED "h test or gd_host fixture missing"; fi
  pytest_layer e2e tests/e2e
  if [ -x "$h" ] && [ -f tools/harness/harness/verbs/selftest.py ]; then
    run_layer selftest "$h" selftest
  else record selftest SKIPPED "h selftest verb missing"; fi
fi

if [ $fails -gt 0 ]; then verdict=FAIL; code=1
elif [ $passes -eq 0 ]; then verdict="NOTHING RAN (all layers skipped)"; code=3
else verdict=PASS; code=0; fi

{
  echo "# CI summary $ts"; echo
  echo "mode: $([ $quick -eq 1 ] && echo quick || echo full)"
  echo "verdict: **$verdict** ($passes passed, $fails failed, $skips skipped)"; echo
  echo "| layer | status | detail |"; echo "|---|---|---|"
  printf '%s\n' "${rows[@]}"
  echo; echo "SKIPPED layers did not run and are not passes."
} > "$out/summary.md"
echo "ci: $verdict ($passes passed, $fails failed, $skips skipped); summary: ${out#$ROOT/}/summary.md"
exit $code
