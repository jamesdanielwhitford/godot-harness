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
