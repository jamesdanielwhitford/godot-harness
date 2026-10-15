area: P0 contract      phase: plan      state: done
spec: .claude/plans/specs/00_contract.md @ uncommitted
tests: 0 total (spec only; 27 ACs, 8 faults + 2 clean entries for T1)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- spec v2: applied REVIEW.md B01-B07 (R-38, R-50, R-25, R-24, R-32, R-01, R-05, R-06, R-09, R-14, R-31, R-16, R-10, R-11, R-12, R-22, R-39, R-45)
- applied N03 (R-03, R-04, R-07, R-13, R-46, R-44, R-48), N14 (§8 open items closed), N17 (§8.1 R-id list), N18 (AC-00.27)
- FAULT-P0-06 replaced (scene `_ready` quits rc 0 under --smoke), now must; AC-00.21 (8 caught) holds
- spec length 491 lines (was 515); prose rewrapped to 150 cols to fit, no content lost beyond the R-id edits
next:
- spec reviewer: confirm B01-B07 closed in REVIEW.md; G1 still needs B08-B19 from P1-P9 re-runs
- orchestrator: C5-C7 (C7 now: gd layer = `pytest tests/gd`), C10, C11 before Phase 2
- T1: helpers per §2.12 (assert_contract R-38/R-50 regexes, run_godot, gd.py), fixtures clean_min + gd_host
blockers:
- none
disputes: 0 open
