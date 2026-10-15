# A6 test notes (T6)

Layers: `tests/unit/a6/` (fixture/fault data integrity only, no harness import; passes now), `tests/contract/a6/` (all verbs via `h`).
Helpers: `tests/helpers/h.py` (unchanged) plus area-local `tests/contract/a6/a6_util.py` (PNG decoder, odiff call, pty/no-tty runner, meta edit) and `conftest.py` (`sm` = warm copy of shot_min via `mkwarm`, `sm_cold`).

## Fixtures
- `tests/fixtures/projects/shot_min/` (new): spec section 6 layout. Baseline `main-t30.png/.json` made with `tests/fixtures/tools/capture_ref.gd` under the K1 command line (Xvfb, gl_compatibility, `--fixed-fps 60`); meta env: llvmpipe LLVM 20.1.2 / Mesa 25.2.8. [Run] Pixel (50,120) orange, (49,120) background, `%Score` is 101x23, hud layout rects sane at 640x360, 1280x720, 800x1280.
- `scenario_min`, `scenario_noautoload` copied unchanged from T5's worktree (orchestrator dedupes).
- Baseline hash is for this machine class; on a different Mesa the verb falls to tolerant mode (`identical` only if sha equal, so CLEAN-A6-01 and AC-06.8 assume the same machine class).

## AC coverage
06.1 test_ac_06_1_*; 06.2 test_ac_06_2_*; 06.3 test_ac_06_3_*; 06.4 test_ac_06_4_* (slow); 06.5 test_ac_06_5_*; 06.6 / 06.7 test_ac_06_6_/_7_; 06.8 test_ac_06_8_*; 06.9 test_ac_06_9_* (tolerant, ignore, provisional); 06.10 / 06.11 / 06.12 in test_a6_compare.py; 06.13 test_ac_06_13_*; 06.14 test_ac_06_14_*; 06.15 test_ac_06_15_*; 06.16 test_ac_06_16_*; 06.17 test_ac_06_17_*; 06.18 / 06.19 test_ac_06_18_/_19_; 06.20 test_a6_layout.py; 06.21 / 06.22 / 06.24 test_a6_baseline.py; 06.23 test_a6_compare.py (incl. predicate parametrisation); 06.25 / 06.26 test_a6_scenario.py.
Extras: usage rc 2 matrix (bad ticks, names, sizes, layers, crop+node, target outside project, layout with capture flags), multi-tick naming, odiff missing -> rc 4 (via `HARNESS_CACHE`, [U] that the verb reads the odiff path from it as spec 3.2 step 1 says).
Untestable automatically: AC-06.27 (visual.py not public; covered through 06.8/9/11) and the A8 hook blocking `approve` for agents (A8 tests). Spec 2.2 rows `shot.no-display` and `shot.headless` (runner-side) cannot be triggered without a broken X server; only the CLI `--headless` path is tested.

## Faults (selftest/faults, selftest/clean)
FAULT-A6-01..12 (11 must, 12 nice), CLEAN-A6-01..03; spec minimum is 6. `files/other.png` is 8-bit RGB 640x360, 201 bytes.

## Run state (verbs not built; only `doctor` exists)
- `pytest tests/unit/a6`: 18 passed (data checks, every fault's apply ops replay cleanly on the fixture).
- `pytest tests/contract/a6 --co`: 83 tests collected, no collection errors (101 with unit).
- Contract tests fail for the right reason: `h: unknown verb 'shot'` (rc 2) for `sm_cold` tests; tests using `sm` error in fixture setup because `h import` (A1) is not built yet (`unknown verb 'import'`). They become real once A1 and A6 land. Not run against a real implementation.
- Timing assumptions to watch: AC-06.4 median <= 3 s warm; AC-06.19 wall <= 12 s (warm copy used so import time is excluded); layout default four sizes asserted <= 5 s (spec 2 s plus start-up slack).
