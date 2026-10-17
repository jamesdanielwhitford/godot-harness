area: A3 lint      phase: build      state: done (3 tests disputed)
spec: .claude/plans/specs/03_lint.md v2
tests: tests/unit/a3 + tests/contract/a3 = 126 collected / 123 pass / 3 fail (all 3 disputed, see test_disputes.md D-1, D-2)
selftest: `h selftest --area A3` rc 0, 27/27 faults caught, 3/3 clean pass (9 s)
regression: p0 82/82; a1+a2 contract and unit a1/a2/a3/p0 pass (424 pass, 1 fail fixed afterwards: p0 help width, now 82/82);
  tests/unit a4/a5/a6/a7/a9 fail as their areas are unbuilt
updated: 2026-10-17 by builder B3
blockers: none
disputes: 2 open (3 tests)
