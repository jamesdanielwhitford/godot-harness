area: A4 test-runner      phase: plan      state: done
spec: .claude/plans/specs/04_test_runner.md @ uncommitted
tests: 0 total (spec only; 21 ACs, 11 faults + 2 clean entries for T4)      lock: n/a
updated: 2026-10-15 by planner (claude-opus-5-5)
done:
- 04_test_runner.md (444 lines): `h test [TARGET...] [--filter] [--changed] [--dotnet]`, 15-line output, rc map 0/100/101/103/104/105/1/124, `[test]` config (orphans, push_error), tests.json schema, layout convention + sim/scene test examples for the A8 skill
- S4 resolved: harness pre-resolves targets (gdUnit4 exits 0 on bad paths), single test = `-a suite` + `-i res://suite:other` per other test
- 17 spikes [Run] (K1-K17) incl.: absolute -rd rewritten to res:// (use res://.harness/gdunit/<run-id>), 105 writes no report, XML message gives wrong file for runtime errors in game code (use CDATA body), push_error passes in gdUnit4, orphans only on console, hang identifiable by last STARTED line, autoloads load under -s
next:
- spec reviewer: decide deviations D-1 (unit tests import harness.gdunit), D-2 (15-line cap), D-3 (--changed 0-test PASS)
- A1 planner/reviewer: confirm assumption A-1 (sync.install_gdunit4 API, h test auto-installs gdUnit4 when missing) and A-2 (godot.run kind "test" with A4's expected rc set)
- T4 writes tests/{unit,contract}/a4/, fixture gd_tests + tests/fixtures/gdunit/ recordings, FAULT-A4-01..11, CLEAN-A4-01..02
blockers:
- none
disputes: 0 open
