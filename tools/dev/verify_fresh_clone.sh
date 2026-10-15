#!/usr/bin/env bash
# verify_fresh_clone.sh <branch> [dir]
# Clone the pushed remote branch into a fresh dir (default: $VERIFY_DIR or a new dir under
# ${CLAUDE_SCRATCHPAD:-${TMPDIR:-/tmp}}), run tools/bootstrap.sh if present, then tools/dev/ci.sh.
# Remote: $VERIFY_REMOTE, else this repo's `origin`. Exit code is ci.sh's (2 on usage/clone error).
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
if [ $# -lt 1 ] || [ $# -gt 2 ]; then echo "usage: verify_fresh_clone.sh <branch> [dir]" >&2; exit 2; fi
branch="$1"
remote="${VERIFY_REMOTE:-$(git -C "$ROOT" remote get-url origin 2>/dev/null || true)}"
[ -n "$remote" ] || { echo "verify_fresh_clone: no remote (set VERIFY_REMOTE)" >&2; exit 2; }
dir="${2:-${VERIFY_DIR:-}}"
if [ -z "$dir" ]; then
  base="${CLAUDE_SCRATCHPAD:-${TMPDIR:-/tmp}}"; mkdir -p "$base"
  dir="$(mktemp -d "$base/verify-clone-XXXXXX")"
fi
if [ -e "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then echo "verify_fresh_clone: $dir is not empty" >&2; exit 2; fi
mkdir -p "$dir"
if ! git clone -q --branch "$branch" --single-branch "$remote" "$dir" 2> "$dir.clone.err"; then
  echo "verify_fresh_clone: clone of '$branch' from $remote failed: $(head -c 300 "$dir.clone.err")" >&2; rm -f "$dir.clone.err"; exit 2
fi
rm -f "$dir.clone.err"
commit="$(git -C "$dir" rev-parse --short HEAD)"
boot=skipped
if [ -x "$dir/tools/bootstrap.sh" ]; then
  if (cd "$dir" && tools/bootstrap.sh > .bootstrap.log 2>&1); then boot=ok; else boot="FAILED (see $dir/.bootstrap.log)"; fi
fi
if [ "$boot" != "ok" ] && [ "$boot" != skipped ]; then
  echo "verify_fresh_clone: $branch@$commit in $dir: bootstrap $boot"; exit 1
fi
if [ ! -x "$dir/tools/dev/ci.sh" ]; then echo "verify_fresh_clone: no tools/dev/ci.sh in clone" >&2; exit 2; fi
ci_out="$(cd "$dir" && HARNESS_ROOT= tools/dev/ci.sh 2>&1)"; rc=$?
echo "verify_fresh_clone: $branch@$commit dir=$dir bootstrap=$boot ci_rc=$rc"
printf '%s\n' "$ci_out" | tail -n 12
exit $rc
