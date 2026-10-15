# A5 test notes (T5, Sonnet, 2026-10-15)

Written from spec 05_scenario.md v2 + 00_contract.md + REVIEW.md (R-01, R-15, R-18, R-19, R-20, R-34, R-38, R-39, R-50, R-51).
No tools/harness/**, addons/harness/**, templates/** or sample/** source was opened.

## Files
- `tests/unit/a5/test_a5_scenario.py` (AC-05.7, pure parts of 05.8/05.9/05.18; imports `harness.scenario` lazily; 65 cases incl. parametrised)
- `tests/contract/a5/{conftest.py,a5util.py,test_a5_run.py,test_a5_selftest.py}` (53 cases: AC-05.1-6, 8-24, 27, 28 + fault-driven `--twice` cases)
- `tests/gd/a5/{test_rng.gd,test_harness.gd,test_gd_a5.py}` (AC-05.25 = 7 cases, AC-05.26 = 7 cases; wrapper expects 14/14 via `run_gd_suites("a5")`)
- fixtures `tests/fixtures/projects/scenario_min/` (spec section 6; also reused by T6/A6 AC-06.25) and `scenario_noautoload/`
- `selftest/faults/FAULT-A5-01..12` (10 must, 2 nice, as the spec table) and `selftest/clean/CLEAN-A5-01..02`. Fault `files/` are generated JSON (wrong/ghost/typo scenarios, hand-written golden with `mover.n = 599`); `apply_fault` was run for all 14 entries against the fixture (every `replace` matches exactly once).

## AC coverage
All 28 ACs are covered. AC-05.1 .. 05.6 and 05.8 .. 05.24, 05.27, 05.28 contract; 05.7 unit; 05.25/26 gd. Not directly testable here:
- R-34 runner-side `[run.not-synced]` rc 1 (verb pre-check fires first; AC-05.13 covers the verb path).
- R-15 `--shot-at` block and R-19 `replay.run_scenario`: A6 AC-06.25 / A7; `harness.replay` is not importable by unit tests (R-01).
- `states.jsonl > 50 MB` `run.state-large`, `run.tick-skipped`, `run.unknown-command` at runner level beyond AC-05.11: no cheap deterministic trigger.

## Validation done without the implementation
- Fixture scripts were run in a scratch project against stub autoloads and a hand-rolled fixed-tick runner (spec 3.2 algorithm, `_process` + parse + flush): player lands at tick 21; jump press at 40 gives `velocity.y = -400`; `landed` fires once at tick 89; teleport at 90 gives x 501.67 (tick 89: 148.3); `x(60)` = 99.998; `input_events == 1`; events stamped 40/43/89. These numbers back the six jump.json asserts and the AC-05.5/05.10 values.
- gdUnit4 suites were run (gdUnit4 6.2.2, stub autoloads implementing the spec API): 18/18 pass.
- Red-state run: every contract test fails on `h: unknown verb 'run'` (warm-fixture creation), every unit test on `No module named 'harness.scenario'`; `pytest tests/unit tests/contract --co -q` collects 730 tests with 0 collection errors.

## Disputes / spec inconsistencies found (for the adjudicator or planner)
- **D-1 (resolved, R-57)** multi-scenario check lines use colon-free project-relative names (`OK   scenarios/jump.json: ...`); tests use the strict `assert_contract` (wrapper removed).
- **D-2** FAULT-A5-03 / AC-05.6 say "jump.json + assert `player.position.x ge 400 @tick 100`" fails, but jump.json teleports to x=500 at tick 90 (x(100) = 518), so the assert would pass. `wrong.json` therefore drops the teleport command and the tick-90 assert (5 pass + the new failing one = `1 of 6`, matching the spec's example verdict).
- **D-3** AC-05.14 says `golden: skipped (overrides)` with `--seed`. Tested only with a golden file present (without a golden `none` is also plausible).
- **D-4** `_unhandled_input` counts only presses (`is_action_pressed`), so `input_events == 1` holds for a hold-3 press (a press plus a release would otherwise give 2).
- **D-5 (resolved)** the gdUnit4 suite triggers no push_error. Dropped from gd (they necessarily log `ERROR:`): bad/duplicate id register, submit with no handler, unknown target, submit after unhandle. Those paths are covered only indirectly by contract AC-05.11 (runner-level unknown-target/unknown-command). Suite is now 7 Rng + 7 Harness/CommandBus = 14 cases (wrapper expects 14/14).

## Assumptions [U] (shapes the spec does not fix)
- `scenario.ScenarioError` is raised by `load` (tests check the class name and that pointer/message text contains the pointer or key).
- `resolve(state, path)`: `state` is the entities mapping `{id: state}`; `eval_asserts(resolved, states, metrics)`: `states` = states.jsonl rows, `metrics` = the `metrics` mapping of metrics.json; `compare_golden` returns `status` (compared case-insensitively: match / drift / mismatch / stale) and findings dicts with `rule`, `severity`, `message`.
- `eval_asserts` entry for `during`/`any` failure: `got` = closest value, `at_tick` its tick; `during`/`all` failure: first failing tick's value.
- `h run --record` writes golden `final_hash`/`chain_hash` equal to run A's state.json (`artifacts/A/state.json` under `--twice`, else `artifacts/`).
- With `--twice` artifacts live in `artifacts/A/` and `artifacts/B/` (spec 2.4); with `--record` the same.
- Event ticks are the tick of the physics step that logged them (press at 40, release at 43, landed at 89), as AC-05.5 states.
- Hand-written goldens (AC-05.18) list only the `mover` entity; the verb is expected to compare the golden's entities only.
- Perf test (AC-05.23) measures the whole `h` wall (incl. Python start-up) on a warm copy, median of 3.
