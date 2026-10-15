# A7 test notes (T7, Sonnet)

Spec: .claude/plans/specs/07_feel.md + REVIEW (R-01, R-17, R-19, R-35, R-37, R-38, R-39, R-42, R-50, R-52, R-54).
Nothing under tools/harness, addons/harness, templates or sample was opened. Nothing was run against a built `h trace`
(it does not exist); fixture behaviour is [U] and was only checked with a Python model of the physics (see Fixture).

## Files
- Unit: tests/unit/a7/test_a7_feel_metrics.py (+ feel_adapt.py, tolerant adapter for `harness.feel`).
- Contract: tests/contract/a7/{test_a7_trace_suite,test_a7_trace_modes,test_a7_selftest}.py, conftest.py, a7util.py.
- E2E (pty): tests/e2e/a7/test_a7_approve_pty.py. gd: tests/gd/a7/{trace_dormant_test.gd,feel_targets_roundtrip_test.gd,test_gd_a7.py}.
- Fixtures: tests/fixtures/projects/{feel_min,feel_noautoload}/, tests/fixtures/feel_csv/ (4 CSV + .meta.json).
- Selftest: selftest/faults/FAULT-A7-01..11 (10 must, 1 nice), selftest/clean/CLEAN-A7-01..02. Minimum was 6.

## AC coverage
AC-07.1-8 unit; 9-12 suite contract; 13, 14, 19 test_a7_trace_modes; 15, 16, 17, 20, 21, 23 suite file; 18 non-TTY in
suite file and pty in e2e; 22 gd; 24 selftest. Untestable automatically: taste of targets (human, D10) and "agents cannot
edit targets" (A8 hook). AC-07.19 and 07.24 and the `--rates` tests are `slow`; 07.19 is also `xvfb`.

## Assumptions [U] (adjudicate when B7 lands)
1. `harness.feel` signatures are not fixed by the spec. feel_adapt tries: `read_trace(csv_path)`;
   `measure(trace, metric, params_dict | **params)` returning a number/dict/object with `value`,`unit`,`seconds`
   (undefined = exception, `verdict=="undefined"` or `value is None`, reason text in `reason`);
   `window({offset: bool}) -> (width, gap)`; `rate_spread(by_rate_seconds, base, slack)` -> relative spread float;
   `judge(value, unit, rate, target_dict, seconds)` -> verdict word or exception for a unit mismatch;
   `is_approved(by, on)`. A mismatch fails the unit tests: change feel_adapt only through the adjudicator.
2. Report sweep table rows are matched by `^|? <offset> | ... y|n|yes|no`; per-rate table by `30 Hz` / `@30` / three rates in a row.
3. `proposed_targets.json`: list of entries, or `{"targets": [...]}` / name-keyed dict, each with
   `metric,min_value,max_value,unit,approved_by`.
4. Schema errors rc 2 use `feel.suite` (duplicate name, window metric without sweep, sweep without `t0`/`k` vars, bad schema
   const), `feel.unknown-metric`, `feel.targets` (missing file, min > max). No scenario/movie invocation may be in run.json.
5. AC-07.21 injects a null call at physics step 50 in every probe (the spec only asks for rc 1 + `godot.script-error`).

## Fixture notes and deviations from spec section 6
- Fall/rise ratio target is [0.5, 0.9], not [1.2, 3]: gravity 1960 falling vs 980 rising gives fall_time < time_to_apex.
  Python model (semi-implicit Euler, 60 Hz): apex 85.0 px, time_to_apex 25 ticks (0.417 s), fall 18 ticks, ratio 0.72,
  tap apex 19.0 px (cut ratio 0.22), no-cut 1.0, constant gravity ratio 1.0 (so FAULT-A7-02 and -05 still fail alone).
  Other bounds are unchanged. Recorded in the fixture's FIXTURE.md.
- jump.json also holds a one-tick `right` tap at tick 1 so scenario mode traces 9 columns (AC-07.13: tick, position x/y,
  velocity x/y, is_on_floor, is_on_wall, in.jump, in.right). The jump probe measures only jump.* so this is harmless.
- Ledge scene `floor_end` 60; flat 4000. Level script builds floor, Player (16x32) and Camera2D "Camera" in code; player.gd
  configures the camera (smoothing speed 5, process mode) from the hook constants. Gravity is always applied so
  `is_on_floor()` stays true on the ground (row k vy 0 as in spec S1).
- Coyote timer refreshed on floor, decrement-then-check in air; buffer set on just_pressed, decrement after check; expected
  windows C 5..6, B 4..6 (spec 07.11). Hook lines are verbatim; the ACCEL hook line sits under `if dir != 0.0:` (two tabs),
  the FAULT-A7-01 `replace` old text starts with one tab and so still matches once (checked).
- targets.tres is a hand-written text resource (R-48 exempts data-only .tres), scripts are the synced
  `res://addons/harness/feel_target(s).gd`, no `script_class` attribute (no class_name).
- Fault regexes follow spec 5 and R-37 exactly; FAULT-A7-07/10 use verdict WARN, FAULT-A7-11 verdict ERROR.
- CLEAN-A7-02 max_seconds 150 (spec gives no limit); fault max_seconds 60 except 08 (150) and 11 (30).

## Red run (2026-10-15, before any implementation)
`pytest tests/unit tests/contract --co -q`: 701 tests collected (91 in A7 incl. e2e/gd), no collection errors.
Executed samples: unit tests fail with `ImportError: cannot import name 'feel' from 'harness'`; contract tests fail with
`h: unknown verb 'trace'` (rc 2, caught by assert_contract's stderr rule or by the rc assertion). The three fixture
self-checks (targets/suite/fault.toml files parse and agree) pass today by design. Nothing was skipped or xfailed.
