# A9 test notes (T9, spec 09_sim_view_sample.md v2, REVIEW R-08/16/17/35/36/38/39/50/51)

No sample/ or templates/ source was opened. Everything is black-box (`h` verbs on `copy_fixture("@sample")`, files read as data).

## Files
- `tests/unit/a9/test_a9_data.py`: AC-09.1, 09.2, hook-line presence (spec 3.1, so faults are not BROKEN), schema-helper self-tests.
- `tests/fixtures/a9/{sim_snapshot.schema.json,snapshot_check.py}`: spec 2.5 schema + stdlib validator (no jsonschema in the venv).
- `tests/gd/a9/*.gd` (5 suites, ~45 tests) + `test_gd_a9.py` (runs `run_gd_suites("a9","@sample")`, maps `test_ac_09_<n>_*`
  rows of `artifacts/tests.json` to ACs, validates an exported snapshot against the schema). AC-09.8-18.
- `tests/contract/a9/{conftest.py,test_a9_contract.py}`: AC-09.3-7, 09.19, 09.20, 09.22.
- `tests/e2e/a9/test_a9_fresh_clone.py`: AC-09.21 (clones committed HEAD; sample must be committed).
- `selftest/faults/FAULT-A9-01..12` (11 must + 1 nice; spec minimum 12 (1 nice), 3 clean) and `selftest/clean/CLEAN-A9-01..03`.
  Fault suites in `FAULT-A9-{02,03,06,09,10}/files/`. Replace ops match the hook text without its leading tab.

## AC coverage
AC-09.1,2 unit(data) | 3,4,5,6,7,19,20,22 contract | 8-18 gd (+wrapper) | 21 e2e. Untestable automatically: the section 2.8 text
accuracy and "sample reads well" (orchestrator review, per spec).

## Red check (no builder output yet)
`pytest tests/unit tests/contract --co -q`: 674 collected, no collection errors. Running: unit/a9 28 fail / 10 pass (schema helper tests)
on "missing templates/sample path"; contract/gd/e2e fail with `HelperError: @sample requested but sample/ does not exist yet (A9)` or
the missing-path assertion. gdparse accepts all .gd files (syntax only; the .gd suites have never run against an engine) [U].

## Interpretation choices the builder/verifier must know [U]
1. Coyote/buffer off-by-one (AC-09.16): "press k ticks after leaving the floor" = the k-th airborne `step` (k=1 first airborne step), accepted iff
   k <= 6 (`ticks_since_floor <= coyote_ticks()`). "k ticks before landing" = press at step 0 (airborne, coyote already expired), landing
   step (`on_floor=true`) is step k; accepted iff k <= 6. A builder whose counting differs by one must ask the planner, not edit the test.
2. AC-09.18 presses `move_right` for 40 frames (spec says 30) and waits until a Player exists; 30 frames at 220 px/s is borderline for >100 px.
3. AC-09.14 builds the second view with `TacticsView.new()` + `add_child` + `bind(world.clone())` (not a second scene instance, which would
   re-register CommandBus handlers).
4. AC-09.7: multi-scenario artifact layout is unspecified in A5, so asserts.json and `golden: match` are checked from single `h run` calls;
   the directory `--twice` run checks verdict, `OK` check lines and wall <= 90 s. Required asserts are matched in the scenario JSON by
   (path|metric, op, value, when); `between` value is expected as `[lo, hi]`.
5. AC-09.13 reason ordering: each rejection test uses a command that violates only one rule (e.g. `blocked` via occupied cell (0,3) and via
   terrain (3,3) from unit 2, both within move range). `unknown_command` and `no_such_unit` for attack are extra (from section 2.2/2.6 text).
6. AC-09.13 respawn: kills units 4,5,6 (5,6 despawned directly), `end_turn`, expects 3 `unit_spawned` with ids >= next_id before; and
   `wave_started` + `turn_ended` events.
7. SceneManager test paths: A=level_1, B=level_2, C=`scenes/tactics/unit_view.tscn` (instantiated as slot child; assumes it loads standalone).
8. `test_ac_09_10_export_snapshot_for_schema_check` writes `res://a9_snapshot_out.json` (copy root) for the Python schema check.
9. AC-09.6 counts suites via `artifacts/tests.json` (res://tests/sim/ >= 4, res://tests/scenes/ >= 3).
10. AC-09.22 baseline files expected at `sample/baselines/scenes/<scene stem>/<stem>-t60.{json,png}` (A6 layout); feel targets .tres expected
    to contain >= 5 `approved_by = "provisional-default"` lines (A7 text form [U]).
11. Selftest CLEAN entries use `not_regex ['\] error:']`; FAULT-A9-12 is rc 5 WARN (spec "5 WARN").
12. Run `tools/dev/lock_tests.sh` after review if the lock covers new test files (not run here).
