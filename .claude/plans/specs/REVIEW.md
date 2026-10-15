# Spec consistency review (Gate G1, plan §8.1 phase 1c)

Status: review v2 (v1 + re-check §8), 2026-10-15, Opus spec reviewer. Inputs: CLAUDE.md, plan §1-8/10/11, `00_contract.md` (C), specs
01-09 (cited "A1 §x" ... "A9 §x"), `.claude/handoff/*/status.md`. This file is the single source of reconciliation:
where it and a spec disagree, this file wins until the planner re-run lands. Tags: [Run] verified here (§7), [U].

**Re-check (v2, §8): G1 passed.** B01-B19 are all applied. The re-check found no new blocking items. It adds
decisions R-51..R-56 and non-blocking items N25-N29; builders and test-writers follow them now.

v1 verdict (historical): G1 not yet passed. 19 BLOCKING items (§3.1), 24 NON-BLOCKING (§3.2). All specs meet the AC/fault
minimums (§2.7). No two specs define the same verb, rule id or fixture name. The blocking items are mostly
mismatched cross-spec APIs and selftest entries that cannot pass as written.

## 1. DECISIONS (every deviation, reviewer question and open cross-area item)

Rule of thumb applied: the simplest option that keeps tests black-box and keeps each file owned by one builder.
"Amend" names the spec to change. The amendment text is either given here or points at the R-id row, which is
normative.

| ID | Topic (raised by) | Decision | Amend |
|---|---|---|---|
| R-01 | Unit tests importing `harness.*` beyond logscan/out (A2 D-1, A4 D-1, A5 D-a, A7 D-a, A8 AC-08.9) | **Accept, closed list.** tests/unit may import only these pure, stdlib-only, side-effect-free modules: `harness.logscan` (scan), `harness.out` (render, Run), `harness.scenes.model` (A2), `harness.gdunit` (parse_results, parse_console; A4), `harness.scenario` (load, resolve, eval_asserts, compare_golden; A5), `harness.feel` (read_trace, measure, window, rate_spread, judge, is_approved; A7), `harness.wiring` (merge_settings; A8). A3 tests read `tools/harness/rules/*.json` as data (layer `data`). `harness.checkrun` is NOT public (see R-28). Each owning spec lists its public names in §2. | C §2.12 last bullet: "Unit tests may import only the modules listed in REVIEW R-01, via sys.path insert of tools/harness." C §2.9 heading too. |
| R-02 | A4 15-line stdout cap (A4 D-2) | **Accept** as a verb-local stricter cap (the contract's 40 lines still apply and are checked by `assert_contract`). Fix A4 §2.2: "up to **5** stat lines" (project, import, gdunit4, tests, selected). | A4 §2.2 |
| R-03 | New rule prefix `api.*` (A1 D-a) | **Accept.** | C §2.7: add "`api.` (A1)". |
| R-04 | `verbs/import_.py` (A1 D-b) | **Accept.** | C §2.1 discovery: "a module name may end in one `_` (keyword clash); the CLI name drops it (`import_.py` -> `h import`). Names starting `_` stay private." |
| R-05 | `godot.run` without `--path` for doctool/version (A1 D-c) | **Accept.** `godot.run(run, kind, project=None, ..., cwd=<dir>)`: with `project=None` there is no `--path`, `cwd` is required and no import check runs. Allowed for kinds `version`, `doctool`. | C §2.8.2 first sentence; C §2.9 signature. |
| R-06 | Log-scan additions (A1 D-d, §3.4) | **Accept into the contract for all verbs.** Before matching, strip ANSI CSI sequences `\x1b\[[0-9;]*[A-Za-z]` (superset of A1's SGR form; A4 uses the same). Location fallback: if a "next (res://F:L)" rule finds no paren location in its window, use the first `res://<path>:<line>` token of the matched line. AC-00.16 unchanged; AC-01.26 stays in A1. | C §2.8.4 (2 sentences). |
| R-07 | Stricter scan/runner dedup in `check` (A1 D-e) | **Accept as verb-level.** C §2.8.6 dedup is the minimum. A verb may dedup further (A1 by normalised message, A4 by location). A protected scan finding may be dropped only when a runner/XML finding covers the same problem. | C §2.8.6 one sentence. |
| R-08 | `[lint] replay_dirs` default (A3 §8.2 Q1) | **Default `[]`.** With `["res://"]`, every UI Timer/Tween in a user project warns. It would also turn fixtures that must PASS `h check` into WARN: `scene_host` has an AnimationPlayer without `callback_mode_process = 0` (A2 AC-02.11, §6), and so does `h init --new` output. The sim dirs still get errors. Projects opt in: `templates/project/harness.toml` and `sample/harness.toml` set `[lint] replay_dirs = ["res://"]` (the sample dogfoods strict mode). A3 changes: §2.6 default `[]`. `lint_clean_demo` ships `harness.toml` with `[lint]\nreplay_dirs = ["res://"]` (FIXTURE.md says it is ours), so AC-03.5 and CLEAN-A3-02/03 keep their expectations. AC-03.16 tests write that harness.toml first. FAULT-A3-13 and FAULT-A3-17 gain a first `[[apply]] op="write" path="harness.toml" text="[lint]\nreplay_dirs = [\"res://\"]\n"`. | A3 §2.6, §6.3, AC-03.16, FAULT-A3-13/17, §8.2; A9 §2.4 (replace "no [lint] overrides ... incl. replay_dirs" with the line above) |
| R-09 | New Godot kinds `oracle`, `lsp_start`, and `godot.spawn` (A3 §8.3) | **Accept; B1 builds `spawn`.** Kind table adds `oracle` 60 s (expected rc {0}) and `lsp_start` 30 s. `godot.spawn(run, kind, project, args) -> Popen` starts in its own session and process group, with stdin `/dev/null` and a log file under the run dir (or a given path). It records an invocation entry once readiness is known (`rc` 0 ready / 1 failed, `timed_out`). No auto-import. A3 never calls `subprocess` on Godot. | C §2.8 intro ("started by `godot.run()` or `godot.spawn()`"), §2.8.2 table, §2.9; A1 §3.1 (godot.py exposes spawn); A3 §8.3 closed. |
| R-10 | `fixture = "@sample"` (A9 D-1) | **Accept.** `@sample` = `$HARNESS_REPO/sample` copied like a fixture, excluding `.godot/ .harness/ addons/harness/ addons/gdUnit4/`. A9 faults whose hook lines are missing report `BROKEN` until B9 lands (expected red). Sample edits need no re-lock. `copy_fixture("@sample", dest)` supports it. | C §2.10 (`fixture` = name \| `"none"` \| `"@sample"`), §2.12 helper text. |
| R-11 | Binary PNG baselines in fixtures (A6 D-a) | **Accept, narrow exception**: `*.png` <= 20 KB under a fixture's `baselines/` or a fault's `files/`. Every other fixture file stays text. | C §2.11 "Text files only, except ...". |
| R-12 | `_capture.gd` loaded at run time by absolute path (A6 D-b) | **Accept.** | C §2.8.5 add: "A runner may `load()` (never `preload`) a library file under `$HARNESS_REPO/addons/harness/runners/` whose absolute path comes from its args or plan. Library files start with `_`, have no `class_name`, and never print `done` or call `quit()`." |
| R-13 | `h shot --layout` runs headless (A6 D-c) | **Accept.** The never-headless rule applies to image capture only. A user-passed `--headless` stays rc 4 in every mode. | C §2.8.2 last clause: "never together with `--headless` for image capture". |
| R-14 | godot.py xvfb handling: stale X lock cleanup, extra args, display retry (A6 D-d) | **Accept; owned by A1/B1 in `godot.py`.** Extra Godot args already go through `args`. For `display="xvfb"`: (1) after the T+3 s SIGKILL path, remove each `/tmp/.X<n>-lock` created after the invocation started whose PID (the file content) is dead, plus `/tmp/.X11-unix/X<n>`. (2) If the log matches `Unable to create DisplayServer\|Xvfb failed to start\|xvfb-run: error`, retry once (`retried: true`). If it still fails, `Invocation.display_failed = True` and the verb maps that to rc 4 `[shot.no-display]`. Verified later by A6 AC-06.19. | A1 new §3.8 (copy A6 §3.5 bullets 2-3); C §2.8.3 one sentence; A6 §8.3 D-d closed. |
| R-15 | Ownership of the A6 block in A5's `runners/scenario.gd` and `extra_args` (A6 §8.4) | **A5/B5 owns `scenario.gd` entirely and writes the `--shot-at` block itself.** If `--shot-at=<abs plan json>` is present: parse it, `cap = load(plan.capture_script).new()`, `root.add_child(cap)`, `cap.start(plan, Harness)`. Before `quit`, keep stepping frames (recording no more ticks) while `cap.pending() > 0`, capped at 120 frames, then finding `[harness.runner-incomplete]`. Any other unknown `--x=` user arg is ignored (A7's `--trace=` is read by the Trace autoload). A6 drops `scenario.gd` from its §3.1 file list. AC-06.25 is the test (after B6). | A5 §3.1/§3.2 (new step 6), A6 §3.1, §8.4 |
| R-16 | Trace in the default autoloads (A7 §8.4) vs the A9 template order | **Accept.** C §2.6 default `autoloads = ["Harness", "Rng", "CommandBus", "Trace"]`. `h sync` appends a missing entry after the last key line of an existing `[autoload]` section (new section at the end of the file only if there is none) and never reorders. The A9 template and sample `[autoload]` = Harness, Rng, CommandBus, **Trace**, SceneManager, so sync stays byte-identical. A9 AC-09.2 lists those 5 in that order; AC-09.5 says "5 autoloads". A5 `required_autoloads` stays 3. `scenario_min` keeps 3 declared (A5 tests do not run `h sync`). The A8 example shows "4 autoloads". | C §2.6; A1 §2.3 (default + insertion rule); A9 §2.4, AC-09.2, AC-09.5; A8 §2.1 example |
| R-17 | A7 metric names and the accel-time convention vs plan/A9 wording | **A7 §2.5 names and §2.4 conventions are canonical** (also for RP.A/RP.D, plan §9.2.4). "Accel ticks to max speed" = `run.accel_time` (ticks, steps counted from the press tick inclusive; instant = 1, never 0; A7 D-c accepted). A9 `feel_targets.tres` uses `jump.apex_px` [44, 52] px, `jump.time_to_apex` [0.35, 0.41] s, `run.accel_time` [3, 8] ticks, `jump.coyote_window` [5, 7] ticks, `jump.buffer_window` [4, 7] ticks (A7 S2: check-then-decrement code measures 4). All are `provisional-default`. B9b may widen a provisional bound to measured ± 1 and must record why in build_notes. | A9 §2.7 "Data files" sentence |
| R-18 | A5 `tick_completed(0)` (A7 §8.4-1) | **Accept.** In `_begin`, after recording tick 0 and before applying the tick-1 inputs, the runner emits `Harness.tick_completed(0)`. Over a run it is emitted ticks + 1 times. | A5 §2.3 comment, §3.2 step 2 |
| R-19 | `run_scenario` helper: resolved-file parameter, `extra_args`, display (A6 §8.4, A7 §8.4-2/3) | **One helper in a new A5 file `tools/harness/harness/replay.py`** (keeps `scenario.py` pure for R-01): `run_scenario(run, project, resolved: Path, *, fps: int, global_seed: int, out_dir: Path, extra_user_args=(), extra_args=(), display="headless", kind="scenario") -> RunResult` (fields: `invocation`, `out_dir`, `state`, `ticks_path`, `states_path`, `events_path`, `metrics`, `findings`). It runs the C §2.8.6 merge for its invocation. It does NOT evaluate asserts or goldens, or add `run.no-asserts` (those are `h run` only). Public in `scenario.py`: `load(path, vars=None, seed=None, ticks=None) -> dict` (resolved) and `write_resolved(d, path)`. `h run`, A6 (kind `shot`, display xvfb) and A7 (kind `scenario`/`movie`) all call it. | A5 §3.1 (+replay.py), §3.3, §8; A6 §3.2 step 3; A7 §3.3/§3.5 |
| R-20 | `CommandBus.handle` replace vs `unhandle` (A9 §8.4) | **`handle()` silently replaces** an existing handler for that type. Also add `unhandle(type) -> void`. SimHost calls `unhandle` on `tree_exiting` (hygiene). | A5 §2.3, AC-05.26 (+"second handle replaces; unhandle removes"); A9 §2.3 SimHost note |
| R-21 | scene-edit ext `uid=` text pass (A2 §3.3) | **Accept as specified.** The rewrite touches header attributes only (`[gd_scene ... uid=`, `[ext_resource ... uid=`). It is followed by the load-check, the digest compare and, on any error, byte-exact rollback. This is the harness repairing an engine save, not a hand edit. | none |
| R-22 | digest <= 40 lines with a `more:` stat; plan's "<= 60" (A2 D-2) | **Accept.** Plan §7 "<= 60 lines" is superseded. `--all-props` dropped. | C §2.3 add: "A verb whose stat lines would exceed the limit ends them with `more: <K> lines in <path>` (A1 api, A2 digest)." |
| R-23 | `--project-summary` instead of plan `--project` (A2 D-3) | **Accept** (`--project DIR` is the common flag). | none |
| R-24 | class_name re-import costs 4.6 s vs the < 2 s hook budget; cache staleness by content (A8 §8.2-1) | **Accept content-based staleness; drop the script mtime rule.** `ensure_imported` imports when `.godot/` or `.godot/global_script_class_cache.cfg` is missing. Otherwise it compares the set of (class, res path) pairs in the cache's `list` [Run §7] with the set parsed from every project `*.gd` (`^\s*class_name\s+(\w+)` in the first 50 lines). Scope: everything Godot imports, including `addons/`, excluding `.godot/`, `.harness/`, hidden dirs and dirs with `.gdignore`. Any difference -> import, `<why>` `stale class cache (<first differing file>)`. `base` is not compared [U]. A1 §3.3 refinements (missing script, unimported asset) stay. AC-01.12, CLEAN-A1-02 and AC-04.18 stay valid (new class -> import). A8 §3.2 budget: a clean `.gd` edit, including a class_name edit that keeps the name, <= 2.5 s. | C §2.8.7 (rewrite as above); A1 §3.3 first line; A8 §3.2 budgets, §8.2-1 closed |
| R-25 | FAULT-P0-06 cannot fire (A1 §8.2-2, §3.6 K) | **Replace it [Run §7].** FAULT-P0-06 (**must**): write `scripts/quit_early.gd` (`extends Node` / `func _ready() -> void:` / `\tget_tree().quit(0)`) and `scenes/quit_early.tscn` (root Node with that script); args `["--smoke"]`. Expect rc 1, FAIL, `\[harness\.runner-incomplete\]`, <= 40 s. A runner that awaits frames never prints `done` when project code quits (rc 0). AC-00.21 (8 caught, rc 0) then holds. A1 §3.2 step 5: when the process ends rc 0 with an item that has `begin` but no `end`, put `[harness.runner-incomplete]` at that item and resume the rest (like hang/crash). | C §5 row P0-06, §8 open (1) closed; A1 §3.2 step 5 |
| R-26 | `h api --exists` FAIL prints only verdict + log, which breaks the C §2.3 invariant (FAIL => error finding) | **FAIL output = 3 lines**: verdict, `-: [api.not-found] error: <q> does not exist in Godot 4.7` (or `[api.renamed]` with hint), then `log:`. PASS stays 2 lines. | A1 §2.4 `--exists` bullet, AC-01.21 |
| R-27 | CLEAN-A1-01 runs lint, and c21 gives `syn-lambda-capture-reassign` (W) per A3 §6.1, so rc 5 not 0 | **Args `["--smoke", "--no-lint"]`.** | A1 §5 CLEAN-A1-01 |
| R-28 | AC-01.16 asserts `lint skipped` (red once B3 lands) and needs `harness.checkrun` in units | **Rewrite AC-01.16 [contract]**: `phases:` matches `lint (\d+\.\d+s\|skipped \(.+\))`; with `--no-lint` it shows `lint skipped (--no-lint)`. Drop the [unit] monkeypatch part. The integration is covered by A3 AC-03.23 and FAULT-A3-22. | A1 AC-01.16 |
| R-29 | Lint API: A1 assumes `harness.lint.check_files(run, project, files)`, A3 ships `run_lint(run, project, paths, mode)` | **A3's API is canonical.** In step 9, A1 calls `harness.lint.run_lint(run, project, None, "full")` when no PATH/`--changed` was given (lints project.godot too). Otherwise it passes the selected file list including dependents (A3 still applies `exclude`). Remove `h check --lsp` from A3 §2.3 (LSP stays `h lsp diag [--oneshot]`; A1 §8.1 already excludes it). | A1 §3.2 step 9, §8.4; A3 §2.3 |
| R-30 | A2 assumes `load_check.gd -- <res path>...` with `@@H` findings; A1 defines `--mode scenes --list <file>` + begin/end data records | **A1's protocol is canonical.** A1 exposes `checkrun.load_check(run, project, res_paths, smoke=0) -> list[dict]` (A1 §3.2 steps 3-8, no lint; returns findings, does not add them). A2 calls it for its pre/post write checks. A2 may add a `--mode` to `load_check.gd` only via an A1 re-plan (prefer not). | A1 §3.1 (public helper), A2 §3.3 + §8.4 bullet 1 |
| R-31 | `godot.run` return value (A2 §8.4 "returns parsed records"; A1/A4 own dedup) | **`godot.run` returns `Invocation`** with `n, kind, argv, rc, timed_out, duration_s, log_path, scan_verdict, runner_rc, retried, display_failed, records` (parsed `@@H` data/stat records) and `findings` (scan + rc + runner, merged per C §2.8.6). It records the run.json invocation entry but does NOT add findings to the Run. The verb calls `run.add_findings(inv.findings)` or dedups first. | C §2.9 |
| R-32 | Is auto-import implicit in `godot.run`? (C §2.8.7 is ambiguous) | **Explicit.** Verbs call `godot.ensure_imported(run, project)` (which prints `import:`) before their first invocation of a kind other than `version/import/doctool/oracle/lsp_start`. `godot.run` never imports. | C §2.8.7 first sentence |
| R-33 | Sync library: `install_gdunit4` (A4 A-1), `ensure_synced` (A5 §8, A6, A7), and a user's own gdUnit4 copy (A4 "never overwrite" vs A1 "copy when commit differs") | **New A1 file `tools/harness/harness/sync.py`**, with `verbs/sync.py` as a thin wrapper. `ensure_synced(run, project) -> str` (`fresh` \| `ran (<why>)`): mirrors `addons/harness/` when project.godot declares any harness autoload and `.sync.json.source_hash` is missing or differs. It never edits project.godot and never installs gdUnit4. `install_gdunit4(run, project) -> str` (`present` \| `installed (was missing)`): copies the cache addon minus `test/` and `*.uid` (A4 K17). An existing addon whose `plugin.cfg` version differs from the pin is overwritten only if `.sync.json.gdunit4_commit` is non-null (harness-installed), else rc 4 `gdUnit4 <v> in project, harness pins 6.2.2 (run h sync)`. `sync_project(run, project, gdunit=True, check=False)` = `h sync`. | A1 §2.3, §3.1, §8.4; A4 §3.2 step 2, §8 A-1 |
| R-34 | A5 runner exits rc 2 on `run.not-synced`, but C §2.8.6 maps runner rc 2 to verb rc 3 | **The runner emits `[run.not-synced] error` and `done` rc 1.** The verb's pre-check in A5 §3.3 step 1 stays rc 2. | A5 §3.2 step 1 |
| R-35 | Approval predicate differs: A6 accepts any non-empty `approved_by`, A7 rejects `provisional*`/agent names. How does the sample pass while provisional? (A9 §8.2-5, plan §11.5) | **One predicate for both:** human-approved iff `approved_by` matches none of `^$\|^(?i:provisional\|agent\|claude\|ai$\|bot$)` (A7 §2.7). A6 compare: meta `status: approved` with a non-human `approved_by` still compares, plus one `[shot.baseline-unapproved] warning: <name>: provisional baseline (approved_by <v>)`. A proposal-only baseline stays an error. B9b makes the sample's provisional baselines with `h baseline propose`, then renames the pair to approved with `approved_by: "provisional-default"`, `approved_at: null`, recorded in build_notes. This is not an approval (D4); the human approves at G3. Sample `h shot --compare` and `h trace` therefore give **rc 5 WARN** with only `shot.baseline-unapproved` / `feel.unapproved` warnings. Plan §10/§11 "0 false positives on the sample" counts error findings; rc 5 is pass (C §2.4 Δ). | A6 §2.2 row, §3.3 step 1; A9 AC-09.22, §8.2-5 |
| R-36 | A9 AC-09.22 calls `h trace <scenario>` without `--nodes` (rc 2 per A7). The sample player is spawned by SceneManager after the first fade, so A7's Trace cannot resolve it at row 0 (`feel.bind`) | **The sample gets a feel suite and an arena scene.** B9b adds `sample/specs/feel_arena.scene.json` -> `res://scenes/platformer/feel_arena.tscn` (root Node2D: `level_1.tscn` instance + `player.tscn` instance at the Spawn position; no SceneManager), probe scenarios `res://feel/{run,jump,tap,coyote,buffer,camera}.json` on that scene (coyote uses the level_1 ledge, `vars {"t0","k"}` per A7 §6), and `res://feel/player.feel.json`. In that file, run.* metrics take `params {"action": "move_right"}` and trace `camera` -> `Player/Camera2D`. Feel files live under `res://feel/`, so `h run res://scenarios/` does not pick them up. AC-09.22 trace part: `h trace res://feel/player.feel.json` -> rc 5 per R-35, every target metric measured, no error findings. | A9 §2.7, §3.1 (B9b file list), §7 step 8, AC-09.22 |
| R-37 | A7 FAULT-A7-01..06 `not_regex = ['^FAIL +(?!<metric>)']` also matches the verdict line `FAIL trace ...`, so these can never be CAUGHT | **Use `not_regex = ['^FAIL +(?!<metric>:)[a-z]+\.[a-z0-9_.]+:']`** (check lines only). Also fix the fold line, which breaks the check-line grammar: `OK   more: <n> metrics in range`. | A7 §5 header sentence + rows 01-06; A7 §2.2 |
| R-38 | Rule id pattern: C §2.7 `[a-z0-9][a-z0-9._-]*` rejects r1_5 ids like `class-KinematicBody2D` that A3 keeps (A3 §8.3) | **Pattern `[a-z0-9][a-zA-Z0-9._-]*`**; upper case only in undotted r1_5 ids. `assert_contract` must use it. | C §2.7 |
| R-39 | `[gd]` layer: where gdUnit4 suites for `addons/harness` run (A1 AC-01.27, A5 AC-05.25/26, A7 AC-07.22, A9 D-2); plan's unowned `gd_host` | **T1 writes `tests/helpers/gd.py`**: `run_gd_suites(area, fixture="gd_host") -> Result` copies the fixture (or `@sample`) to `$HARNESS_TMP`, runs `h sync` (with gdUnit4), copies `tests/gd/<area>/*.gd` to `<copy>/tests/<area>/`, and runs `h test --project <copy> res://tests/<area>/`. **T1 also writes the fixture `tests/fixtures/projects/gd_host/`**: C §2.11 minimum plus `[autoload]` Harness, Rng, CommandBus, Trace as `*res://addons/harness/<snake>.gd`; no tests. Each gd area has one pytest wrapper `tests/gd/<area>/test_gd_<area>.py`. A1 AC-01.27 is re-layered to [contract] and runs the runner through a helper `run_godot(args, project, timeout)` that resolves the binary as C §2.8.1 does. That is the only direct Godot call allowed in tests, and only for the runner protocol. A9 D-2 accepted (`fixture="@sample"`). | C §2.12 helpers; A1 AC-01.27; A5/A7/A9 [gd] layer text; orchestrator: ci.sh gd layer = `pytest tests/gd` |
| R-40 | P0 / A1 assumption "A2 reuses load_check" etc. | Covered by R-30. | - |
| R-41 | `docs/HARNESS.md`, `docs/ADOPTION.md` (plan §11.7) have no owner | **B8 owns both** (Phase 6). A6 keeps `docs/visual.md`. `h init --check`'s `hook.tmpl-verb` lint also runs over `docs/*.md`. | A8 §3.1, §3.4 |
| R-42 | Two movie paths: A6 `--movie` (PNG frames), A6 §2.6 says A7 uses `visual.capture`, A7 §3.5 uses its own AVI path | **Both stay, each independent.** A7 records AVI through `replay.run_scenario(kind="movie", display="xvfb", extra_args=[--write-movie ...])`. Delete A6 §2.6's A7 sentence and A7 §8.4's "if A6 ships a movie helper" clause. | A6 §2.6; A7 §8.4 |
| R-43 | A8 hook rule severities are unstated, but `h init --hook` verdicts depend on them | error: `hook.approved-write, human-only, raw-godot, readonly-agent, scratch, unmeasured-claim, bad-output, init-*` (except `init-modified`), `tmpl-*`; warning: `golden-overwrite` (ask), `tscn-structure, scene-change, busy-drop, ui-action, code-action, stop-budget, init-modified`; info: `harness-missing`. | A8 §2.5 (add a severity column) |
| R-44 | A8 D-a..D-c (`init --new`, `init --hook`, `harness.local.json`, the hook running project code) | **Accept.** C §2.2 resolution: "`init --new` may create the dir". D-d (A3 absorbing hook regexes) deferred to v0.1. | C §2.2 one clause |
| R-45 | Env vars beyond the contract list: A6/A7 `$USER`, A6 `PATH`, A8 `CLAUDE_PROJECT_DIR` | **Accept for attribution and tool lookup only.** | C §2.2: "Also read: `PATH`, `HOME`, `TMPDIR`, `USER` (attribution), `CLAUDE_PROJECT_DIR` (hook/launcher)." |
| R-46 | `CONFIG_TABLE` declared by two modules (A2 digest/scene_gen/scene_edit; A6 shot/baseline) | **Exactly one declaring module per table**: `scene` digest.py, `shot` shot.py, `run` run.py, `feel` trace.py, `hooks` init.py, `lint` lint.py, `test` test.py. Duplicates make `config.py` raise rc 3. | C §2.6 one sentence |
| R-47 | A6 `baseline approve` with nothing pending gives WARN with no warning line (C §2.3 invariant) | Emit check line `WARN proposals: none pending`. | A6 §2.3 |
| R-48 | A5 D-b (runner drives ticks; plan field renames), A7 D-b/c/d, A9 D-3 (data-only `.tres` as text; matches A8's exemption), A9 D-4, A2 §8.4 A3 owns `tscn-*`, A3 `lsp stop --all` without project | **Accept all.** | C §2.2 list: "`lsp stop --all`" |
| R-49 | A3 `--hook` vs A8 hook path; A8 relies on `h check F --no-lint --no-deps` | Consistent; no change. | - |
| R-50 | Check-line names contain spaces/dots (`SKIP autoload Rng: not shipped`, `OK   CLAUDE.md: created`, `FAIL 1280x720: ...`) | **Grammar**: name = `[^:]+` (no colon). `assert_contract` uses `^(OK\|FAIL\|SKIP\|WARN) +([^:]+): (.*)$`. | C §2.3 item 3 |

## 2. CONFLICTS

### 2.1 File ownership (spec §3 file lists; one owner per file after the decisions)
| Path | Owner | Was claimed by / note |
|---|---|---|
| `tools/harness/harness/{out,project,config,logscan,godot,proc,faults}.py`, `verbs/selftest.py`, Δ `cli.py`, `verbs/doctor.py`, `h` | A1 (B1 step 0) | C §3.1; godot.py also gets R-05/09/14/24/31/32 |
| `harness/{checkrun,apiindex,sync}.py`, `verbs/{check,import_,sync,api}.py`, `data/renames_3to4.json`, `addons/harness/runners/load_check.gd`, Δ `tools/bootstrap.sh` | A1 | `sync.py` is new (R-33) |
| `addons/harness/runners/scenario.gd` | **A5 only** | A6 §3.1 also claimed a block (R-15) |
| `addons/harness/{harness,rng,command_bus}.gd`, `harness/{scenario,replay}.py`, `verbs/run.py`, `schemas/scenario.schema.json` | A5 | `replay.py` new (R-19) |
| `addons/harness/runners/{shot,layout,_capture}.gd`, `harness/visual.py`, `verbs/{shot,baseline}.py`, `schemas/baseline.schema.json`, `docs/visual.md` | A6 | |
| `addons/harness/{trace,feel_target,feel_targets}.gd`, `addons/harness/runners/feel_targets.gd`, `harness/feel.py`, `verbs/trace.py`, `schemas/feel.schema.json` | A7 | `feel_targets.gd` exists twice (autoload dir vs runners/): legal (sync skips runners/), keep |
| `harness/scenes/*`, `verbs/{digest,scene_gen,scene_edit}.py`, `runners/{scene_digest,scene_gen,scene_edit}.gd` | A2 | |
| `harness/lint/*`, `verbs/{lint,lsp}.py`, `tools/harness/rules/*` | A3 | A1 assumed `harness/lint.py`; a package imports the same (R-29) |
| `harness/gdunit.py`, `verbs/test.py` | A4 | |
| `harness/{wiring}.py`, `verbs/init.py`, `templates/claude/**`, `docs/HARNESS.md`, `docs/ADOPTION.md` | A8 | docs ownership (R-41) |
| `templates/{sim_view,project}/**`, `sample/**` | A9 | A8 reads templates only |
| `tests/helpers/*`, `tests/conftest.py`, fixtures `clean_min`, `gd_host` | T1 | `gd_host` was unowned (R-39) |
No other overlaps. The schemas dir has 3 distinct files.

### 2.2 Rule ids
No duplicate ids across specs. Prefixes: `godot. harness. check. api. selftest.` (P0/A1), `scene.` (A2), `lint.` +
r1_5 undotted (A3), `test.` (A4), `run.` (A5), `shot.` (A6), `feel.` (A7), `hook.` (A8), `sim.` reserved/unused (A9).
Clashes: (1) the upper-case r1_5 ids against the C §2.7 regex (R-38). (2) Intended reuse: A7 re-reports A5's
`[run.scenario]`; A1's `h sync` uses `harness.sync-conflict`/`harness.sync-stale` (A1 owns `harness.*`). Similar
names from different verbs are fine: `scene.load-failed` (digest) vs `check.load-failed`, `feel.bind` vs `run.bind`.

### 2.3 Verbs, flags, output format vs the contract
- Verb list = C §2.1 closed list, each verb with one owner. `h layout` (plan) became `h shot --layout`. `h check --lsp` is dropped (R-29).
- Output: A4 15 lines (R-02); `more:` stat (R-22); check-line names (R-50); A7 fold line (R-37); `--exists` (R-26); A6 WARN line (R-47).
- `h api` and `h selftest` need no project and write to `$HARNESS_REPO/.harness/out`. `h init --new` creates a project (R-44). `h lsp stop --all` needs no project (R-48).
- Plan text superseded: `fault.yaml`/`expected_matrix.yaml` (C C11), digest <= 60 lines (R-22), `h digest --project` (R-23), runners `smoke.gd`/`api_dump.gd` (merged/dropped by A1 §3.1).

### 2.4 Autoload sets
| Where | Before | After (R-16) |
|---|---|---|
| C §2.6 default `autoloads` | Harness, Rng, CommandBus | + Trace |
| A5 `required_autoloads`, `scenario_min` | Harness, Rng, CommandBus | unchanged |
| A7 `feel_min` | + Trace | unchanged |
| A9 template/sample `[autoload]` | Harness, Rng, CommandBus, SceneManager | Harness, Rng, CommandBus, **Trace**, SceneManager |
| A8 `h init` (sync) | "3 autoloads" | 4 harness autoloads |
| `gd_host` (T1) | n/a | Harness, Rng, CommandBus, Trace |

### 2.5 Exit-code mapping
| Case | Issue | Resolution |
|---|---|---|
| `h api --exists` FAIL with no finding | breaks the FAIL invariant | R-26 |
| A5 runner rc 2 on not-synced | C maps runner rc 2 to verb rc 3 | R-34 |
| A6 `[shot.headless]` runner finding -> verb rc 4; `[shot.no-display]` -> rc 4 | verb-level ERROR override | accepted (environment class, C §2.4 row 4) |
| A4 gdUnit4 103/104 -> rc 4; 1 -> FAIL `[harness.rc]` | consistent with C §8 | ok |
| A2 `scene-gen` existing target without `--force` -> rc 2 | usage | ok |
| A6/A7 approve without a TTY -> rc 2 | usage class, same in both | ok |
| A3 `lsp diag` without daemon -> rc 4 | environment | ok |
| A8 `init --hook`: deny/block rc 1, ask/context rc 5 | needs severities | R-43 |
| A7 approve readback mismatch -> rc 3 | internal | ok |

### 2.6 Fixtures (names unique; owners)
`projects/`: clean_min, gd_host (T1/P0), scene_cases (A1), scene_host (A2), godot3_scripts, lint_base,
lint_clean_demo (A3), gd_tests (A4), scenario_min, scenario_noautoload (A5), shot_min (A6), feel_min,
feel_noautoload (A7), empty_47, hook_host (A8); `@sample` (A9). Non-project dirs: `bin/`, `logs/`, `selftest_trees/`
(P0), `gd_cases/`, `harness_trees/` (A1), `gdunit/` (A4), `tools/` (A6), `feel_csv/` (A7), `hook_inputs/` (A8), `a9/`
(A9). No collisions. Notes: `gd_cases` (A1) and `godot3_scripts/cases` (A3) both carry r1_5 snippets with small
differences (c32 has 1 vs 2 lines). They are separate fixtures, so this is acceptable; do not merge them. `scene_host` must PASS `h check` (holds under R-08).

### 2.7 Seeded faults: ids unique; counts vs plan §10 minimums
| Area | Faults (nice) | Clean | Min | Notes |
|---|---|---|---|---|
| P0 | 8 (0 after R-25) | 2 | 4 | P0-06 replaced (R-25) |
| A1 | 20 (1) | 4 | 12 | CLEAN-A1-01 fix (R-27) |
| A2 | 15 (1) | 3 | 10 | |
| A3 | 27 (2) | 3 | 15 | 13/17 get a harness.toml op (R-08) |
| A4 | 11 | 2 | 8 | |
| A5 | 12 (2) | 2 | 8 | |
| A6 | 12 (1) | 3 | 6 | |
| A7 | 11 (1) | 2 | 6 | not_regex fix (R-37) |
| A8 | 15 (2) | 4 | 8 | |
| A9 | 12 (1) | 3 | 6 | `@sample` (R-10) |
| **Total** | **143 faults** + 28 clean | | 75 | all areas >= minimum |

## 3. BLOCKING vs NON-BLOCKING

### 3.1 BLOCKING (must be applied before G1 / tag `specs-v1`; planners re-run with the listed R-ids)
| # | Spec | Fix (R-ids) | Applied by |
|---|---|---|---|
| B01 | 00 | Rule-id regex with upper case (R-38); check-line name grammar (R-50) | P0 planner |
| B02 | 00 | FAULT-P0-06 replacement, must (R-25) | P0 planner |
| B03 | 00 | Auto-import by class-set content; explicit `ensure_imported` (R-24, R-32) | P0 planner |
| B04 | 00 | Unit-import allowlist (R-01) | P0 planner |
| B05 | 00 | godot.py surface: `project=None`/`cwd`, kinds `oracle`/`lsp_start`, `spawn`, `Invocation` fields, xvfb cleanup/retry, ANSI + location fallback in logscan (R-05, R-06, R-09, R-14, R-31) | P0 planner |
| B06 | 00 | Default autoloads + Trace (R-16) | P0 planner |
| B07 | 00 | `@sample`, PNG exception, runner `load()` rule, `more:` stat, gd helper + gd_host in §2.12, env list (R-10, R-11, R-12, R-22, R-39, R-45) | P0 planner |
| B08 | 01 | `run_lint` call (R-29) | P1 planner |
| B09 | 01 | `--exists` FAIL shape (R-26) | P1 planner |
| B10 | 01 | CLEAN-A1-01 `--no-lint` (R-27) | P1 planner |
| B11 | 01 | AC-01.16 rewrite; AC-01.27 re-layer (R-28, R-39) | P1 planner |
| B12 | 01 | `sync.py` library: `ensure_synced`, `install_gdunit4`, gdUnit4 overwrite policy, autoload insertion (R-33, R-16) | P1 planner |
| B13 | 01 | Public `checkrun.load_check`; runner-incomplete attribution; godot.py xvfb section (R-30, R-25, R-14) | P1 planner |
| B14 | 02 | Adopt A1's load_check protocol through `checkrun.load_check` (R-30) | P2 planner |
| B15 | 03 | `replay_dirs = []` + fixture/test/fault adjustments; drop `h check --lsp` (R-08, R-29) | P3 planner |
| B16 | 05 | `tick_completed(0)`; `replay.run_scenario` signature; `handle` replaces + `unhandle`; `--shot-at` block in scenario.gd; not-synced rc (R-18, R-19, R-20, R-15, R-34) | P5 planner |
| B17 | 06 | Drop scenario.gd from the file list; approval predicate + provisional warning; `run_scenario` call (R-15, R-35, R-19) | P6 planner |
| B18 | 07 | Fault `not_regex` fix + fold line; `run_scenario` call (R-37, R-19) | P7 planner |
| B19 | 09 | Trace in `[autoload]` (+AC-09.2/5); `replay_dirs` in harness.toml; feel arena + suite + AC-09.22; target names/ranges (R-16, R-08, R-36, R-17, R-35) | P9 planner |
B01-B15 gate Phase 2 (T1-T4). B16-B19 gate the Phase 3 test-writers T5/T6/T7/T9 and can be re-run in parallel with
Phase 2. A4 and A8 have no blocking item.

### 3.2 NON-BLOCKING (apply with the next planner touch; builders follow this file meanwhile)
| # | Spec | Fix | Applied by |
|---|---|---|---|
| N01 | 04 | "up to 5 stat lines" (R-02) | P4 |
| N02 | 04 | `install_gdunit4` naming/policy per R-33 (A-1 text) | P4 |
| N03 | 00 | `api.` prefix (R-03); `import_` rule (R-04); dedup sentence (R-07); headless clause (R-13); one CONFIG_TABLE owner (R-46); `init --new` and `lsp stop --all` in §2.2 (R-44, R-48) | P0 (with B01-B07) |
| N04 | 01 | Mark §8.3 D-a..D-e accepted (R-03, R-04, R-05, R-06, R-07); §8.2-2 closed by R-25 | P1 |
| N05 | 02 | §8.3 deviations marked accepted (R-01, R-22, R-23); R-21 accepted | P2 |
| N06 | 03 | §8.3 deviations accepted (R-09, R-38, R-48); data layer accepted (R-01) | P3 |
| N07 | 05 | AC-05.26 adds the replace/unhandle checks (R-20) | P5 (with B16) |
| N08 | 06 | Drop A6 §2.6's A7 sentence (R-42); `WARN proposals: none pending` (R-47) | P6 |
| N09 | 07 | Drop "if A6 ships a movie helper" (R-42); D-a..D-d accepted | P7 |
| N10 | 08 | Severity column (R-43); docs ownership + docs lint (R-41); budget per R-24; D-a..D-c accepted (R-44) | P8 (before T8, Phase 6) |
| N11 | 09 | SimHost `unhandle` on `tree_exiting` (R-20); D-2..D-4 accepted | P9 (with B19) |
| N12 | plan | §3.1/§10 text (C C11), §7 A2 "<= 60 lines", A6 `h layout`, §3.2 `h check --lsp`, `gd_host` ownership | orchestrator |
| N13 | tools/dev | C5-C7, C10 (contract §3.2) + `ci.sh` gd layer = `pytest tests/gd` (R-39) | orchestrator, before Phase 2 |
| N14 | 00 §8 | Open (1) closed: autoloads instantiate under `-s` after `_init` [Run A1 K, A4 K13]; (3) answered by A6 §3.5 | P0 |
| N15 | 05 | Open Q2 answered by A6 K9 (injection under Xvfb works) | P5 |
| N16 | 01 | B1 order: build `sync.py` in step 1 (not step 5) so B4 can start right after the godot.py gate (§4) | P1 |
| N17 | all | Each spec's §8 "Deviations" marks the accepted ones with the R-id | each planner |
| N18 | 00 | Contract AC for R-24 (class edit keeping the name -> `import: fresh`) as AC-00.27 | P0 |
| N19 | 01 | AC for R-14 cannot run before A6; note in A1 §8 that A6 AC-06.19 verifies it | P1 |
| N20 | 03 | AC-03.5 wording: "with harness.toml replaced by `[lint]\nreplay_dirs = []`" | P3 (with B15) |
| N21 | 09 | `sample/feel/` probes are not counted in AC-09.7's "7/7 scenarios" | P9 (with B19) |
| N22 | 06 | AC-06.9/AC-06.23 add one provisional case (`approved_by "provisional-default"` -> rc 5) | P6 (with B17) |
| N23 | 07 | §8.4 A9 bullet: suite lives at `res://feel/player.feel.json` on `feel_arena.tscn` (R-36) | P7 |
| N24 | 08 | A8 §2.1 example "4 autoloads" (R-16) | P8 |

## 4. Build order and dependency graph

```
B1 step 0 (contract core: out project config logscan proc faults cli doctor selftest)
  └─ B1 step 1 (godot.py + load_check scripts mode + check scripts phase + sync.py)  ── GATE "core ready":
       │                                     P0/A1 contract tests for godot.py + check green (AC-00.11-15,19,20; AC-01.1-3,15)
       ├─ B3 (A3) needs only step 0; run_lint wiring meets B1 step 4 (AC-03.23)
       ├─ B4 (A4) needs godot.run kind test + sync.install_gdunit4 + ensure_imported
       └─ B1 step 2 (scenes phase, checkrun.load_check) ─► B2 (A2)
B1 steps 3-7 continue in parallel (resume, smoke, import_, api, doctor extras, selftest runner).
Phase 5: B5 (A5: autoloads, scenario.gd incl. --shot-at, replay.py) ∥ B9a (A9 templates + tactics sim; needs A1/A3/A4)
         ∥ B6 steps 1-6 (A6 scene mode; needs godot.py xvfb from B1)
         → B9b (needs A2 + B5: scenes, scenarios, feel arena/suite) → B6 step 7 (scenario mode, AC-06.25)
         → B7 (needs B5 + B9b) → B9b step 8 (provisional baselines/targets, AC-09.22)
Phase 6: T8 → B8 (needs everything; docs).
```
**What B1 must expose (step 0 + step 1) so B2-B9 can work in parallel:**
- `out.Run` (finding, stat, check, error, finish, `add_findings`), `out.render`, `out.common_parser`.
- `project.resolve`, `project.res_path`, `project.fs_path`; `config.load` with CONFIG_TABLE discovery (R-46), the
  `[harness]` keys incl. 4 default autoloads (R-16), and renderer validation (A6 §8.4).
- `logscan.scan` (R-06); `proc.run` (timeout-safe, stdin /dev/null; odiff, git).
- `godot.binary`, `godot.run` (all C kinds + `oracle`, `lsp_start`; `project=None`/`cwd`; display `headless|xvfb`
  with R-14; returns `Invocation` R-31), `godot.spawn` (R-09), `godot.ensure_imported` (R-24, R-32), kind
  expected-rc override (A4 {0,100,101,105}).
- `checkrun.load_check(run, project, res_paths, smoke=0)` (R-30, by step 2) and `runners/load_check.gd`.
- `sync.ensure_synced`, `sync.install_gdunit4`, `sync.sync_project` (R-33, in step 1 per N16).
- `faults.py` + `h selftest` (`--area`, `--faults-dir`, `@sample`) by the end of B1 so every builder can run its area.

## 5. Test-writer groupings

Phase 2 (core, parallel after T1's first deliverable):
- **T1 = P0 + A1 (+ bootstrap C4).** First deliverable, before T2-T4 start (short, ~1 agent step): `tests/conftest.py`
  (markers, sys.path); `tests/helpers/h.py` (`run_h`, `Result`, `copy_fixture` incl. `@sample` and the B3 exclusions,
  `assert_contract` with the R-38/R-50 regexes, the `more:` stat and the run.json schema, plus `run_godot` (R-39));
  `tests/helpers/gd.py` (`run_gd_suites`, R-39); fixtures `clean_min`, `gd_host`. Then the rest: P0/A1 ACs, faults
  FAULT-P0-* (with R-25), FAULT-A1-* (with R-27), fixtures `scene_cases`, `gd_cases`, `harness_trees/sync_src`, `bin/`,
  `logs/`, `selftest_trees/`. Pathguard areas `a1,p0,bootstrap`.
- **T2 = A2** (scene_host, specs, r1_4 case copies). **T3 = A3** (godot3_scripts, lint_base, lint_clean_demo with its
  harness.toml per R-08). **T4 = A4** (gd_tests, gdunit recordings).
- T2-T4 read the helper API from C §2.12 + this file. If T1 is late they code against that signature and must not
  write their own copies of the helpers.

Phase 3 (during core build): **T5 = A5**, **T9 = A9**, **T6 = A6** (reuses `scenario_min` from T5 for AC-06.25, so
start T6 after T5 has written that fixture, or have T6 copy-on-read it at test time), **T7 = A7**. Phase 6: **T8 = A8**.

## 6. Items for the human (only these)
1. **Provisional sample artefacts (R-35, D4).** Builders write sample baselines/feel targets marked `provisional-default`
   (they give WARN, never PASS) until you approve them at Gate G3 with `h baseline approve` / `h trace --approve`.
   OK? Otherwise the sample stays rc 1 until you approve.
2. **Lint default (R-08).** Determinism warnings for idle Tween/Timer/AnimationPlayer apply only to `sim_dirs`
   plus the dirs a project lists in `replay_dirs`. The template and sample list `res://` (strict). New user projects
   start quiet. Override if you want strict by default.
3. (Info, no answer needed) Dogfood budget: 3 nested `claude -p` tasks at <= $1.50 each (A8 §4.1).

## 7. Reviewer spikes ([Run], scratchpad `rev/`, Godot 4.7.stable.official.5b4e0cb0f, 2026-10-15)
- R-25: a `-s` runner that instantiates a scene whose `_ready` calls `get_tree().quit(0)`, then awaits 2
  `physics_frame`s before printing `done`. Output: banner, `@@H begin`, no `done`, **rc 0**. A `--smoke` load-check
  therefore yields `[harness.runner-incomplete]`. This replaces the unfireable autoload `_init` premise.
- R-24: after `--import`, `.godot/global_script_class_cache.cfg` = `list=[{"base": &"Node2D", "class": &"Hello",
  "icon": "", "is_abstract": false, "is_tool": false, "language": &"GDScript", "path": "res://scripts/hello.gd"}]`,
  so (class, path) pairs are directly comparable.

## 8. Re-check after the planner re-runs (v2, 2026-10-15)

Inputs: specs at HEAD `b2c990a` (00 v2, 01 v1.1, 02 v2, 03 v2, 04 re-run N01/N02, 05 v2, 06 v1.1, 07 v2, 09 v2; 08
not re-run, which is expected because it has no B item). For each B item I read the cited spec text and checked
that the R-id wording is applied, not only cited.

### 8.1 Blocking items
| # | R-ids | Status | Where applied |
|---|---|---|---|
| B01 | R-38, R-50 | applied | C §2.7 (pattern + `assert_contract`), §2.3 item 3 (check-line grammar) |
| B02 | R-25 | applied | C §5 FAULT-P0-06 (must, quit_early, `--smoke`), §8 open (1) closed, §3.4 spike |
| B03 | R-24, R-32 | applied | C §2.8.7 (explicit, class-set content, scope, no mtime), AC-00.27 (N18) |
| B04 | R-01 | applied | C §2.12 last bullet (closed list), §2.9 heading |
| B05 | R-05, R-06, R-09, R-14, R-31 | applied | C §2.8.2 (`project=None`/`cwd`, kinds `oracle`/`lsp_start`), §2.8.3 (xvfb cleanup/retry), §2.8.4 (ANSI, fallback), §2.8.6 (`oracle` {0}), §2.9 (`spawn`, `Invocation`, no auto-add), run.json `retried`/`display_failed` |
| B06 | R-16 | applied | C §2.6 default `autoloads` with Trace |
| B07 | R-10, R-11, R-12, R-22, R-39, R-45 | applied | C §2.10 (`@sample`), §2.11 (PNG), §2.8.5 (`load()` libraries), §2.3 (`more:`), §2.12 + §6 (`run_godot`, `gd.py`, `gd_host`), §2.2 (env) |
| B08 | R-29 | applied | A1 §3.2 step 9, §8.4 |
| B09 | R-26 | applied | A1 §2.4 `--exists` bullet, AC-01.21 |
| B10 | R-27 | applied | A1 §5 CLEAN-A1-01 |
| B11 | R-28, R-39 | applied | A1 AC-01.16 (regex), AC-01.27 ([contract] via `run_godot`) |
| B12 | R-33, R-16 | applied | A1 §2.3 (overwrite policy, insertion rule), §3.1 (`ensure_synced`, `install_gdunit4`, `sync_project`), AC-01.18 |
| B13 | R-30, R-25, R-14 | applied | A1 §3.1 (`checkrun.load_check`), §3.2 step 5 + AC-01.31, §3.8 |
| B14 | R-30 | applied | A2 §3.3 (load-check paragraph, scene-gen/scene-edit steps), §8.4 |
| B15 | R-08, R-29 | applied | A3 §2.6 (default `[]`), §6.3, AC-03.5, AC-03.16, FAULT-A3-13/17, §8.2 closed; §2.2/§2.3 no `h check --lsp` |
| B16 | R-18, R-19, R-20, R-15, R-34 | applied | A5 §3.2 steps 1, 2, 6; §2.3 (`handle` replaces, `unhandle`), AC-05.26; §2.7 + §3.1 (`replay.py`, exact R-19 signature); §3.3 |
| B17 | R-15, R-35, R-19 | applied | A6 §3.1 (no scenario.gd), §2.2 rows, §3.3 step 1, §3.2 step 3, AC-06.9/23 (N22) |
| B18 | R-37, R-19 | applied | A7 §5 header + FAULT-A7-01..06, §2.2 fold line, §3.3 step 3, §3.5 |
| B19 | R-16, R-08, R-36, R-17, R-35 | applied | A9 §2.4 + AC-09.2/5 (5 autoloads, Trace 4th), §2.4 harness.toml `replay_dirs`, §2.7 (feel arena, suite, R-17 names/ranges), §3.1 file list, §7 step 8, AC-09.22 |

Non-blocking items checked as applied: N01-N09, N11, N14, N15, N16, N17, N18, N19, N20,
N21, N22, N23. Still open, as planned: N10 and N24 (A8, P8 before T8), N12 and N13 (orchestrator).

### 8.2 Cross-spec checks (the orchestrator's list)
- (a) `replay.run_scenario`: consistent. A5 §2.7 says it returns `RunResult.findings` and adds nothing. `h run` (A5
  §3.3), A6 §3.2 step 3 and A7 §3.3 step 3 each add the findings themselves. The `[U ...]` notes in A6 §3.2 step 2 and
  A7 §3.3 step 3 are stale and are resolved by A5 v2 (N25).
- (b) `checkrun.load_check`: A1 §3.1 and A2 §3.3/§8.4 use the same signature `(run, project, res_paths, smoke=0) ->
  list[dict]`. Both specs agree that it returns findings without adding them, does not import, and that A2 calls
  `ensure_imported` first. Consistent.
- (c) `install_gdunit4` -> `installed (pin changed)` (A1 §3.1, D-g): accepted, R-53.
- (d) Autoload counts: the C §2.6 / A1 default has 4 entries; A5 `required_autoloads` and `scenario_min` keep 3;
  A7 `feel_min`, `gd_host` and A9 have 4 harness entries (A9 lists 5 with SceneManager). A8 §2.1 still shows
  "3 autoloads" (N24, open, non-blocking). Consistent.
- (e) Line counts: 00 = 491 (over the orchestrator's 480 tolerance and the plan's 450), 01 = 480, the rest <= 475.
  Accepted for `specs-v1` (R-56).

### 8.3 New decisions (normative; where one disagrees with a spec, REVIEW wins until the next planner touch)
| ID | Topic | Decision | Amend |
|---|---|---|---|
| R-51 | `@sample` copies exclude `addons/harness/` (C §2.10), but the sample declares the harness autoloads. Every Godot run then logs `ERROR: Failed loading resource: res://addons/harness/harness.gd` and `Failed to instantiate an autoload` [Run §8.4], so A9 AC-09.3/6 (`h check`/`h test` on a copy) and A9 `check`/`test` faults could never PASS. Only `h run`/`h shot`/`h trace` call `ensure_synced`. | **An `@sample` copy is synced as part of the copy.** `copy_fixture("@sample", dest)` (T1) and `faults.py` (selftest, before the `apply` ops) run `h sync --no-gdunit --project <copy>` with `HARNESS_OUT` under the test/entry dir. A non-zero rc counts as a helper error, or as `BROKEN` in selftest. `h sync` leaves the sample's `project.godot` byte-identical (R-16), so the copy differs from the repo only in `addons/harness/`. No other fixture is affected: `gd_host` is synced by `run_gd_suites`, `feel_min` and `scenario_min` are synced by their verbs, and no other fixture declares a harness autoload. | C §2.10 `@sample` sentence, §2.12 `copy_fixture` text (P0, N26) |
| R-52 | Kind `movie` (A7 `run_scenario(kind="movie")`) is missing from C §2.8.2 "runner-style kinds" and from the C §2.8.6 expected-rc sets | **`movie` is runner-style**: it takes `-s <runner>` and its expected rc is {0,1}, the same as `scenario`/`shot`. Timeout stays 300 s. | C §2.8.2, §2.8.6 (P0, N26) |
| R-53 | A1 `install_gdunit4` also returns `installed (pin changed)` (harness-installed copy at another version was overwritten), which is not in the R-33 list | **Accept.** R-33's return set is `present` \| `installed (was missing)` \| `installed (pin changed)`. A4 prints the value verbatim in its `gdunit4:` stat, so A4 §2.2/§8 A-1 need only the list update. | A4 §3.2 step 2, §8 A-1 (P4, N27); A1 §8.3 D-g drop the `[U]` |
| R-54 | `--fixed-fps` duplicated: `run_scenario` always passes `--fixed-fps <fps>`, yet A7 §3.5 adds `"--fixed-fps", "<tick_rate>"` to `extra_args` and A6 §3.2 step 3 passes "size/movie args as above" | **`run_scenario` owns `--fixed-fps`.** Callers never put `--fixed-fps` in `extra_args`: A7's movie passes `fps=tick_rate`, and A6 passes only `--resolution`/`--write-movie`. A builder that sees a duplicate drops the caller's copy. | A6 §3.2 step 3, A7 §3.5 (N25) |
| R-55 | Stale `[U]` markers that point to "until the A5 re-plan lands" (A6 §3.2 step 2, A7 §3.3 step 3) | Resolved by A5 v2 §2.7: `run_scenario` does no sync/import and adds no findings. The markers are editorial. | A6, A7 (N25) |
| R-56 | 00_contract is 491 lines (plan cap 450, orchestrator tolerance 480) | **Accept for `specs-v1`.** The overrun comes from normative R-text, and a trim must not reword decisions. At its next touch P0 moves the §8.1 R-id list (11 lines) to a one-line pointer to REVIEW §1. No other spec is over 480. | 00 §8.1 (P0, N26) |
| R-57 | Multi-scenario check lines `OK   res://...json: ...` do not match the R-50 grammar (name `[^:]+`) (T5 D-1) | **Check-line names never contain `:`.** `h run` prints scenario check lines with the path relative to the project, without the `res://` prefix (`OK   scenarios/jump.json: 3/3 asserts`). Finding messages may still use `res://` paths. Tests use the strict `assert_contract` with no wrapper. | A5 §2.2 (T5, B5) |
| R-58 | `jump.fall_rise_ratio` range [1.2, 3] (A7 §8 / R-17) contradicts the metric: it is fall_time / time_to_apex, and with FALL_GRAVITY = 2x rise gravity the ratio is about 0.71 (T7 [Run] model) | **Provisional target is [0.5, 0.9]** for the sample and for the A7 `feel_min` fixture; FAULT-A7-02 (constant gravity, ratio 1.0) still fails. R-17 ranges elsewhere unchanged. | A7 §8 target list, A9 §2.7 data files |

### 8.4 Spike ([Run], scratchpad `rev2/`, Godot 4.7.stable.official.5b4e0cb0f)
Project with `[autoload] Harness="*res://addons/harness/harness.gd"` and no such file. `--import` gives rc 0 and logs
`ERROR: Attempt to open script ... 'File not found'`, `ERROR: Failed loading resource: res://addons/harness/harness.gd.`
and `ERROR: Failed to create an autoload ...`. A `-s` runner gives rc 0, prints `begin`/`done`, and logs `ERROR: Failed to
instantiate an autoload, can't load from path: ...`. Under C §2.8.4 these lines become `godot.load-failed`/`godot.error`
errors, so the verb FAILs (R-51).

### 8.5 New non-blocking items (apply at the next planner touch)
| # | Spec | Fix | Applied by |
|---|---|---|---|
| N25 | 06, 07 | Drop the stale `[U]` markers (R-55); remove `--fixed-fps` from caller `extra_args` (R-54) | P6, P7 |
| N26 | 00 | `@sample` copy sync (R-51); `movie` runner-style + rc set (R-52); move §8.1 list to a REVIEW pointer (R-56) | P0 |
| N27 | 04, 01 | `installed (pin changed)` in the return set (R-53) | P4, P1 |
| N28 | 09 | AC-09.3/6 note: "copy" = `copy_fixture("@sample")`, which includes the R-51 sync | P9 |
| N29 | tests | T1 implements R-51 in `copy_fixture`; B1 implements it in `faults.py` (both follow this file now) | T1, B1 |

**Re-check verdict: G1 passed.** Every B01-B19 item is applied and no new blocking item remains. R-51..R-56 are
REVIEW-normative now, and T1/T9/B1/B5-B7 follow them without waiting for N25-N29. Tag `specs-v1` once the
orchestrator commits.
