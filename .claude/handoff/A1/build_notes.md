# A1 + P0 build notes (builder B1, Sonnet, 2026-10-15)

## "core ready" gate: GREEN (before step 2+)
Contract tests for godot.py + check (AC-00.11-15, 19, 20; AC-01.1-2, 15) pass; AC-01.3 passes except one assertion
that I dispute (test_disputes.md D-1). Also green at that point: AC-00.1-10, 16-18, 26, 27; AC-01.17, 18, 26, 27, 30.

## Built (all under tools/harness/, addons/harness/, tools/bootstrap.sh)
- Step 0/1 core: `out.py` (Run, render, common_parser, `out.invoke` standard verb wrapper), `project.py`, `config.py`
  (CONFIG_TABLE discovery), `logscan.py`, `proc.py`, `godot.py` (binary + version cache, run, spawn/record_spawn,
  xvfb cleanup/retry, import retry on rc 134, content-based `ensure_imported`), `sync.py` (sync_project, ensure_synced,
  install_gdunit4, status), `cli.py` (verb discovery, help, did-you-mean), shim `h` (no cd, keeps HARNESS_REPO).
- A1: `verbs/{check,import_,sync,api,doctor,selftest}.py`, `checkrun.py` (load_check public), `apiindex.py`,
  `data/renames_3to4.json`, `faults.py`, `addons/harness/runners/load_check.gd`.
- C8/C9: bootstrap step 8 = `h api --rebuild` (guarded by index.json + @GDScript.xml), step 9 = `h sync/import --project sample`,
  venv check also imports jsonschema; `jsonschema` in requirements-dev.txt.

## Decisions / notes for other builders
- Verb boilerplate: `out.invoke(verb, argv, parser, main, need_project=True, soft_project=False)`; `main(r, args, project)`
  returns `r.finish(reason)`. It handles usage errors (`ERROR <verb> usage:`), project resolution, HARNESS_TIMEOUT_SCALE,
  harness.toml, and sets `r.config`, `r.project`, the `project:` stat. `r.error(rc, reason)` stops the verb (SystemExit
  after rendering); `r.finish_error(rc, reason)` renders an ERROR without raising (doctor uses it to keep check lines).
- `h <verb> --help` is answered by cli.py from the module's `HELP` and optional `USAGE` string (no run dir).
- `godot.run(..., expected_rc=set)` overrides the per-kind rc set (A4). `godot.run_import(r, project)` runs a plain import.
  A runner whose `done.rc` is 2/3 makes `godot.run` call `run.error(3, ...)` (C 2.8.6). Version probes are not recorded
  as invocations (run.json lists only real work). `Invocation.failed` = a harness.* error finding (hang/crash/rc/incomplete).
- `ensure_imported` sets `run.import_invocation` when it ran an import and adds the import findings to the run.
- `h check` records per-phase timings in `run.extra["check"]["timings"]`, file list in `extra.check.files`; the lists given to
  the runner are `artifacts/scripts.txt` / `scenes.txt` (`-2` etc. for resumes).
- The runner uses `_init` (not `_initialize`) so autoloads start after `done` is printed ([Run K] semantics kept).
- selftest `matrix.json` is a plain list; `--keep` keeps `$HARNESS_TMP/selftest-<run id>/`.
- api index extras beyond A1 §2.8: top-level `count` and `classes` (inherits, member counts, names) in index.json;
  cache path is `api/<godot_version_string>/` (the old bootstrap used `api/4.7`, ignored now).
- Lint: `h check` imports `harness.lint` lazily; `ModuleNotFoundError` for exactly that module -> `lint skipped (harness.lint not installed)`.

## Not done / not verified
- AC-01.29 (e2e, network, clones committed HEAD): not run here, the work is uncommitted.
- xvfb handling (A1 §3.8) is written but untested (needs A6).
- `h check --changed` outside a git work tree needs `git`; `unimported asset` staleness rule (A1 §3.3 b) is [U] (stat-only).
- 1 test disputed: AC-01.3 (see test_disputes.md).
