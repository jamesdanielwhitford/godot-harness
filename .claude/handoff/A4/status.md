area: A4 test-runner      phase: plan      state: done
spec: .claude/plans/specs/04_test_runner.md (v2) @ uncommitted
tests: 0 total (spec only; 21 ACs, 11 faults + 2 clean entries for T4)      lock: n/a
updated: 2026-10-15 by planner re-run (claude-opus-5-5)
done:
- v1 (444 lines): `h test` verb, rc map, `[test]` config, tests.json, layout convention, 17 spikes [Run] (K1-K17)
- v2 (463 lines), REVIEW.md v1 applied:
  - N01/R-02: §2.2 up to 5 stat lines; finding lines 8, or 7 when `selected:` shown (keeps 15-line cap);
    AC-04.13 and FAULT-A4-08 now expect `... 23 more findings` (target given), AC-04.13 adds a no-target 22 case
  - N02/R-33: §3.2 step 2 calls `sync.install_gdunit4` (present | installed (was missing)); differing version
    overwritten only if `.sync.json.gdunit4_commit` non-null, else rc 4; §3.1, §3.6 wording, AC-04.11, §8 A-1
  - N17: §8 D-1 accepted (R-01), D-2 accepted (R-02), D-3 noted as consistent with contract §2.4; A-1/A-2 settled
  - R-01: §3.1 closed public list `gdunit.parse_results` / `gdunit.parse_console`
  - `[test.no-tests]` row (§2.3): always error; `--changed` empty = only 0-test PASS, no finding
  - consistency: R-31 (`Invocation`, explicit add_findings, §3.2 step 7), R-24 (AC-04.18 `stale class cache (`),
    R-39 (§6 gd_host/gd.py are T1's)
next:
- spec reviewer G1 re-check
- T4 writes tests/{unit,contract}/a4/, fixture gd_tests + tests/fixtures/gdunit/ recordings, FAULT-A4-01..11, CLEAN-A4-01..02
blockers:
- none
disputes: 0 open
