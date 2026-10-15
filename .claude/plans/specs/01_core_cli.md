# 01 Core CLI: shim, godot.py, import, sync, api, check, doctor, selftest (A1)

Status: spec v1, 2026-10-15, Opus planner P1. Conforms to `00_contract.md` (cited as "C §x"); deviations are listed in
§8.3. Tags: [Run] verified in §3.6 spikes (Godot 4.7.stable.official.5b4e0cb0f), [U] unverified.

## 1. Purpose and failure modes covered

A1 is the first builder. It ships the contract core (C §3.1 step 0) plus the verbs an agent uses after every edit:
`h check` (did my scripts/scenes break?), `h api` (does this API exist in 4.7?), `h import`, `h sync`, `h doctor`,
`h selftest`. Failure modes (godot_harness_plan F-ids):
- **F1/F2 Godot-3 idioms and hallucinated API**: `h check` catches 24/35 r1_5 snippets at parse time [Run]; `h api`
  answers "not in 4.7, renamed to X" and "did you mean" before code is written; `--exists` for hooks (A8).
- **F3 silent scene breakage** (r1_4): load+instantiate with Logger capture; every "detectable" r1_4 case FAILs.
- **F4 exit codes lie** (R1.1 #4, R1.5 #2, S2): log/Logger records are the signal; rc only adds failures; hang and
  crash become findings; an autoload can overwrite the exit code [Run, §3.6 K].
- **F5 runtime-only errors** (R1.5 rec. 4): `--smoke` runs each scene for N physics frames; catches 8/8 r1_5 R-class
  snippets [Run].
- **F7 class cache / fresh clone** (R1.1 #3): auto-import rule C §2.8.7 plus two A1 refinements (§3.3).
- **F11 noisy output**: C §2.3 grammar, <= 40 lines; batching keeps runs to one Godot process per phase.
- D-ids: none changed. Uses D1 (GDScript only) and D5 (small projects: <= ~500 files per check).

## 2. Interfaces

All verbs: C §2.1-2.5 (shim, common flags `--project/--strict/-h`, stdout grammar, rc 0-5, run dir). Only the
verb-specific parts are listed here. Rule ids owned by A1: `godot.*`, `harness.*`, `check.*`, `selftest.*`, and the
new prefix `api.*` (§8.3).

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
- `--no-lint`: skip the A3 phase. Lint is otherwise called through `harness.lint` if importable (§3.4).
- Stat lines, in order: `project:`, `import: ran (<why>)|fresh`, `files: <a> .gd, <b> .tscn, <c> .tres` (omit zero
  kinds, but at least `0 .gd`), `phases: scripts <s>s, scenes <s>s, lint <s>s|skipped (<why>), smoke on|off`.
- Verdict reason: `<e> errors, <w> warnings in <n> files (<t>s)` or `0 findings in <n> files (<t>s)` (C §2.3).
- Rules emitted: scan/Logger rules of C §2.8.4 (`godot.*`); `check.load-failed` (ResourceLoader returned null),
  `check.instantiate-failed` (PackedScene.instantiate() returned null), `harness.hang`/`harness.crash` located at the
  file being checked when the runner died, `harness.rc` warning when the process rc differs from the runner's
  `done` rc (an autoload called `quit()`, §3.6 K), plus whatever `harness.lint` adds.
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

### 2.3 `h sync [--no-gdunit] [--check]`
- Mirrors `$HARNESS_REPO/addons/harness/` (excluding `runners/`, `*.uid` and `.import` files) into
  `<project>/addons/harness/` (extra files there are deleted), then writes `addons/harness/.sync.json`
  `{"schema":"harness.sync/1","source_hash":"<sha256 over sorted (relpath, bytes)>","gdunit4_commit":"<sha|null>"}`.
- gdUnit4 (unless `--no-gdunit`): copies `<HARNESS_CACHE>/gdunit4/addons/gdUnit4/` to `<project>/addons/gdUnit4/` when
  missing or when `.sync.json.gdunit4_commit` differs from pins.toml. Cache missing: rc 4 `gdUnit4 not in cache (run
  tools/bootstrap.sh)`. Plugin enabling is not done (A4 decides, §8.2).
- Autoloads: for each name in harness.toml `[harness] autoloads` (default `["Harness","Rng","CommandBus"]`), file
  `addons/harness/<snake_case(name)>.gd`. If the file exists, ensure `[autoload]` in `project.godot` has
  `<Name>="*res://addons/harness/<snake>.gd"` (section appended at the end when missing; other lines untouched). If
  the file is not shipped: check line `SKIP autoload <Name>: not shipped`. A different existing value for the same
  name: finding `res://project.godot: [harness.sync-conflict] error: autoload <Name> already set to <v>`, no write.
- Check lines: `OK addons/harness: <n> files (<k> changed)`, `OK gdunit4: <tag> <sha12>`, one per autoload.
- `--check`: writes nothing; FAIL with `[harness.sync-stale] error` per out-of-date part. Idempotent: a second sync
  changes 0 files and leaves `project.godot` byte-identical.

### 2.4 `h api` (no project needed)
```
h api <Name>                 # Class | Class.member | global function | annotation | constant
h api <Name> --all           # class: list members (<= 30 lines, then `more:` stat)
h api --search <substr> [--limit N]   # case-insensitive substring over keys; default limit 20, max 30
h api --exists <Name>        # rc 0 PASS / rc 1 FAIL; output: verdict + log line only (hook mode)
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
`h check`; tests in `tests/gd/a1/` may run it directly with these args.

### 2.8 Config keys
No new table. A1 reads `[harness] godot, godot_version, autoloads`, `[timeouts]`, `[scan] ignore` (C §2.6).
API index: `$HARNESS_CACHE/api/<godot_version_string>/{extension_api.json,@GDScript.xml,index.json}`; index.json =
`{"schema":"harness.api-index/1","godot_version":"...","entries":{"<key>":{"k":kind,"sig":...,"d":...,"in":...}}}`.

## 3. Design

### 3.1 Files to create (builder B1; exact paths)
Step 0 (C §3.1, all B1): `tools/harness/harness/{out,project,config,logscan,godot,proc,faults}.py`,
`verbs/selftest.py`; Δ `cli.py`, `verbs/doctor.py`, `tools/harness/h` (C1-C3, C8, C9).
A1 proper: `tools/harness/harness/verbs/{check,import_,sync,api}.py` — note `import` is a Python keyword, so the
module is `verbs/import_.py` and cli maps a trailing `_` away (`import_` -> `h import`; Δ to C §2.1 discovery);
`tools/harness/harness/checkrun.py` (phase driver, record->finding mapping, resume), `apiindex.py` (build, load,
lookup, Levenshtein), `data/renames_3to4.json` (copy of `.claude/research/scripts/r1_5_lint/renames.json`),
`addons/harness/runners/load_check.gd`; Δ `tools/bootstrap.sh` step 8 (§3.5). Not created (vs plan §7):
`runners/smoke.gd` (merged into `load_check --smoke`), `runners/api_dump.gd` (index built in Python from dumps).
Ports: `.claude/research/scripts/r1_4_scene_format/load_check.gd` (Logger capture) extended per §2.7; the
`script_backtraces` and begin/end additions are from §3.6 spikes G/H.

### 3.2 `h check` algorithm (`checkrun.py`)
1. Resolve project, config, binary (C §2.8.1). Build the file set (§2.1), sorted by res:// path.
2. `godot.ensure_imported` (§3.3). If the import invocation itself failed by rc/hang/crash: emit its findings,
   `SKIP scripts/scenes: import failed` check lines, stop. Import scan findings (broken resources) count normally.
3. **Scripts phase**: one invocation, kind `runner`, `load_check.gd --mode scripts --list <run dir>/artifacts/
   scripts.txt`. Batch, not per-file: 52 files in 0.29 s vs 2.8 s (4-parallel per-file) and 10.3 s (sequential),
   identical finding locations on the 35 r1_5 snippets [Run §3.6 A-C].
4. **Scenes phase**: one invocation, kind `runner` (`smoke` with `--smoke`), `--mode scenes` over `.tscn/.tres`.
   Runs after scripts so parse errors are reported even if a scene hangs in `_init`.
5. **Resume**: if an invocation times out or crashes, the item with `begin` but no `end` gets `[harness.hang]` /
   `[harness.crash]` at its path; items after it are re-run in a new invocation (at most 3 resumes per phase; then
   `SKIP <phase>: <k> files not checked after 3 hangs`). Expected wall for one hang = timeout + ~1 s.
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
9. **Lint phase** (unless `--no-lint`): `harness.lint.check_files(run, project, files)` if the module imports;
   ImportError -> `lint skipped (harness.lint not installed)`; other exceptions -> rc 3 per C §2.9.
10. `run.finish(reason)`. All file lists and per-phase timings go to `run.json` `extra.check`.

### 3.3 Auto-import refinements (godot.py, C §2.8.7)
Import also runs when (a) a script path listed in `global_script_class_cache.cfg` no longer exists, or (b) a file
with an importable extension (`png jpg jpeg webp svg bmp tga wav ogg mp3 glb gltf fbx obj ttf otf woff woff2`)
lacks `<file>.import` or is newer than it [U: (b) not spiked; cheap stat-only rule]. `<why>` strings:
`no .godot/`, `no class cache`, `stale class cache (<file>)`, `missing script (<file>)`, `unimported asset (<file>)`.

### 3.4 Logscan details owned by B1 (C §2.8.4, additive)
- Strip ANSI SGR sequences (`\x1b\[[0-9;]*m`) before matching: `--import` logs contain colour progress lines [Run E].
- Location fallback for rules with "next (res://F:L)": if no paren location is found in the window, use the first
  `res://<path>:<line>` token of the matched line (`ERROR: res://c19.tscn:1 - Parse Error: ...` [Run E]). Paths in
  absolute-file backtraces (`(/abs/runner.gd:13)`) are never used. AC-00.16 must stay green.

### 3.5 `h api` index and the bootstrap --doctool gap
- Gap root cause [Run F]: `godot --doctool <dir>` needs `<dir>` to exist (`ERROR: Argument supplied to --doctool must
  be a valid directory path.`, rc 1, 0.2 s); bootstrap passed a not-yet-created `$S/doc`, and its guard only tests
  `extension_api.json`, so it never retries. Also `--dump-extension-api-with-docs` with `--path <proj>` writes a
  correct file and then aborts rc 134 (`Parameter "singleton" is null`); without `--path` it exits 0 [Run F].
- `--rebuild`: in a fresh dir `$HARNESS_TMP/api-<run id>/` run (kind `doctool`, project None, cwd = that dir, no
  `--path`, §8.3) `--headless --dump-extension-api-with-docs` and `--headless --doctool <dir>/doc` (after mkdir);
  copy `extension_api.json` and `doc/modules/gdscript/doc_classes/@GDScript.xml` to the cache dir; build
  `index.json` (load 0.21 s + build 0.06 s, 29,551 keys, 4.65 MB; reload 0.03 s [Run D]); write atomically
  (tmp + rename); delete the scratch dir. Rebuild when index.json is missing or its `godot_version` differs.
- Keys: `Class`, `Class.member` (methods with typed args, defaults and return; properties; signals; enum values;
  constants), builtin types and their methods/members, `@GlobalScope.<utility fn|enum value>`,
  `@GDScript.<fn|@annotation>`, singletons. Rename map: `class_renames`, `builtin_types_renames`,
  `gdscript_function_renames`, `gdscript_properties_renames`, `gdscript_signals_renames`, `enum_renames` (values are
  stored quoted, e.g. `"\"CharacterBody2D\""`: strip the quotes).
- Δ bootstrap step 8 becomes: `"$ROOT/tools/harness/h" api --rebuild >"$LOG" 2>&1 || echo "WARN: api index failed"`,
  guarded by `[ -f "$CACHE/api/<version string>/index.json" ]`; until `h api` exists, the minimal fix is
  `mkdir -p "$S/doc"` and a guard on `@GDScript.xml` too.

### 3.6 Spikes (scratchpad `a1/`, all [Run], Godot 4.7.stable.official.5b4e0cb0f, 4 cores)
- A. 52-script project (46 typed class_name scripts, 1 user of `S01`, 3 broken, 1 static-init, 1 preload of a
  broken script). Per-file `--check-only -s res://F` sequential: 10.33 s; `xargs -P 4`: 2.80 s. Batch runner (load
  with Logger): 0.18 s (CACHE_MODE_REUSE) / 0.28 s (IGNORE). Same 4 failing files. -> batch, IGNORE.
- B. Messages identical between modes, e.g. `SCRIPT ERROR: Parse Error: Cannot assign a value of type "String" as
  "int".` + `at: GDScript::reload (res://scripts/bad_type.gd:3)`; Logger R = `{"type":2,"file":
  "res://scripts/bad_type.gd","line":3,...}`. `uses_bad.gd` (preload of broken): `Could not resolve script
  "res://scripts/bad_parse.gd"` at `uses_bad.gd:2`. `$Child` in a member initializer: parse error `(Warning treated
  as error.)` in both modes. An unused local gives no output in either mode (warnings are not printed).
- C. r1_5 cases (35 files): batch and per-file give the same 24 `GDScript::reload` locations (c01:1 c02:2 c03:2
  c04:3 c05:3 c07:1 c08:2 c09:3 c10:3 c11:4 c12:2 c13:3 c14:3 c15:3 c17:3 c19:2 c23:3 c24:2 c25:3 c27:3 c28:4 c30:4
  c31:5 d01:4); batch 0.29 s.
- D. API index prototype: see §3.5 numbers; `Input.is_action_just_pressed` -> `func is_action_just_pressed(action:
  StringName, exact_match: bool = false) -> bool`; `KinematicBody2D` absent from the dump, present in
  `class_renames` -> `CharacterBody2D`.
- E. `--import` on the r1_4 project: rc 0, logs `ERROR: res://cases/c19_future_format.tscn:1 - Parse Error: Saved
  with newer format version.`; 24 lines carry ANSI colour codes (progress). Import never reports GDScript parse
  errors (52-script project: no `SCRIPT ERROR` at import) -> import is not a check.
- F. doctool / dump behaviour as in §3.5: `--doctool <existing dir>` rc 0 in 1.2-1.36 s, 1,076 XML files, 7.1 MB,
  `@GDScript.xml` under `modules/gdscript/doc_classes/`. The dump with `--path` is byte-identical to the cached one.
- G. Scenes batch on r1_4 c00-c27 (+3): 0.18 s; statuses match r1_4 §2 (c08/c09/c16/c19 load-failed, c13
  instantiate-failed; c03 c04 c10 c11 c12 c14 c17 c18 c23 with records; c01 c02 c05 c06 c07 c15 c20-c22 c24-c27
  clean). Parse errors of `.tscn` carry the location only in the message (`res://cases/c16_syntax_error.tscn:N`).
- H. `--smoke 2` (await `physics_frame` inside the runner's `_init`): catches c06 c16 c18 c22 c26 c32 d02 d03 (8/8
  R-class); c20 c21 c29 stay clean; 3 scenes in 0.37 s. C++-side errors (`Can't emit non-existing signal "fooo"`,
  file `core/object/object.cpp`) carry `bt: ["res://cases/c18_emit_str.gd:4"]` -> exact script line.
- I. Hang: scene whose script loops in `_init`; `timeout -k 3 5` -> rc 124 at 5.01 s; log has `begin` for
  `res://x/hang.tscn` with no `end` -> attribution works; the log is flushed up to the kill.
- J. `--check-only` and batch both run `static var` initialisers and `_static_init()` (printed `STATIC_INIT_RAN`);
  `--import` does not (a script whose static initialiser loops: import rc 0 in 5.1 s, batch rc 124 at 5.0 s).
- K. Autoloads under `-s`: instantiated AFTER the runner's `_init` returns (output after `done`); their `_ready` runs;
  an autoload calling `Engine.get_main_loop().quit(0)` turned a runner `quit(1)` into process rc 0. `--check-only`
  does not run autoloads. Hence §3.2 steps 7-8, and FAULT-P0-06's premise (§8.2).

### 3.7 Timeouts and budgets
Kinds and defaults per C §2.8.2 (`runner` 60 s, `smoke` 30 s, `import` 180 s, `doctool` 120 s). Budgets (warm =
imported, version cached, 4 cores): `h check` on clean_min <= 5 s warm, <= 25 s fresh (incl. import); 60 broken
scripts <= 10 s warm; `h api <q>` <= 0.5 s with the index present; `h api --rebuild` <= 20 s; `h sync` <= 3 s;
`h doctor` <= 5 s. A hang costs timeout + <= 5 s (C §2.8.3).

## 4. Acceptance criteria (contract layer unless noted; every `h` result also passes `assert_contract`)
- AC-01.1 `h check` on a fresh copy of `clean_min`: rc 0, `PASS check`, `^import: ran \(no \.godot/\)`, `files: 1 .gd,
  1 .tscn`, wall <= 25 s; second run: `import: fresh`, wall <= 5 s.
- AC-01.2 Each r1_5 P-class snippet (§6 `gd_cases`, 24 files) written into clean_min: rc 1 and a finding
  `^res://scripts/<case>\.gd:<line>: \[godot\.parse-error\] error:` with the §3.6 C line. One test per case (param).
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
- AC-01.16 Lint hook: with a stub `harness/lint.py` absent -> `lint skipped`; [unit] `checkrun` calls
  `harness.lint.check_files` when importable (monkeypatched module) and its findings appear in the verdict.
- AC-01.17 `h import` on clean_min: rc 0, `import: ran (requested)`; `--force` removes `.godot/` first (run.json
  shows import ran and `.godot/global_script_class_cache.cfg` exists after); on c19 in scene_cases: rc 1 with
  `res://cases/c19_future_format.tscn:1:`.
- AC-01.18 `h sync` with `HARNESS_REPO` pointing at a temp harness tree containing `addons/harness/{harness.gd,
  runners/load_check.gd}`: copies `harness.gd` but not `runners/`; adds `Harness="*res://addons/harness/harness.gd"`
  under `[autoload]`; `SKIP autoload Rng: not shipped`; second run 0 changed and `project.godot` byte-identical;
  `--check` after editing a synced file -> rc 1 `[harness.sync-stale]`; conflicting existing autoload -> rc 1
  `[harness.sync-conflict]` and `project.godot` unchanged; `--no-gdunit` skips gdUnit4; empty `HARNESS_CACHE` without
  `--no-gdunit` -> rc 4.
- AC-01.19 `h api Node2D.position`: rc 0, `sig: var position: Vector2`; `h api CharacterBody2D.position`: rc 0,
  `defined-in: Node2D`; `h api Input.is_action_just_pressed` sig contains `exact_match: bool = false`; `h api preload`
  -> `kind: function` from `@GDScript`; `h api @export_range` -> `kind: annotation`; `h api KEY_A` -> constant.
- AC-01.20 `h api KinematicBody2D`: rc 1, line 1 contains `not in Godot 4.7`, `suggest: CharacterBody2D`,
  `[api.renamed]`. `h api Node2D.positon`: rc 1, hint contains `Node2D.position`. `h api Control.rect_position`: hint
  names `position`. `h api Frobnicator`: rc 1 `[api.not-found]` and no `suggest:`.
- AC-01.21 `h api --exists Node2D.position` rc 0 (2 lines); `--exists Node2D.nope` rc 1; wall <= 0.5 s each.
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
- AC-01.27 [gd] `load_check.gd` run directly on a 3-item list prints begin/end pairs in order, one `done`, and
  rc == done.rc; `--mode bogus` -> rc 2.
- AC-01.28 [selftest] `h selftest --area A1`: rc 0, all FAULT-A1 caught, all CLEAN-A1 pass, wall <= 300 s.
- AC-01.29 [e2e, slow] fresh clone: `tools/bootstrap.sh` with an empty `HARNESS_CACHE` leaves `@GDScript.xml` and
  `index.json` in the cache and prints no `WARN: api`.
- AC-01.30 Every A1 verb with `--help` prints <= 40 lines, rc 0 (also C AC-00.3).

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
| CLEAN-A1-01 | clean_min: write c20 c21 c29 snippets as scripts + one scene each; args `["--smoke"]` | 0 PASS, not_regex `\[godot\.` |
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
  harness/runners/load_check.gd`, a `tools/harness/pins.toml` copy. Smoke scenes: hand-written, root `Node` + script.

## 7. Build order (B1; each step ends green on the named ACs; run `.venv/bin/pytest tests/unit tests/contract/p0
tests/contract/a1 -q` after each)
0. Contract step 0 per C §7 steps 1-2 (out, project, config, cli Δ incl. `import_` mapping, doctor Δ, logscan with
   §3.4) -> AC-00.1-10, 16-18, 26; AC-01.26, 30.
1. `godot.py` + `proc.py` + `load_check.gd` (scripts mode) + `verbs/check.py` scripts phase only -> AC-00.11-14,
   19, 20; AC-01.1-3, 15.
2. Scenes phase, record mapping, scan merge, rc merge -> AC-00.15; AC-01.4-6, 10, 11.
3. Resume after hang/crash, `--smoke` -> AC-01.7-9.
4. File-set options, dependents, `--changed`, lint hook, auto-import refinements -> AC-01.12-14, 16.
5. `verbs/import_.py` -> AC-01.17. `verbs/sync.py` -> AC-01.18.
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
2. FAULT-P0-06 (autoload `_init` calling `quit(0)` -> `harness.runner-incomplete`) cannot fire as written: the runner
   has already printed `done` [Run K]. Recommend the reviewer replaces it with FAULT-A1-17's rc-mismatch rule or
   drops it (it is `nice`).
3. (b) of §3.3 (unimported assets) is not spiked; a texture added without import may load via the fallback loader.
4. Whether enabling the gdUnit4 editor plugin in `project.godot` is needed for CLI runs: A4 decides; `h sync` only
   copies files.
5. > 2,000 files may approach the 60 s runner timeout in one batch; v0 targets D5 "small".
6. `--smoke`: a scene that calls `change_scene_to_file` or `quit()` ends the batch early (runner-incomplete/rc
   findings at that scene). Acceptable for v0.

### 8.3 Deviations from 00_contract (for the spec reviewer)
- D-a `api.*` rule prefix (A1) added to C §2.7.
- D-b Verb module `verbs/import_.py` for `h import` (keyword clash): cli strips one trailing `_` (C §2.1).
- D-c `godot.run(..., project=None)` for kind `doctool` (and `version`): no `--path`, cwd = a given scratch dir,
  because `--dump-extension-api-with-docs --path P` aborts rc 134 after writing [Run F] (C §2.8.2 says `--path`
  always).
- D-d logscan additions §3.4 (ANSI strip, message-embedded `res://F:L` fallback) and auto-import triggers §3.3.
- D-e Scan/runner dedup for `check` by message text (§3.2 step 7), stricter than C §2.8.6's (path, line, message).

### 8.4 Assumptions about other areas
- A3 exposes `harness/lint.py` with `check_files(run, project: Path, files: list[Path]) -> None` adding findings via
  `run.finding(...)`, <= 2 s for 100 files; A3 owns `h lint`. Until it exists `h check` reports `lint skipped`.
- A2 re-uses `load_check.gd --mode scenes` for its post-write load-check (same arg protocol, §2.7) rather than its
  own runner; A2 may add a mode but must not change existing modes.
- A4 uses `h sync` to install gdUnit4 and relies on the auto-import rule; A8 hooks call `h check <file> --no-lint`
  (one batch invocation, ~0.3 s Godot time) and `h api --exists`.
- A5 ships `addons/harness/{harness,rng,command_bus}.gd`; `h sync` enables them by name (snake_case mapping).
- Plan defaults D1-D5, B1-B8 and C §8 hold.
