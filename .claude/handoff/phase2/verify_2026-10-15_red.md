# Phase 2 red check (VERIFIER), 2026-10-15

Setup: fresh clone of origin/main at c07e27d (scratchpad .../scratchpad/c), tools/bootstrap.sh -> doctor ok.
Command: `.venv/bin/pytest tests/unit tests/contract tests/e2e -q --maxfail=1000 -p no:cacheprovider` (no deselection; slow/godot tests included, 56 s wall).
Total: 368 failed, 112 passed, 135 errored (615 items). No collection errors.

## Counts (by test directory area)
| area | passed | failed | errored |
|---|---|---|---|
| p0 (unit+contract) | 88 | 94 | 0 |
| a1 | 0 | 117 | 0 |
| a2 | 0 | 9 | 90 |
| a3 | 3 | 123 | 0 |
| a4 | 0 | 23 | 45 |
| bootstrap (pre-existing unit) | 2 | 2 | 0 |
| devtools (pre-existing) | 19 | 0 | 0 |

## Classification of the 503 non-passing
All right-reason red. Zero helper/fixture bugs found. Breakdown of the reason:
- `h: unknown verb 'X'. verbs: doctor` (check, import, sync, api, lsp, selftest, scenes, test...), surfaced as "a verb must not print to stderr" contract violation, rc=2 asserts, or fixture `h import`/`h test` rc=2 on warm copy: a1 111, a2 99 (90 setup errors from scene_host warm copy `h import` rc=2, plus 9), a3 ~122, a4 45 setup errors (gd_tests warm copy first `h test` rc=2) plus 23, p0 ~79.
- ModuleNotFoundError harness.logscan / harness.out / harness.gdunit / harness.scenes: p0 28, a1 4, a4 15, a2 7.
- Missing generated data/runner: a3 tools/harness/rules/lint_rules.json + native_classes.json missing (12 tests, build_lint_data.py absent); a1 addons/harness/runners/load_check.gd missing (3, test_ac_01_27_*).
- doctor not yet C4 format (first line `PASS doctor`, `--help` usage, flag rejection): test_a1_doctor::test_ac_01_25_* (2), test_p0_doctor::test_ac_00_26_* (2), test_p0_cli::test_ac_00_3[--help-doctor], [-h-doctor], test_ac_00_4[doctor], test_ac_00_7, test_ac_00_1 (help format), bootstrap/test_doctor::test_doctor_fails_when_cache_missing (expects rc 4, gets 1) and test_doctor_passes_after_bootstrap (expects `PASS doctor` first line).
- a1 test_a1_bootstrap::test_ac_01_29 (slow, godot): real bootstrap ran ok but api dump `@GDScript.xml` not at cache/api/<full version> (bootstrap writes cache/api/4.7); right-reason (api build unimplemented).
- p0 test_ac_00_4_unknown_flag[api|check|import|selftest|sync], test_ac_00_8_no_project_is_rc_2, test_ac_00_8_dir_without_project_godot_is_rc_2, test_ac_00_11_missing_godot_binary: fail with `IndexError: r.lines[0]` because unknown verb gives empty stdout. Right reason (verb missing), but the failure message is opaque; a guard `assert r.lines, r` would give a clearer red. Cosmetic, not a bug.

## Helper/fixture bugs
None found. Warm-copy fixtures (scene_host, clean_min, scene_cases, gd_tests) fail only because `h import`/`h test` do not exist. Note: that means a2/a4 errors are setup errors, not failures; they will only become meaningful once `h import` works, and any bug in the warm-copy fixtures themselves is NOT exercised yet (unverifiable in red).

## Vacuous passes (passing with no implementation)
All 112 passes are self-tests of test infrastructure or pre-existing behavior; none assert harness behavior that should be new:
- p0 test_p0_catalogue (fault/clean entry well-formedness, apply-ops on fixture copy, fixture contract, counts), test_p0_helpers (parse/assert_contract self-tests), test_p0_pathguard (4): legitimate infrastructure checks.
- a3 test_a3_fixtures_and_faults (3): fixture-shape checks, legitimate.
- Candidate: tests/contract/p0/test_p0_cli.py::test_ac_00_2_bare_h_prints_usage_rc_2 passes against the current `h` (usage line already exists). Not vacuous in the strict sense (AC is already met) but gives no red; test_writers may leave as regression guard.
- bootstrap 2 + devtools 19: pre-existing, expected green.
Also note: no test among a1/a2/a4 passes, so nothing vacuous there.

## Verdict
Red is clean: failing for the right reasons, no collection errors, no missing-tool failures. Skipped: none (0 skipped/xfail).
