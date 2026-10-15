area: A1 core_cli      phase: tests      state: done
spec: .claude/plans/specs/01_core_cli.md v1.1 @ uncommitted
tests: 304 collected (unit 122 incl. 4 bootstrap / contract 180 / e2e 2) / pass: ~95 self-checks + 3 vacuous / fail: all behaviour tests red   lock: n/a
updated: 2026-10-15 by test-writer T1 (Sonnet)
done:
- first deliverable: conftest, helpers h.py/gd.py, fixtures clean_min/gd_host, FAULT-P0-*
- all P0 + A1 ACs, FAULT-A1-01..20, CLEAN-A1-01..04, fixtures scene_cases/gd_cases/r1_4_cases/harness_trees/bin/logs/selftest_trees, C4 doctor test edit
next:
- orchestrator: pathguard, then lock; verifier red check; B1 builder
blockers:
- none
disputes: 0 open
