area: A4 test-runner      phase: build      state: built, 1 flaky dispute open
spec: .claude/plans/specs/04_test_runner.md (v2)
tests: tests/unit/a4 15 passed; tests/contract/a4 52 passed + 1 flaky (test_ac_04_3_1, see test_disputes.md D-1)
selftest: `h selftest --area A4` 11/11 faults caught, 2/2 clean pass when idle; FAULT-A4-05 missed once under load (D-1)
regressions: p0+a1+a2+a3 contract and a1-a3 unit: 425 passed, 0 failed
updated: 2026-10-17 by builder B4 (sonnet)
done: verbs/test.py, gdunit.py; touched out.py, sync.py, godot.py (build_notes.md)
next: verifier; test author to fix D-1 fixture timing
disputes: 1 open (D-1)
