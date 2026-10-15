# A3 test notes (T3, 2026-10-15)

Spec: `.claude/plans/specs/03_lint.md` v2 + REVIEW (R-01, R-08, R-29, R-38, R-50). Black-box via `tools/harness/h`, helpers
from `tests/helpers/h.py` only. All contract tests copy fixtures first and set `HARNESS_OUT` under the test tmp dir.

## Files
- `tests/unit/a3/test_a3_rules_data.py` (data layer, AC-03.1, reads `tools/harness/rules/*.json` + the r1_5 yaml as text, no harness import)
- `tests/unit/a3/test_a3_fixtures_and_faults.py` (self-checks of fixtures vs spec 6.1 and fault files; green now)
- `tests/contract/a3/a3_common.py` (corpus table of spec 6.1, tiny wrappers), `test_a3_corpus.py`, `test_a3_config.py`,
  `test_a3_checks.py`, `test_a3_paths_speed.py`, `test_a3_godot.py` (marker `godot`; AC-03.7 and 03.28 marker `slow`)
- fixtures: `godot3_scripts` (generated from a3_common.CASES/TSCN; 36 .gd, 4 .tscn; 37 E + 5 W as in the spec example),
  `lint_base`, `lint_clean_demo` (dodge_the_creeps @ b761b4cd5718a7118f2c95eb55f181d0a5f004f1, MIT, text only, + our harness.toml)
- `selftest/faults/FAULT-A3-01..27` (25 must, 2 nice: 21, 27), `selftest/clean/CLEAN-A3-01..03`

## AC coverage
03.1 unit/data (7 tests) | 03.2 corpus (3) | 03.3 dedup | 03.4 base (+strict toml) | 03.5 demo (2) | 03.6 hook median | 03.7 slow |
03.8 no-godot full+hook | 03.9 hints (2) | 03.10 comments (+positive controls) | 03.11 (4) | 03.12 (9) | 03.13 (2) |
03.14 (+per-call param) | 03.15 (7) | 03.16 (17 cases x strict/default) | 03.17 (+sim_dirs) | 03.18 | 03.19 | 03.20 |
03.21 (11) | 03.22 oracle (+needs-paths, rc4) | 03.23 | 03.24 (+stale) | 03.25 (3) | 03.26 (2) | 03.27 | 03.28.
Nothing is "untestable automatically". The 300 ms budget (03.6) and 1.5 s diag (03.25) are wall-clock and machine dependent.

## Interpretation choices (spec silent or ambiguous)
- `lint.det-time-scale` has scope `all` (spec 3.3), so it still warns under the default `replay_dirs = []`; AC-03.16's "no
  lint.det-* finding" is tested for the other det rules only.
- Stdout hint "<= 100 chars": asserted on the whole hint text including a trailing `...`.
- `skipped:` is asserted only in `--hook` mode (spec 2.1 requires it there; full-mode counting of excluded dirs is unspecified).
- LSP tests use a private `HARNESS_CACHE` (tmp) so `stop --all` cannot touch real daemons; they always `stop --all` in `finally`.
- `lint_base/scenes/main.tscn`: Node2D root with a `Player` child carrying the script (a Node2D root cannot take a
  CharacterBody2D script); spec 6.2 says "Node2D root with player script".
- CLEAN-A3-* are in `selftest/clean/` (contract 2.10 layout, pathguard allows `clean-a3-*`), not `selftest/faults/`.
- `sim_dirs` override test (`[harness] sim_dirs`) goes slightly beyond the ACs (spec 2.6 says sim_dirs is scope sim).

## Red run (before any A3 code)
`pytest tests/unit/a3 tests/contract/a3`: 123 failed, 3 passed. Contract failures are all `h: unknown verb 'lint'|'lsp'`
(rc 2, stderr text from the old CLI; `assert_contract` flags it). 12 unit data tests fail on the missing
`tools/harness/rules/*.json`; the 3 passing tests are the fixture/fault self-checks. No collection errors:
`pytest tests/unit tests/contract --co -q` collects 585 tests. Not run green: engine-dependent tests need B3.
