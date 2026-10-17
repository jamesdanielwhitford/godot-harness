# A4 test disputes

## D-1 FAULT-A4-05 / AC-04.3 (test_ac_04_3_1) are flaky: the buggy scene does not always run a physics frame
- Tests: `selftest/faults/FAULT-A4-05` (files/test_buggy.gd) and `tests/contract/a4/test_a4_h_test.py::test_ac_04_3_1_runtime_error_in_game_code`.
- Observed (macOS, Godot 4.7, gdUnit4 6.2.2): `scene_runner(...).simulate_frames(3)` is idle-frame based. The scene's
  `_physics_process` only runs when enough wall time passed for a physics tick. Alone it passes (3/3 runs); under load
  (full contract run, ci.sh --quick) the test finishes in ~40 ms with PASSED, gdUnit4 rc 0, no error in the log
  (run dir: `.harness/out/20261017T132935Z-selftest-565d/entries/FAULT-A4-05`). `h test` reports exactly what gdUnit4
  and the engine log say, so the verdict PASS is faithful; no harness change can make it deterministic.
- Fix proposal (test side): make the fixture force physics ticks, e.g. in test_buggy.gd use
  `await runner.simulate_frames(10, 20)` (delta_milli 20 so simulated time advances) or call
  `runner.invoke("_physics_process", 0.016)`, or have buggy.gd fail in `_ready()`/`_process` (idle frame) instead of
  `_physics_process`. Spec K10 recorded the failure with a physics callback, so only the frame driving needs changing.
