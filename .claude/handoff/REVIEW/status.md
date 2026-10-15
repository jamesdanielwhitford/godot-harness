area: REVIEW spec-review      phase: plan      state: done
spec: .claude/plans/specs/REVIEW.md @ uncommitted (v2, re-check §8 over specs at b2c990a)
tests: n/a      lock: n/a
updated: 2026-10-15 by spec-reviewer (claude-opus-5-5)
done:
- v1: R-01..R-50, conflicts, 19 blocking + 24 non-blocking items, build graph, T1-T9 groupings, 2 human items
- v2 re-check (§8): B01-B19 all applied, each checked against its spec section; N01-N09, N11, N14-N23 applied
- cross-spec checks (a)-(e): run_scenario returns findings everywhere; load_check consistent in A1/A2; autoload counts consistent (A8 "3 autoloads" = open N24)
- new decisions R-51..R-56: @sample copy gets `h sync --no-gdunit` (R-51, [Run §8.4] missing autoload = error findings); `movie` is runner-style (R-52); `installed (pin changed)` accepted (R-53); run_scenario owns --fixed-fps (R-54); stale [U] notes (R-55); 00 at 491 lines accepted (R-56)
- verdict: G1 passed
next:
- orchestrator: commit REVIEW.md, tag specs-v1, start Phase 2 (T1 first deliverable incl. R-51 in copy_fixture)
- orchestrator: apply N12/N13 before Phase 2; P8 applies N10/N24 before T8; N25-N29 at the next planner touch
- ask the human REVIEW §6 items 1-2 once; continue on the stated defaults
blockers:
- none
disputes: 0 open
