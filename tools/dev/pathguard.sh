#!/usr/bin/env bash
# pathguard.sh <role> <area> <range-or-working-tree>
# Enforce the plan 5.1 write allowlists. Lists out-of-allowlist paths, exits 1 if any (2 on usage error).
#   role:  orchestrator planner spec-reviewer test-writer builder verifier adjudicator
#   area:  area id or slug as used in .claude/handoff/<area>/ and tests/*/<area>/ (case-insensitive)
#   third: a git range (base..HEAD) or "working-tree" (uncommitted + untracked, vs HEAD)
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
if [ $# -ne 3 ]; then echo "usage: pathguard.sh <role> <area> <range|working-tree>" >&2; exit 2; fi
role="$1"; area="$2"; target="$3"
case "$area" in *[!A-Za-z0-9_.-]*|"") echo "pathguard: bad area '$area'" >&2; exit 2;; esac
A="$(printf '%s' "$area" | tr 'A-Z' 'a-z')"

cd "$ROOT" || exit 2
if [ "$target" = "working-tree" ] || [ "$target" = "wt" ]; then
  paths="$( { git -c core.quotepath=off diff --name-only --no-renames HEAD --
              git -c core.quotepath=off ls-files --others --exclude-standard; } 2>/dev/null | sort -u)"
else
  paths="$(git -c core.quotepath=off diff --name-only --no-renames "$target" -- 2>&1)" || {
    echo "pathguard: git diff failed for '$target': $paths" >&2; exit 2; }
fi

# allowed <relpath-lowercased-area-aware>; returns 0 if the role may write it.
allowed() {
  local p="$1" lp
  lp="$(printf '%s' "$p" | tr 'A-Z' 'a-z')"
  case "$p" in ..*|*/../*|/*) return 1;; esac
  # Every role may update its own area handoff status.
  case "$lp" in .claude/handoff/$A/status.md) return 0;; esac
  case "$role" in
    orchestrator)
      case "$p" in
        .claude/plans/build_and_test_plan.md|.claude/sessions/*|.claude/handoff/*|tests/LOCK.sha256|.gitignore|CLAUDE.md|README.md) return 0;;
      esac;;
    planner)
      case "$p" in
        .claude/plans/specs/[0-9]*_*.md) return 0;;
        .claude/research/r2_*_spike.md) return 0;;
      esac;;
    spec-reviewer)
      [ "$p" = ".claude/plans/specs/REVIEW.md" ] && return 0;;
    test-writer)
      case "$lp" in
        tests/contract/$A/*|tests/unit/$A/*|tests/gd/$A/*|tests/e2e/$A/*) return 0;;
        tests/fixtures/*) return 0;;   # new fixtures only; modification of existing ones is checked below
        selftest/faults/$A-*) return 0;;
        .claude/handoff/$A/test_notes.md) return 0;;
      esac;;
    builder)
      case "$p" in
        tools/harness/*|addons/harness/*|templates/*|sample/*|docs/*) return 0;;
      esac
      case "$lp" in
        .claude/handoff/$A/build_notes.md|.claude/handoff/$A/test_disputes.md) return 0;;
      esac;;
    verifier)
      case "$lp" in
        .claude/handoff/$A/verify_*.md|.claude/handoff/$A/verify_*.json) return 0;;
      esac;;
    adjudicator)
      case "$lp" in
        tests/contract/$A/*|tests/unit/$A/*|tests/gd/$A/*|tests/e2e/$A/*) return 0;;
        .claude/handoff/$A/test_disputes.md) return 0;;
      esac;;
    *) echo "pathguard: unknown role '$role'" >&2; exit 2;;
  esac
  return 1
}

case "$role" in orchestrator|planner|spec-reviewer|test-writer|builder|verifier|adjudicator) ;;
  *) echo "pathguard: unknown role '$role'" >&2; exit 2;; esac

bad=""; n=0
# Test-writer may add fixtures but not modify existing ones: a tracked fixture file in the diff is a violation.
base_ref=""
case "$target" in working-tree|wt) base_ref="HEAD";; *..*) base_ref="${target%%..*}"; base_ref="${base_ref%.}";; esac
while IFS= read -r p; do
  [ -z "$p" ] && continue
  n=$((n+1))
  if ! allowed "$p"; then bad="$bad$p"$'\n'; continue; fi
  if [ "$role" = "test-writer" ] && [ -n "$base_ref" ]; then
    case "$p" in tests/fixtures/*)
      if git cat-file -e "$base_ref:$p" 2>/dev/null; then bad="$bad$p  (modifies existing fixture)"$'\n'; fi;; esac
  fi
done <<< "$paths"

if [ -n "$bad" ]; then
  echo "pathguard: FAIL role=$role area=$area, out-of-allowlist paths:"
  printf '%s' "$bad" | sed 's/^/  /'
  exit 1
fi
echo "pathguard: OK role=$role area=$area ($n paths checked)"
