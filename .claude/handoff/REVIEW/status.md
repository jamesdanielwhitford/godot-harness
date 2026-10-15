area: REVIEW spec-review      phase: plan      state: done
spec: .claude/plans/specs/REVIEW.md @ uncommitted
tests: n/a      lock: n/a
updated: 2026-10-15 by spec-reviewer (claude-opus-5-5)
done:
- REVIEW.md: 50 decisions (R-01..R-50), conflicts (ownership, rule ids, output, autoloads, rc, fixtures, faults), 19 blocking + 24 non-blocking items, build graph + B1 exposure list, T1-T9 groupings, 2 human items
- fault counts: 143 faults + 28 clean, every area >= plan §10 minimum
- [Run] spikes: smoke-quit gives rc 0 with no done (FAULT-P0-06 replacement); class cache cfg lists (class, path) pairs (content-based staleness)
next:
- orchestrator: re-run planners P0, P1, P2, P3 with B01-B15 (gate Phase 2); P5, P6, P7, P9 with B16-B19 (gate Phase 3 test-writers)
- orchestrator: apply N12/N13 (plan text, tools/dev C5-C7, C10, ci.sh gd layer) before Phase 2
- ask the human REVIEW §6 items 1-2 once; continue on the stated defaults
blockers:
- G1 not passed until B01-B19 are applied
disputes: 0 open
