# 01 Core CLI: shim, godot.py, import, sync, api, check, doctor, selftest (A1)

Status: spec v1.1, 2026-10-15, Opus planner P1 re-run (REVIEW B08-B13, N04/N16/N17/N19 applied). Conforms to
`00_contract.md` (cited as "C §x") and `REVIEW.md` (R-ids; REVIEW wins on conflict); deviations are listed in §8.3.
Tags: [Run] verified in §3.6 spikes (Godot 4.7.stable.official.5b4e0cb0f), [U] unverified.

## 1. Purpose and failure modes covered

A1 is the first builder: the contract core (C §3.1 step 0) plus `h check`, `h api`, `h import`, `h sync`, `h doctor`,
`h selftest`, plus the shared libraries `godot.py`, `checkrun.load_check`, `sync.py`. Failure modes (plan F-ids):
**F1/F2** Godot-3 idioms / hallucinated API (`h check` catches 24/35 r1_5 snippets at parse time [Run]; `h api` gives
"renamed to X" / "did you mean"; `--exists` for A8 hooks). **F3** silent scene breakage (load+instantiate with Logger
capture; every detectable r1_4 case FAILs). **F4** exit codes lie (Logger records are the signal; hang, crash and
early quit become findings [Run §3.6 K]). **F5** runtime-only errors (`--smoke` catches 8/8 r1_5 R-class [Run]).
**F7** class cache / fresh clone (C §2.8.7 + §3.3). **F11** noisy output (C §2.3; one Godot process per phase).
D-ids: none changed; uses D1 (GDScript only) and D5 (<= ~500 files per check).

## 2. Interfaces

All verbs: C §2.1-2.5 (shim, common flags `--project/--strict/-h`, stdout grammar, rc 0-5, run dir). Only the
verb-specific parts are listed here. Rule ids owned by A1: `godot.*`, `harness.*`, `check.*`, `selftest.*`, and the
prefix `api.*` (R-03).

### 2.1 `h check [PATH...] [--changed] [--smoke] [--smoke-frames N] [--no-lint] [--no-deps] [--include-addons]`
- PATH: file or dir, cwd-relative, absolute, or `res://...`; must lie inside the project, else rc 2
  `ERROR check usage: path outside project: <p>`; missing path: rc 2 `ERROR check usage: no such file: <p>`.
- File set: `*.gd`, `*.tscn`, `*.tres` under PATHs (default: project root), excluding `.godot/`, `.harness/`, hidden
  dirs, dirs containing `.gdignore`, and `addons/` unless `--include-addons` (or PATH is inside `addons/`).
- Dependents (unless `--no-deps`): when PATHs or `--changed` select files, every project `.tscn/.tres` whose text
  contains `path="res://<selected file>"` is added (r1_4 rule 19). One level only.
- `--changed`: files changed vs git `HEAD` (`git diff --name-only HEAD` + untracked, not ignored) inside the project,
  plus dependents. Not a git work tree: rc 2 `ERROR check usage: --changed needs a git work tree`. Empty set: PASS.
- `--smoke`: scenes phase also adds each instantiated scene under `root` and awaits N physics frames (default 2,
  1-600); runs `_ready`/`_physics_process` code. Off by default (runs project code with side effects).
- `--no-lint`: skip the A3 phase. Lint is otherwise called through `harness.lint.run_lint` if importable (§3.2
  step 9, R-29).
- Stat lines, in order: `project:`, `import: ran (<why>)|fresh`, `files: <a> .gd, <b> .tscn, <c> .tres` (omit zero
  kinds, but at least `0 .gd`), `phases: scripts <s>s, scenes <s>s, lint <s>s|skipped (<why>), smoke on|off`
  (`<why>` = `--no-lint` or `harness.lint not installed`).
- Verdict reason: `<e> errors, <w> warnings in <n> files (<t>s)` or `0 findings in <n> files (<t>s)` (C §2.3).
- Rules emitted: scan/Logger rules of C §2.8.4 (`godot.*`); `check.load-failed` (ResourceLoader returned null),
  `check.instantiate-failed` (PackedScene.instantiate() returned null), `harness.hang`/`harness.crash` located at the
  file being checked when the runner died, `harness.rc` warning when the process rc differs from the runner's
  `done` rc (an autoload called `quit()`, §3.6 K), `harness.runner-incomplete` at the item when project code quits
  rc 0 before `done` (§3.2 step 5, R-25), plus whatever `harness.lint` adds.
```
$ tools/harness/h check --project /tmp/h/scene_cases --smoke
FAIL check 3 errors, 0 warnings in 6 files (1.9s)
project: /tmp/h/scene_cases
import: fresh
files: 3 .gd, 3 .tscn
phases: scripts 0.3s, scenes 0.4s, lint skipped (harness.lint not installed), smoke on
res://cases/c13_two_roots.tscn: [check.instantiate-failed] error: Invalid scene: node Root2 does not specify its parent node.
res://cases/c16_syntax_error.tscn:5: [check.load-failed] error: Parse Error: Parse error. [Resource file res://cases/c16_syntax_error.tscn:5]
res://scripts/null_ready.gd:4: [godot.script-error] error: Invalid call. Nonexistent function 'foo' in base 'Nil'.
log: /tmp/h/scene_cases/.harness/out/20261015T150102Z-check-4be1/
```

### 2.2 `h import [--force]`
Always runs `--import` (kind `import`, timeout 180 s, retry once on rc 134, C §2.8.3). `--force` deletes `.godot/`
first. Stats: `project:`, `import: ran (requested|forced)`, `duration: <s>s`. Import log findings count (a broken
scene can log `ERROR: res://x.tscn:1 - Parse Error: ...` at import [Run]). PASS / FAIL / WARN per C §2.4.

### 2.3 `h sync [--no-gdunit] [--check]` and the `harness.sync` library (R-33)
`verbs/sync.py` is a thin wrapper over `sync.sync_project` (§3.1; also used by A4-A7).
- Mirrors `$HARNESS_REPO/addons/harness/` (excluding `runners/`, `*.uid` and `.import` files) into
  `<project>/addons/harness/` (extra files there are deleted), then writes `addons/harness/.sync.json`
  `{"schema":"harness.sync/1","source_hash":"<sha256 over sorted (relpath, bytes)>","gdunit4_commit":"<sha|null>"}`
  (`gdunit4_commit` non-null only when the harness installed gdUnit4).
- gdUnit4 (unless `--no-gdunit`) = `install_gdunit4` (§3.1): copies `<HARNESS_CACHE>/gdunit4/addons/gdUnit4/` minus
  `test/` and `*.uid` to `<project>/addons/gdUnit4/` when missing. An existing addon whose `plugin.cfg` version differs
  from the pin is overwritten only if `.sync.json.gdunit4_commit` is non-null (harness-installed); otherwise rc 4
  `gdUnit4 <v> in project, harness pins 6.2.2 (run h sync)` and the user's copy is left untouched. Cache missing:
  rc 4 `gdUnit4 not in cache (run tools/bootstrap.sh)`. Plugin enabling is not done (A4 decides, §8.2).
- Autoloads (R-16): for each name in harness.toml `[harness] autoloads` (default
  `["Harness","Rng","CommandBus","Trace"]`, C §2.6), file `addons/harness/<snake_case(name)>.gd`. If the file exists,
  ensure `[autoload]` in `project.godot` has `<Name>="*res://addons/harness/<snake>.gd"`: a missing entry goes after
  the last key line of the existing `[autoload]` section (new section at file end only if none); lines are never
  reordered, so the A9 template order (Harness, Rng, CommandBus, Trace, SceneManager) stays byte-identical. Not
  shipped: `SKIP autoload <Name>: not shipped`. Different existing value: `res://project.godot:
  [harness.sync-conflict] error: autoload <Name> already set to <v>`, no write.
- Check lines: `OK addons/harness: <n> files (<k> changed)`, `OK gdunit4: <tag> <sha12>`, one per autoload.
- `--check`: writes nothing; FAIL with `[harness.sync-stale] error` per out-of-date part. Idempotent: a second sync
  changes 0 files and leaves `project.godot` byte-identical.

### 2.4 `h api` (no project needed)
```
h api <Name>                 # Class | Class.member | global function | annotation | constant
h api <Name> --all           # class: list members (<= 30 lines, then `more:` stat)
h api --search <substr> [--limit N]   # case-insensitive substring over keys; default limit 20, max 30
h api --exists <Name>        # hook mode: PASS rc 0 = 2 lines (verdict, log); FAIL rc 1 = 3 lines (R-26)
h api --rebuild              # (re)builds the cache index via Godot (kind doctool)
```
- Resolution of a bare name, first hit wins: class / builtin type; `@GDScript.<n>` (GDScript-only functions such
  as `preload`, `range`, `len`, annotations `@export_range`); `@GlobalScope.<n>` (utility functions `lerp`, global
  enum values `KEY_A`); singleton. `Class.member` walks the `inherits` chain (`CharacterBody2D.position` resolves on
  `Node2D`). Exact case first, then case-insensitive.
- Output (stat lines only, C §2.3): `kind: method|property|signal|constant|class|builtin|function|annotation`,
  `sig: <signature>`, `defined-in: <Class>` (if inherited), `inherits: A < B < Object` (classes),
  `doc: <first sentence of the description, BBCode tags removed, <= 160 chars>`, for classes
  `members: <m> methods, <p> properties, <s> signals`. `--all`/`--search`: `match: <key>  <sig>` lines, then
  `more: <k> (narrow the search)`.
- Not found: rc 1, `FAIL api '<q>' not in Godot 4.7`, finding `-: [api.not-found] error: <q> does not exist in
  4.7 (hint: did you mean <a>, <b>?)` (up to 3 candidates: case-insensitive Levenshtein <= max(2, len/4), same class
  incl. inherited members for `Class.member`, else all class names / globals). Renamed in Godot 4 (rename map, §3.5):
  `FAIL api 'KinematicBody2D' not in Godot 4.7 (renamed: CharacterBody2D)`, stat `suggest: CharacterBody2D`, finding
  `-: [api.renamed] error: KinematicBody2D was renamed in Godot 4 (hint: use CharacterBody2D)`. Member renames work
  too (`Control.rect_position` -> `Control.position`, `@GlobalScope.rand_range` -> `randf_range`).
- `--exists` (R-26): PASS = verdict + `log:`. FAIL = verdict, then exactly one finding
  `-: [api.not-found] error: <q> does not exist in Godot 4.7` (or `-: [api.renamed] error: <q> was renamed in Godot 4
  (hint: use <new>)`), then `log:`; no stat lines, no did-you-mean search (keeps C §2.3 "FAIL => error finding").
- Index missing: built on first use (same as `--rebuild`); Godot missing then: rc 4.
```
$ tools/harness/h api Node2D.position
PASS api Node2D.position (property)
kind: property
sig: var position: Vector2
doc: Position, relative to the node's parent.
log: .harness/out/20261015T150301Z-api-91c2/
```

### 2.5 `h doctor [--project DIR]`
C §2.3 example and C3. Required checks (missing -> `FAIL` line, rc 4): `godot` (version string), `gdunit4` (pinned
commit), `odiff`, `venv`, `xvfb-run`, `compare`. Extra A1 checks: `api` (`OK api: index <n> entries` or
`SKIP api: not built (h api --rebuild)`; never affects the verdict). With an explicit `--project` (or a resolvable
project) also `sync` (`OK`/`WARN sync: stale (h sync)`/`SKIP sync: not synced`) and `import`
(`OK import: fresh`/`WARN import: stale (<why>)`). WARN lines give rc 5. Budget <= 5 s (version cache C §2.8.1).

### 2.6 `h selftest`
Exactly C §2.10. A1 adds only fault/clean entries (§5).

### 2.7 Runner `addons/harness/runners/load_check.gd` (run by absolute path, C §2.8.5)
User args: `--mode scripts|scenes`, `--list <abs path of a UTF-8 file, one res:// path per line>`,
`[--smoke N]`. Per item it prints `@@H {"t":"data","ev":"begin","path":P}`, loads with
`ResourceLoader.load(P, "", CACHE_MODE_IGNORE)`, for scenes `instantiate()` (+ smoke frames), frees, then
`@@H {"t":"data","ev":"end","path":P,"status":"ok|load-failed|instantiate-failed","recs":[R...]}` where R =
`{"type":0|1|2,"file":str,"line":int,"msg":str,"bt":["res://f.gd:12",...]}` (Logger `_log_error`: error_type
ERROR/WARNING/SCRIPT; `bt` = frames of `script_backtraces`). Last: `{"t":"done","rc":0|1}` then `quit(rc)`.
rc 2 on bad args. Never calls `.new()` on loaded scripts (S2). Not part of the black-box surface except through
`h check` and `checkrun.load_check` (§3.1); contract tests may run it directly only via the T1 helper
`run_godot(args, project, timeout)` (C §2.12, R-39). A2 reuses this protocol unchanged (R-30).

### 2.8 Config keys
No new table. A1 reads `[harness] godot, godot_version, autoloads`, `[timeouts]`, `[scan] ignore` (C §2.6).
API index: `$HARNESS_CACHE/api/<godot_version_string>/{extension_api.json,@GDScript.xml,index.json}`; index.json =
`{"schema":"harness.api-index/1","godot_version":"...","entries":{"<key>":{"k":kind,"sig":...,"d":...,"in":...}}}`.

## 3. Design

### 3.1 Files to create (builder B1; exact paths)
Step 0 (C §3.1, all B1): `tools/harness/harness/{out,project,config,logscan,godot,proc,faults}.py`,
`verbs/selftest.py`; Δ `cli.py`, `verbs/doctor.py`, `tools/harness/h` (C1-C3, C8, C9).
A1 proper (under `tools/harness/harness/`): `verbs/{check,import_,sync,api}.py` (`import_` -> `h import`, R-04),
`checkrun.py` (phase driver, record->finding mapping, resume), `sync.py` (R-33), `apiindex.py` (build, load, lookup,
Levenshtein), `data/renames_3to4.json` (copy of `.claude/research/scripts/r1_5_lint/renames.json`); plus
`addons/harness/runners/load_check.gd` (port of `.claude/research/scripts/r1_4_scene_format/load_check.gd` + §2.7
records) and Δ `tools/bootstrap.sh` step 8 (§3.5). `godot.py` also exposes `spawn` (R-09), `ensure_imported`
(R-24, R-32) and §3.8 (R-14); `godot.run` returns `Invocation` and never adds findings to the Run (R-31). Not
created (vs plan §7): `runners/smoke.gd` (= `load_check --smoke`), `runners/api_dump.gd` (index built in Python).
Public library API for other areas (not importable by unit tests, R-01):
- `checkrun.load_check(run, project, res_paths: list[str], smoke: int = 0) -> list[dict]` (R-30): §3.2 steps 3-8
  without file-set building, import or lint. Returns findings as dicts (C §2.7 fields) and does NOT add them to the
  Run; its invocations go to run.json. `h check` uses it; A2 calls it for pre/post-write checks.
- `sync.ensure_synced(run, project) -> str` (`fresh` | `ran (<why>)`): mirrors `addons/harness/` when project.godot
  declares any harness autoload and `.sync.json.source_hash` is missing or differs. Never edits project.godot or
  installs gdUnit4.
- `sync.install_gdunit4(run, project) -> str` (`present` | `installed (was missing)` | `installed (pin changed)`):
  §2.3 policy (A4 K17); a user's own differing copy gives the rc 4 error of §2.3.
- `sync.sync_project(run, project, gdunit=True, check=False)` = `h sync`.

### 3.2 `h check` algorithm (`checkrun.py`)
1. Resolve project, config, binary (C §2.8.1). Build the file set (§2.1), sorted by res:// path.
2. `godot.ensure_imported` (§3.3). If the import invocation itself failed by rc/hang/crash: emit its findings,
   `SKIP scripts/scenes: import failed` check lines, stop. Import scan findings (broken resources) count normally.
3. **Scripts phase**: one invocation, kind `runner`, `load_check.gd --mode scripts --list <run dir>/artifacts/
   scripts.txt`. Batch, not per-file (10-35x faster, same locations [Run §3.6 A-C]).
4. **Scenes phase**: one invocation, kind `runner` (`smoke` with `--smoke`), `--mode scenes` over `.tscn/.tres`.
   Runs after scripts so parse errors are reported even if a scene hangs in `_init`.
5. **Resume**: if an invocation times out or crashes, the item with `begin` but no `end` gets `[harness.hang]` /
   `[harness.crash]` at its path; when the process ends rc 0 with an item that has `begin` but no `end` (project code
   called `quit()`, e.g. `get_tree().quit(0)` in `_ready` under `--smoke` [Run REVIEW §7]), that item gets
   `[harness.runner-incomplete] error` instead (R-25, FAULT-P0-06). In all three cases items after it are re-run in a
   new invocation (at most 3 resumes per phase; then `SKIP <phase>: <k> files not checked after 3 hangs`). Expected
   wall for one hang = timeout + ~1 s. A missing `done` with no open item stays the C §2.8.6 runner-incomplete at `-`.
6. **Record -> finding**: classify each R by rendering it as a log line (`SCRIPT ERROR: msg` for type 2,
   `ERROR: msg` for 0, `WARNING: msg` for 1) and applying the logscan rule table (same ids, severities, protection).
   Location, first that applies: R.file if `res://`; first `res://` frame in R.bt; first `res://<path>:<line>`
   token in R.msg; the item path without line. Status `load-failed`/`instantiate-failed` adds one
   `check.load-failed`/`check.instantiate-failed` error at the item, message = the first R whose msg contains
   `Parse Error`/`Invalid scene`/`res://`, else the first R; R messages starting `Condition "` on such items become
   `info`. A `godot.script-load-failed` finding is dropped when the same path already has a `godot.parse-error`.
7. **Scan merge**: logscan also runs over each invocation log; a scan finding is dropped when a runner R had the
   same message (after removing a leading `Parse Error: ` and surrounding whitespace). What remains is output the
   Logger did not see: crash lines, autoload errors after `done` (autoloads run after the runner's `_init` [Run K]).
8. **rc merge**: C §2.8.6, plus: process rc != `done.rc` -> `[harness.rc] warning: exit code <rc> but runner reported
   <done> (project code called quit()?)`; the verdict never improves.
9. **Lint phase** (unless `--no-lint`, then `lint skipped (--no-lint)`), R-29: if `harness.lint` imports, call
   `harness.lint.run_lint(run, project, None, "full")` when no PATH and no `--changed` were given (lints
   project.godot too); otherwise `run_lint(run, project, <selected files incl. dependents>, "full")` (A3 still applies
   its `exclude`). ImportError -> `lint skipped (harness.lint not installed)`; other exceptions -> rc 3 per C §2.9.
10. `run.finish(reason)`. All file lists and per-phase timings go to `run.json` `extra.check`.

### 3.3 Auto-import refinements (godot.py, C §2.8.7)
Base rule per C §2.8.7 (R-24): content-based class-set staleness ((class, res path) pairs of the cache `list` vs
`class_name` lines of every project `*.gd`); no mtime rule. Verbs call `godot.ensure_imported` explicitly (R-32).
Import also runs when (a) a script path listed in `global_script_class_cache.cfg` no longer exists, or (b) a file
with an importable extension (`png jpg jpeg webp svg bmp tga wav ogg mp3 glb gltf fbx obj ttf otf woff woff2`)
lacks `<file>.import` or is newer than it [U: (b) not spiked; cheap stat-only rule]. `<why>` strings:
`no .godot/`, `no class cache`, `stale class cache (<file>)`, `missing script (<file>)`, `unimported asset (<file>)`.

### 3.4 Logscan details (now normative in C §2.8.4, R-06)
ANSI CSI strip and the `res://F:L`-in-line location fallback [Run E]; absolute-path backtrace frames are never used as
locations. B1 builds them in `logscan.py`; AC-00.16 and AC-01.26 cover them.

### 3.5 `h api` index and the bootstrap --doctool gap
- Gap root cause [Run F]: `--doctool <dir>` needs `<dir>` to exist (rc 1 otherwise); bootstrap passed a
  not-yet-created `$S/doc` and guarded only on `extension_api.json`. `--dump-extension-api-with-docs --path <proj>`
  writes a correct file then aborts rc 134; without `--path` it exits 0.
- `--rebuild`: in a fresh `$HARNESS_TMP/api-<run id>/` run (kind `doctool`, `project=None`, cwd = that dir, R-05)
  `--headless --dump-extension-api-with-docs` and `--headless --doctool <dir>/doc` (after mkdir); copy
  `extension_api.json` and `doc/modules/gdscript/doc_classes/@GDScript.xml` to the cache dir; build `index.json`
  (29,551 keys, 4.65 MB, build 0.27 s, reload 0.03 s [Run D]); write atomically; delete the scratch dir. Rebuild when
  index.json is missing or its `godot_version` differs.
- Keys: `Class`, `Class.member` (methods with typed args/defaults/return, properties, signals, enum values,
  constants), builtin types + members, `@GlobalScope.<fn|enum value>`, `@GDScript.<fn|@annotation>`, singletons.
  Rename map: the `*_renames` tables of `renames.json` (values stored quoted, e.g. `"\"CharacterBody2D\""`: strip).
- Δ bootstrap step 8: `"$ROOT/tools/harness/h" api --rebuild >"$LOG" 2>&1 || echo "WARN: api index failed"`, guarded
  by `[ -f "$CACHE/api/<version string>/index.json" ]` (interim fix: `mkdir -p "$S/doc"` + guard on `@GDScript.xml`).

### 3.6 Spikes (scratchpad `a1/`, all [Run], Godot 4.7.stable.official.5b4e0cb0f, 4 cores)
- A. 52-script project (3 broken, 1 static-init, 1 preload of a broken script): per-file `--check-only` 10.33 s
  serial, 2.80 s `xargs -P 4`; batch Logger runner 0.18 s (REUSE) / 0.28 s (IGNORE); same 4 failing files.
- B. Messages identical between modes (`SCRIPT ERROR: Parse Error: ...` + `at: GDScript::reload (res://F:L)`; Logger
  R carries file/line). Preload of a broken script: `Could not resolve script` at the preload line. `$Child` in a
  member initializer: parse error `(Warning treated as error.)`. Warnings such as an unused local are not printed.
- C. r1_5 cases (35 files): batch = per-file, 24 `GDScript::reload` locations (lines as in §6); batch 0.29 s.
- D. API index: `Input.is_action_just_pressed` -> `func is_action_just_pressed(action: StringName, exact_match: bool
  = false) -> bool`; `KinematicBody2D` absent from the dump, in `class_renames` -> `CharacterBody2D`.
- E. `--import` on r1_4: rc 0, logs `ERROR: res://cases/c19_future_format.tscn:1 - Parse Error: ...`; 24 ANSI lines.
  Import never reports GDScript parse errors -> import is not a check.
- F. `--doctool <existing dir>` rc 0 in 1.2-1.36 s, 1,076 XML files; dump with `--path` byte-identical to cached one.
- G. Scenes batch on r1_4 c00-c27: 0.18 s; c08/c09/c16/c19 load-failed, c13 instantiate-failed, c03 c04 c10 c11 c12
  c14 c17 c18 c23 with records, rest clean. `.tscn` parse errors carry the location only in the message.
- H. `--smoke 2`: catches c06 c16 c18 c22 c26 c32 d02 d03 (8/8 R-class); c20 c21 c29 clean; 3 scenes 0.37 s. C++-side
  errors carry `bt: ["res://cases/c18_emit_str.gd:4"]` -> exact script line.
- I. Hang in `_init`: `timeout -k 3 5` -> rc 124 at 5.01 s; `begin` without `end` attributes it; log flushed.
- J. `--check-only` and batch run `static var` initialisers / `_static_init()`; `--import` does not.
- K. Autoloads under `-s` are instantiated after the runner's `_init` returns (output after `done`); an autoload
  calling `quit(0)` turned a runner `quit(1)` into rc 0; `--check-only` runs no autoloads. Hence §3.2 steps 7-8;
  the old FAULT-P0-06 premise could not fire (replaced, R-25).

### 3.7 Timeouts and budgets
Kinds and defaults per C §2.8.2 (`runner` 60 s, `smoke` 30 s, `import` 180 s, `doctool` 120 s). Budgets (warm =
imported, version cached, 4 cores): `h check` on clean_min <= 5 s warm, <= 25 s fresh (incl. import); 60 broken
scripts <= 10 s warm; `h api <q>` <= 0.5 s with the index present; `h api --rebuild` <= 20 s; `h sync` <= 3 s;
`h doctor` <= 5 s. A hang costs timeout + <= 5 s (C §2.8.3).

### 3.8 godot.py display `xvfb` handling (R-14; from A6 §3.5 [Run K3], C §2.8.3)
`display="xvfb"` wraps argv in `xvfb-run -a` (never with `--headless`); extra Godot args (`--fixed-fps`,
`--resolution`, `--write-movie`) go through `args`. SIGTERM at T stops the whole group cleanly. (1) After the T+3 s
SIGKILL path, remove each `/tmp/.X<n>-lock` created after the invocation started whose PID (file content) is dead, plus
`/tmp/.X11-unix/X<n>`. (2) If the log matches `Unable to create DisplayServer|Xvfb failed to start|xvfb-run: error`,
retry once (`retried: true`, both logs kept); still failing -> `Invocation.display_failed = True`, which the verb maps
to rc 4 `[shot.no-display]` (A6 rule id). No A1 AC: verified by A6 AC-06.19 after B6 (N19, §8.2-7).

## 4. Acceptance criteria (contract layer unless noted; every `h` result also passes `assert_contract`)
- AC-01.1 `h check` on a fresh copy of `clean_min`: rc 0, `PASS check`, `^import: ran \(no \.godot/\)`, `files: 1 .gd,
  1 .tscn`, wall <= 25 s; second run: `import: fresh`, wall <= 5 s.
- AC-01.2 Each r1_5 P-class snippet (§6 `gd_cases`, 24 files) written into clean_min: rc 1 and a finding
  `^res://scripts/<case>\.gd:<line>: \[godot\.parse-error\] error:` with the §6 line. One test per case (param).
- AC-01.3 All 24 at once (plus c20): rc 1, 24 distinct error paths in `findings.jsonl`, no finding for c20, wall
  <= 10 s warm, stdout <= 40 lines with a truncation line.
- AC-01.4 Each r1_4 detectable case (c03 c04 c08 c09 c10 c11 c12 c13 c14 c16 c17 c18 c19 c23) placed in
  `scene_cases/cases/`: rc 1 (c04: rc 5 WARN, `invalid UID` warning); a finding located at that `.tscn`; c08 c09 c16
  c19 carry `:<line>` and `[check.load-failed]`; c13 `[check.instantiate-failed]`; c10/c11/c12
  `[godot.parent-vanished]`; c18 `[godot.load-failed]` or `[godot.error]` naming `res://scripts/ghost.gd`.
- AC-01.5 The r1_4 silent cases c00 c01 c02 c05 c06 c07 c15 c20 c21 c22 c24 c25 c26 c27 give rc 0 from `h check
  --no-lint` (documents the load-check limit; A3 lint covers them).
- AC-01.6 A parse-broken script attached to a scene (P0-03 setup) yields both `res://scripts/broken.gd:4:
  [godot.parse-error]` and no `[check.load-failed]` for the scene (the scene loads scriptless).
- AC-01.7 `--smoke`: null call in `_ready` -> `res://scripts/null_ready.gd:4: [godot.script-error]`; without
  `--smoke` the same copy gives rc 0 and `smoke off`.
- AC-01.8 `--smoke` on c18/c32 snippets (as scenes) -> findings at `res://scripts/c18_emit_str.gd:4` and
  `res://scripts/c32_get_tree_input.gd:3` (backtrace location).
- AC-01.9 Hang + resume (FAULT-A1-14 setup, `runner = 5`): rc 1, `^res://scripts/a_hang\.gd: \[harness\.hang\]`
  AND `^res://scripts/z_broken\.gd:3: \[godot\.parse-error\]`; wall <= 20 s; no surviving Godot process.
- AC-01.10 Autoload with a runtime error in `_ready` (no `--smoke`): rc 1, finding at `res://scripts/bad_auto.gd:3`.
  Autoload calling `quit(0)` while a script is broken: rc 1 plus `[harness.rc] warning`.
- AC-01.11 No duplicates: on c08, `findings.jsonl` holds exactly one `error` per (path, line, message); the scan never
  repeats a runner finding.
- AC-01.12 Stale class cache (CLEAN-A1-02 setup): `^import: ran \(stale class cache`, rc 0.
- AC-01.13 PATH and `--changed`: `h check scripts/hello.gd` checks 1 .gd + `scenes/main.tscn` (dependent; `files: 1
  .gd, 1 .tscn`); with `--no-deps` only the script; `--changed` in a temp git repo after editing one file lists only
  it and its dependents; outside a git repo -> rc 2; `h check ../x.gd` -> rc 2 `path outside project`.
- AC-01.14 `addons/` excluded by default (a broken `addons/x/bad.gd` -> rc 0); `--include-addons` -> rc 1.
- AC-01.15 `run.json` of a check has invocations of kinds `import` (if ran), `runner` (scripts), `runner`/`smoke`
  (scenes) with `--path <abs copy>` and the runner's absolute path after `-s`; `artifacts/scripts.txt` lists the files.
- AC-01.16 (R-28) `h check` on clean_min: the `phases:` line matches `lint (\d+\.\d+s|skipped \(.+\))` (valid before
  and after B3); with `--no-lint` it contains `lint skipped (--no-lint)`. The run_lint integration itself is covered by
  A3 AC-03.23 and FAULT-A3-22.
- AC-01.17 `h import` on clean_min: rc 0, `import: ran (requested)`; `--force` removes `.godot/` first (run.json
  shows import ran and `.godot/global_script_class_cache.cfg` exists after); on c19 in scene_cases: rc 1 with
  `res://cases/c19_future_format.tscn:1:`.
- AC-01.18 `h sync` with `HARNESS_REPO` pointing at a temp harness tree containing `addons/harness/{harness.gd,
  runners/load_check.gd}`: copies `harness.gd` but not `runners/`; adds `Harness="*res://addons/harness/harness.gd"`
  under `[autoload]`; `SKIP autoload Rng: not shipped`; second run 0 changed and `project.godot` byte-identical;
  `--check` after editing a synced file -> rc 1 `[harness.sync-stale]`; conflicting existing autoload -> rc 1
  `[harness.sync-conflict]` and `project.godot` unchanged; `--no-gdunit` skips gdUnit4; empty `HARNESS_CACHE` without
  `--no-gdunit` -> rc 4. Insertion (R-16): a project.godot with `[autoload]` holding only `Other="*res://o.gd"` followed
  by `[display]` gets `Harness=...` on the line after `Other=` (still before `[display]`); a project.godot already
  listing all shipped autoloads plus `SceneManager` stays byte-identical. gdUnit4 policy (R-33): a project with its
  own `addons/gdUnit4/plugin.cfg` at another version and no `.sync.json` -> rc 4 `harness pins 6.2.2`, addon files
  unchanged; the same with `.sync.json.gdunit4_commit` non-null -> overwritten, rc 0; installed copy has no `test/`
  dir and no `*.uid` files.
- AC-01.19 `h api Node2D.position`: rc 0, `sig: var position: Vector2`; `h api CharacterBody2D.position`: rc 0,
  `defined-in: Node2D`; `h api Input.is_action_just_pressed` sig contains `exact_match: bool = false`; `h api preload`
  -> `kind: function` from `@GDScript`; `h api @export_range` -> `kind: annotation`; `h api KEY_A` -> constant.
- AC-01.20 `h api KinematicBody2D`: rc 1, line 1 contains `not in Godot 4.7`, `suggest: CharacterBody2D`,
  `[api.renamed]`. `h api Node2D.positon`: rc 1, hint contains `Node2D.position`. `h api Control.rect_position`: hint
  names `position`. `h api Frobnicator`: rc 1 `[api.not-found]` and no `suggest:`.
- AC-01.21 (R-26) `h api --exists Node2D.position` rc 0, exactly 2 lines (verdict, `log:`); `--exists Node2D.nope`
  rc 1, exactly 3 lines: `^FAIL api`, `^-: \[api\.not-found\] error: Node2D\.nope does not exist in Godot 4\.7`,
  `^log:`; `--exists KinematicBody2D` rc 1, 3 lines with `[api.renamed]`; wall <= 0.5 s each.
- AC-01.22 `h api --search move_and` lists `CharacterBody2D.move_and_slide`; <= 40 lines with `more:` when > limit.
- AC-01.23 `h api --rebuild` with an empty temp `HARNESS_CACHE`: rc 0, creates `api/4.7.stable.official.5b4e0cb0f/
  {extension_api.json,@GDScript.xml,index.json}`, wall <= 20 s, leaves no scratch dir in `HARNESS_TMP`; the
  invocations in run.json have kind `doctool` and no `--path`. [contract, slow]
- AC-01.24 `HARNESS_GODOT=/nonexistent/godot h api --rebuild` -> rc 4; with a built index `h api Node2D` still works
  without Godot (no invocation in run.json).
- AC-01.25 `h doctor`: C §2.3 lines plus `api` check; with `--project <synced copy>` adds `sync`/`import` lines; a
  never-imported copy -> `WARN import: stale (no .godot/)`, rc 5.
- AC-01.26 [unit] `logscan.scan` strips ANSI (`\x1b[1mERROR: x\x1b[0m` -> `godot.error`) and takes the location from
  `ERROR: res://a.tscn:7 - Parse Error: y` -> (`res://a.tscn`, 7); AC-00.16 unchanged.
- AC-01.27 [contract] (R-39) `load_check.gd`, run via `run_godot(args, project, timeout)` on a 3-item list in a
  clean_min copy, prints begin/end pairs in order, one `done`, and rc == done.rc; `--mode bogus` -> rc 2. This is the
  only A1 test that calls Godot directly (runner protocol only).
- AC-01.28 [selftest] `h selftest --area A1`: rc 0, all FAULT-A1 caught, all CLEAN-A1 pass, wall <= 300 s.
- AC-01.29 [e2e, slow] fresh clone: `tools/bootstrap.sh` with an empty `HARNESS_CACHE` leaves `@GDScript.xml` and
  `index.json` in the cache and prints no `WARN: api`.
- AC-01.30 Every A1 verb with `--help` prints <= 40 lines, rc 0 (also C AC-00.3).
- AC-01.31 (R-25) FAULT-P0-06 setup with `h check --smoke`: rc 1, `^res://scenes/quit_early\.tscn: \[harness\.runner-incomplete\]`,
  and a scene sorted after it, `scenes/zz_null.tscn` with `scripts/null_ready.gd` (null call line 4), is resumed in a
  new invocation and still yields `null_ready\.gd:4: \[godot\.script-error\]`; wall <= 40 s.

## 5. Seeded faults (`selftest/faults/FAULT-A1-NN/fault.toml`, C §2.10; must unless marked nice)
Fixtures: `clean_min` (P0), `scene_cases` (§6). "write X" = `[[apply]] op="write"` from `files/`. Verb `check`
with `args = []` unless noted. All regexes are MULTILINE searches over stdout; max_seconds 60 unless noted.
| ID | Fixture: planted | Expect rc / verdict / regex |
|---|---|---|
| FAULT-A1-01 | clean_min: write `scripts/c02_onready.gd` | 1 FAIL `^res://scripts/c02_onready\.gd:2: \[godot\.parse-error\]` |
| FAULT-A1-02 | clean_min: write `scripts/c01_kinematic.gd` | 1 FAIL `c01_kinematic\.gd:1: \[godot\.parse-error\].*KinematicBody2D` |
| FAULT-A1-03 | clean_min: write `scripts/c11_variant_infer.gd` | 1 FAIL `c11_variant_infer\.gd:4: \[godot\.parse-error\]` |
| FAULT-A1-04 | clean_min: write `scripts/c28_tabspace.gd` | 1 FAIL `c28_tabspace\.gd:4: \[godot\.parse-error\]` |
| FAULT-A1-05 | clean_min: write `scripts/c27_hallucinated.gd` | 1 FAIL `c27_hallucinated\.gd:3: \[godot\.parse-error\]` |
| FAULT-A1-06 | clean_min: write `scripts/bad_parse.gd` (parse error line 3) + `scripts/uses_bad.gd` (`const B = preload("res://scripts/bad_parse.gd")` line 2) | 1 FAIL `bad_parse\.gd:3: \[godot\.parse-error\]` and `uses_bad\.gd:2: \[godot\.parse-error\]` |
| FAULT-A1-07 | scene_cases: write `cases/c10_bad_parent.tscn` | 1 FAIL `^res://cases/c10_bad_parent\.tscn: \[godot\.parent-vanished\]` |
| FAULT-A1-08 | scene_cases: write `cases/c03_missing_ext_path.tscn` | 1 FAIL `^res://cases/c03_missing_ext_path\.tscn(:\d+)?: \[godot\.` and `missing\.png` |
| FAULT-A1-09 | scene_cases: write `cases/c16_syntax_error.tscn` | 1 FAIL `^res://cases/c16_syntax_error\.tscn:\d+: \[check\.load-failed\]` |
| FAULT-A1-10 | scene_cases: write `cases/c13_two_roots.tscn` | 1 FAIL `c13_two_roots\.tscn: \[check\.instantiate-failed\]` |
| FAULT-A1-11 | scene_cases: write `cases/c18_missing_script_path.tscn` | 1 FAIL `ghost\.gd` and `\[godot\.(load-failed\|error)\]` |
| FAULT-A1-12 | scene_cases: write `cases/c23_instance_missing.tscn` | 1 FAIL `gone\.tscn` |
| FAULT-A1-13 | scene_cases: write `scripts/null_ready.gd` (null call line 4 in `_ready`) + `scenes/null_ready.tscn`; args `["--smoke"]` | 1 FAIL `^res://scripts/null_ready\.gd:4: \[godot\.script-error\]` |
| FAULT-A1-14 | clean_min: write `scripts/a_hang.gd` (`extends RefCounted` / `static var v: int = _f()` / `static func _f() -> int:` / `while true: pass`), `scripts/z_broken.gd` (parse error line 3), `harness.toml` `[timeouts]\nrunner = 5\n`; max_seconds 40 | 1 FAIL `^res://scripts/a_hang\.gd: \[harness\.hang\]` and `^res://scripts/z_broken\.gd:3:` |
| FAULT-A1-15 | scene_cases: write `scripts/c18_emit_str.gd` + `scenes/c18.tscn` attaching it; args `["--smoke"]` | 1 FAIL `^res://scripts/c18_emit_str\.gd:4: \[godot\.error\]` |
| FAULT-A1-16 | scene_cases: write `scripts/bad_auto.gd` (`extends Node`, `_ready` null call line 3), write `project.godot` = fixture text + `[autoload]\nBadAuto="*res://scripts/bad_auto.gd"\n` | 1 FAIL `^res://scripts/bad_auto\.gd:3: \[godot\.script-error\]` |
| FAULT-A1-17 (nice) | clean_min: autoload `scripts/quit0.gd` whose `_init` calls `Engine.get_main_loop().quit(0)` + `scripts/bad_parse.gd` | 1 FAIL `\[harness\.rc\] warning` and `bad_parse\.gd:3:` |
| FAULT-A1-18 | none: verb `api`, `no_project = true`, args `["KinematicBody2D"]`; max_seconds 30 | 1 FAIL `not in Godot 4\.7` and `CharacterBody2D` |
| FAULT-A1-19 | none: verb `api`, `no_project = true`, args `["--exists","Vector2.length_squared_fast"]` | 1 FAIL `^FAIL api` |
| FAULT-A1-20 | scene_cases: write `cases/c19_future_format.tscn`; verb `import` | 1 FAIL `^res://cases/c19_future_format\.tscn:1: \[godot\.error\]` |
| CLEAN-A1-01 | clean_min: write c20 c21 c29 snippets as scripts + one scene each; args `["--smoke", "--no-lint"]` (R-27: lint warns on c21) | 0 PASS, not_regex `\[godot\.` |
| CLEAN-A1-02 | clean_min: write `.godot/global_script_class_cache.cfg` = `list=[]\n`, then `scripts/late.gd` (`class_name Late extends Node`) and `scripts/uses_late.gd` (`var l: Late`) | 0 PASS `^import: ran \(stale class cache` |
| CLEAN-A1-03 | scene_cases: write the r1_4 silent cases c00 c21 c24 c25 c27 into `cases/`; args `["--no-lint"]` | 0 PASS |
| CLEAN-A1-04 | none: verb `api`, `no_project = true`, args `["Node2D.position"]` | 0 PASS `^sig: var position: Vector2$` |

## 6. Fixtures needed (test-writer T1)
- `tests/fixtures/projects/scene_cases/`: `project.godot` (C §2.11), `scripts/hero.gd` (`class_name Hero`, `extends
  Node2D`, `signal hit(amount)`, `@export var speed: float = 100.0`, `@export var target: Node`, `func _on_hit(a):
  print("hit ", a)`), `scripts/other.gd` (`extends Node`), `cases/c00_valid.tscn` (copy), `FIXTURE.md` (PASS).
  The r1_4 case files come from `.claude/research/scripts/r1_4_scene_format/cases/` (repo); copy them verbatim into
  each fault's `files/`.
- r1_5 snippets: the case sources live only in an ephemeral scratchpad, so they are given here (escapes `\n`, `\t`,
  `·` = one space). Put them under `tests/fixtures/gd_cases/<name>.gd` (not a project; faults and AC-01.2/3 copy
  them into `scripts/`). Expected line in brackets; `-` = not a parse error (R = smoke catches it, S = silent).
```
c01_kinematic   extends KinematicBody2D\nfunc _ready():\n\tpass                                   [1]
c02_onready     extends Node\nonready var a = 1\nfunc _ready():\n\tpass                          [2]
c03_export      extends Node\nexport var a = 1\nfunc _ready():\n\tpass                           [2]
c04_yield       extends Node\nfunc _ready():\n\tyield(get_tree().create_timer(1.0), "timeout")  [3]
c05_connect3    extends Node\nfunc _ready():\n\tconnect("tree_exited", self, "_x")\nfunc _x():\n\tpass [3]
c06_instance    extends Node\nfunc _ready():\n\tvar s = PackedScene.new()\n\tvar n = s.instance()   [- R:4]
c07_tool        tool\nextends Node                                                              [1]
c08_setget      extends Node\nvar a = 1 setget set_a\nfunc set_a(v):\n\ta = v                     [2]
c09_rect        extends Control\nfunc _ready():\n\trect_position = Vector2(1,1)                   [3]
c10_randrange   extends Node\nfunc _ready():\n\tprint(rand_range(0,1))                          [3]
c11_variant_infer extends Node\nfunc _ready():\n\tvar d := {}\n\tvar x := d.get("a")\n\tprint(x)  [4]
c12_poolarr     extends Node\nvar a: PoolStringArray                                            [2]
c13_os_ticks    extends Node\nfunc _ready():\n\tprint(OS.get_ticks_msec())                      [3]
c14_file        extends Node\nfunc _ready():\n\tvar f = File.new()                              [3]
c15_move_and_slide extends CharacterBody2D\nfunc _physics_process(d):\n\tvelocity = move_and_slide(velocity, Vector2.UP) [3]
c16_changescene extends Node\nfunc _ready():\n\tget_tree().change_scene("res://a.tscn")         [- R:3]
c17_stepify     extends Node\nfunc _ready():\n\tprint(stepify(1.234,0.1))                       [3]
c18_emit_str    extends Node\nsignal foo\nfunc _ready():\n\temit_signal("fooo")                 [- R:4]
c19_get_node_in_var extends Node\nvar a = $Missing\nfunc _ready():\n\tprint(a)                  [2]
c20_ok_baseline extends Node\n@export var a: int = 1\n@onready var b = 2\nfunc _ready():\n\tprint(a, b) [- clean]
c21_lambda_capture extends Node\nfunc _ready():\n\tvar n := 0\n\tvar f := func(): n += 1\n\tf.call()\n\tprint(n) [- S]
c22_tween_new   extends Node\nfunc _ready():\n\tvar t = Tween.new()\n\tt.interpolate_property(self,"x",0,1,1) [- R:4]
c23_shadow_dot_super extends Node\nfunc _ready():\n\t._ready()                                  [3]
c24_typedarray  extends Node\nvar a: Array[int] = [1, "x"]                                      [2]
c25_deg2rad     extends Node\nfunc _ready():\n\tprint(deg2rad(90))                              [3]
c26_empty       extends Node\nfunc _ready():\n\tvar a = []\n\tprint(a.empty())                  [- R:4]
c27_hallucinated extends Node\nfunc _ready():\n\tself.get_player_position()\n\tvar v = Vector2(1,1)\n\tv.length_squared_fast() [3]
c28_tabspace    extends Node\nfunc _ready():\n\tvar a = 1\n········print(a)                       [4]
c29_int_div     extends Node\nfunc _ready():\n\tvar a: int = 5 / 2\n\tvar b: float = 5 / 2\n\tprint(a,b) [- S]
c30_preload_dyn extends Node\nfunc _ready():\n\tvar p = "res://x.tscn"\n\tvar s = preload(p)     [4]
c31_assign_ret_void extends Node\nfunc f() -> void:\n\tpass\nfunc _ready():\n\tvar a = f()       [5]
c32_get_tree_input extends Node\nfunc _ready():\n\tInput.is_action_pressed("nope")             [- R:3]
d01_untyped_connect extends Node\nfunc _ready():\n\tvar b = Button.new()\n\tb.connect("pressed", self, "_x")\nfunc _x():\n\tpass [4]
d02_untyped_move extends Node\nfunc _ready():\n\tvar b = Node2D.new()\n\tb.rect_position = Vector2.ZERO [- R:4]
d03_signal_connect_str extends Node\nfunc _ready():\n\tvar b = Button.new()\n\tb.connect("pressed", _x)\n\tb.connect("nosuch", _x)\nfunc _x():\n\tpass [- R:5]
```
  Each file ends with a newline. c28 line 4 is 8 spaces then `print(a)` (tabs elsewhere).
- `tests/fixtures/harness_trees/sync_src/` (AC-01.18, used as `HARNESS_REPO`): `addons/harness/harness.gd`, `addons/
  harness/runners/load_check.gd`, a `tools/harness/pins.toml` copy. `tests/fixtures/harness_trees/gdunit_cache/`
  (AC-01.18 policy cases, used as `HARNESS_CACHE`): `gdunit4/addons/gdUnit4/{plugin.cfg (version="6.2.2"),
  src/a.gd, src/a.gd.uid, test/t.gd}`. Smoke scenes: hand-written, root `Node` + script.

## 7. Build order (B1; each step ends green on the named ACs; run `.venv/bin/pytest tests/unit tests/contract/p0
tests/contract/a1 -q` after each)
0. Contract step 0 per C §7 steps 1-2 (out, project, config, cli Δ incl. `import_` mapping, doctor Δ, logscan with
   §3.4) -> AC-00.1-10, 16-18, 26; AC-01.26, 30.
1. `godot.py` (run, spawn, ensure_imported, xvfb §3.8) + `proc.py` + `load_check.gd` (scripts mode) +
   `verbs/check.py` scripts phase only + `sync.py` with `verbs/sync.py` (N16: B4 starts right after this gate) ->
   AC-00.11-14, 19, 20, 27; AC-01.1-3, 15, 18, 27. Gate "core ready" (REVIEW §4).
2. Scenes phase, record mapping, scan merge, rc merge, public `checkrun.load_check` (unblocks B2) -> AC-00.15;
   AC-01.4-6, 10, 11.
3. Resume after hang/crash/runner-incomplete, `--smoke` -> AC-01.7-9, 31; AC-00.21 P0-06.
4. File-set options, dependents, `--changed`, `run_lint` call, auto-import refinements -> AC-01.12-14, 16.
5. `verbs/import_.py` -> AC-01.17.
6. `apiindex.py`, `verbs/api.py`, renames copy, bootstrap step 8 Δ -> AC-01.19-24, 29.
7. Doctor extras -> AC-01.25. `faults.py`, `verbs/selftest.py` -> AC-00.21-23, AC-01.28. Then `tools/dev/ci.sh --quick`.

## 8. Out of scope, open questions, assumptions

### 8.1 Out of scope / deferred
`h check --lsp` (A3 owns the daemon; `--lsp` is not an A1 flag); per-file `--check-only` mode (batch is strictly
faster and equal on all spiked cases; the `check_only` kind stays in the contract for A8 hooks if they want it);
C# scripts (D1); checking `.res` binary resources; editor-plugin (`@tool`) execution paths; Windows/macOS.

### 8.2 Open questions [U]
1. Autoloads run during `h check` after the runner's `_init` (§3.6 K): their errors are real findings, but an
   autoload that blocks forever makes every check a hang. Accepted and documented for v0.
2. Closed (R-25): FAULT-P0-06 replaced by the `get_tree().quit(0)`-in-`_ready` scene under `--smoke` (must);
   attribution in §3.2 step 5, AC-01.31.
3. (b) of §3.3 (unimported assets) is not spiked; a texture added without import may load via the fallback loader.
4. Whether enabling the gdUnit4 editor plugin in `project.godot` is needed for CLI runs: A4 decides; `h sync` only
   copies files.
5. > 2,000 files may approach the 60 s runner timeout in one batch; v0 targets D5 "small".
6. `--smoke`: a scene that calls `change_scene_to_file` or `quit()` ends the batch early; the item gets
   runner-incomplete (or `harness.rc`) and the rest is resumed (§3.2 step 5). Acceptable for v0.
7. (N19) §3.8 xvfb cleanup/retry/`display_failed` (R-14) has no A1 AC: it needs A6 runners and is verified by
   A6 AC-06.19 after B6. B1 ships it untested in step 1.

### 8.3 Deviations from 00_contract (all accepted in REVIEW; now in the contract where noted)
- D-a `api.*` prefix (C §2.7) **R-03**. D-b `verbs/import_.py`, cli strips one trailing `_` (C §2.1) **R-04**.
- D-c `godot.run(project=None, cwd=<dir>)` for `doctool`/`version`, no `--path` (the dump with `--path` aborts rc 134
  [Run F]) **R-05**. D-d logscan ANSI strip + `res://F:L` fallback (C §2.8.4) **R-06**; §3.3 refinements stay A1-local
  on top of R-24. D-e message-level scan/runner dedup in `check` (§3.2 step 7) **R-07**.
- D-f `h api --exists` FAIL = 3 lines, PASS = 2 (§2.4) **R-26**. D-g `sync.py` library, autoload insertion, gdUnit4
  overwrite policy (§2.3, §3.1) **R-33/R-16**; extra return value `installed (pin changed)` (same policy, [U] not in
  R-33's list). D-h public `checkrun.load_check` (§3.1) **R-30**. D-i xvfb handling in `godot.py` (§3.8) **R-14**.
- Also applied: lint via `run_lint` **R-29**; CLEAN-A1-01 `--no-lint` **R-27**; AC-01.16 **R-28**; AC-01.27
  [contract] via `run_godot` **R-39**; runner-incomplete attribution + AC-01.31 **R-25**.

### 8.4 Assumptions about other areas
- A3 (R-29): package `harness.lint` with `run_lint(run, project, paths | None, mode)` adds findings, <= 2 s per 100
  files; A3 owns `h lint`/`h lsp`; there is no `h check --lsp`. A2 (R-30): calls `checkrun.load_check` and adds the
  returned findings itself; a new `load_check.gd` mode needs an A1 re-plan. A4 (R-33): `sync.install_gdunit4` +
  `godot.ensure_imported`; A5/A6/A7 `sync.ensure_synced`. A8 hooks: `h check <file> --no-lint --no-deps`, `h api
  --exists`. A5 ships `harness,rng,command_bus.gd`, A7 `trace.gd` under `addons/harness/` (R-16). T1 owns
  `tests/helpers/gd.py` and fixture `gd_host` (R-39); A1 has no `[gd]` suites. Plan D1-D5, B1-B8, C §8 hold.
