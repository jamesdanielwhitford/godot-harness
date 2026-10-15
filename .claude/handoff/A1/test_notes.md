# T1 test notes (P0 + A1 core CLI + bootstrap C4)

## first-deliverable done (2026-10-15)
Ready for T2-T4 to use (read-only for them):
- `tests/conftest.py`: markers `godot`/`xvfb`/`slow`; `tests/` on sys.path (so `from helpers.h import ...`); `tools/harness` on
  sys.path only while collecting `tests/unit/**` (R-01); fixtures `mkproj(name)`, `warm(name)`, `mkwarm(name)`.
  Test file basenames must be unique across the whole tree (no `__init__.py`, rootdir import mode): prefix files with the area, e.g. `test_a2_*.py`.
- `tests/helpers/h.py`: `run_h(*args, cwd=, env=, timeout=) -> Result`, `copy_fixture(name|"@sample"|"none", dest)` (R-51 sync for @sample),
  `assert_contract(result, nodir=, help_output=)`, `apply_fault(id, project)` (replays a fault's `apply` ops), `run_godot(args, project, timeout)`,
  `write`, `scene_for_script`, `tree_hash`, `live_processes_mentioning`, `verbs_under_test()`.
  `Result` fields: rc stdout lines verdict verb reason stats stat_items checks findings trunc log_dir; methods run_json(), findings_jsonl(), has_finding(), matches().
- `tests/helpers/gd.py`: `run_gd_suites(area, fixture="gd_host")` + `cleanup(result)`.
- Fixtures: `projects/clean_min`, `projects/gd_host`; `selftest/faults/FAULT-P0-01..08` (06 per R-25), `selftest/clean/CLEAN-P0-01..02`.

## Full delivery (2026-10-15)
Files: tests/unit/{p0,a1,bootstrap}, tests/contract/{p0,a1}, tests/e2e/{p0,a1}; fixtures `scene_cases`, `gd_cases` (35 snippets),
`r1_4_cases` (28 verbatim .tscn, non-project), `harness_trees/{sync_src,gdunit_cache}`, `bin/godot_wrong_version`, `logs/*.log`,
`selftest_trees/{miss_must,miss_nice,broken_op,falsepos,bad_schema,slow,mixed,all_caught}` (each a `--faults-dir` root with faults/ and clean/);
selftest `FAULT-P0-01..08`, `CLEAN-P0-01..02` (P0-06 per R-25), `FAULT-A1-01..20` (A1-17 nice), `CLEAN-A1-01..04` (R-27 `--no-lint`).
CLEAN entries live in `selftest/clean/` (contract 2.10; pathguard allows `clean-<a>-*`), faults in `selftest/faults/`.
Counts (collected): unit p0 114 (incl. 90 catalogue/helper self-checks that pass now), unit a1 4, bootstrap 4, contract p0 67, contract a1 113, e2e 2.
Red check [Run]: unit/contract A1+P0 behaviour tests fail now (`ModuleNotFoundError harness.logscan/out`, `unknown verb 'check'`, missing runner file);
no collection errors (`pytest tests/unit tests/contract --co` collects clean). 3 contract tests pass vacuously because the old doctor already
satisfies them (bare `h` rc 2; `doctor --help` rc 0 short, no run dir). The helper/catalogue self-checks pass by design.

AC map: AC-00.1-4,6-12,19,20 test_p0_cli.py; 00.13-15,27 test_p0_faults.py; 00.16 unit/p0/test_p0_logscan.py; 00.17/18 unit/p0/test_p0_out.py;
00.21-23 test_p0_selftest.py; 00.24 e2e/p0; 00.25 unit/p0/test_p0_pathguard.py; 00.26 test_p0_doctor.py; 00.5 = assert_contract everywhere.
AC-01.1-16,31 test_a1_check.py; 01.17 test_a1_import.py; 01.18 test_a1_sync.py; 01.19-24 test_a1_api.py; 01.25,30 test_a1_doctor.py;
01.26 unit/a1; 01.27 test_a1_runner.py; 01.28 test_a1_selftest.py; 01.29 e2e/a1/test_a1_bootstrap.py (network, slow).
Untestable automatically / gaps: OVERFLOW comparator (AC-00.22 last clause: faults.py is not a public unit module, R-01); `--strict` rendering at
unit level (out.Run has no strict parameter in the spec) is tested through `h doctor --strict` (test_a1_doctor); handoff format (C 2.15).

Assumptions [U] builders should know (dispute if wrong):
- `--strict` on a FAIL with only warnings: assert_contract accepts FAIL when `--strict` is in argv and a warning/WARN line exists.
- ERROR runs: findings are read from findings.jsonl (stdout may show only verdict/project/log).
- AC-01.18 passes `HARNESS_REPO` pointing at a temp tree; the shim must not overwrite an already-set value.
- uid in r1_4 c00/c05 is the research project's; tests substitute the real `scripts/hero.gd.uid` after import. scene_cases/c00 and CLEAN-A1-03's c00 have the uid attribute removed.
- AC-01.7 second half and AC-01.4/5/8 use `--no-lint` to isolate A1 from A3; AC-01.1/2/3/13/14/16 run lint-default as in the spec.
- selftest `matrix.json` may be a list or `{"entries": [...]}`; both accepted. Nice-miss run must print a `WARN` check line (WARN invariant).
- Files in tests/ need unique basenames (no `__init__.py`): prefix with the area.
