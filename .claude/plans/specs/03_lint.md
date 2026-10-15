# 03 Lint, Godot-3 hook, LSP (A3, planner P3)

Status: spec v2, 2026-10-15, Opus planner P3 re-run. Conforms to `00_contract.md` (cited as "C §x") and
`REVIEW.md` (R-ids; B15, N06, N17, N20 applied). Deviations in §8.3 are all accepted. Tags: [Run] verified in §3.7 spikes, [U] unverified. Inputs: r1_5 (all), r1_8 checklist, r1_1
LSP notes, r2_spikes S2/S5, `scripts/r1_5_lint/*`, `scripts/r1_1_cli/lsp_probe.py`.

## 1. Purpose and failure modes covered
`h lint` is the cheap, Godot-free first line: it runs in < 300 ms on one file, so the A8 PostToolUse hook can run it on
every edit, and `h check` (A1) folds it into its verdict. It catches what the engine load-check cannot (r1_5 §3):
- **F1 Godot 3 idioms** (r1_5 patterns 1-12, 18-20, 29): 1,213 regex rules from `renames_map_3_to_4.cpp`@4.7 plus 48
  hand rules. Silent cases matter most: Godot 3 `.tscn`/`.tres` load in 4.7 with no message (r1_5 #4), `.instance()`,
  `.empty()`, `change_scene()`, `Tween.new()` on untyped receivers only fail at runtime.
- **Runtime-only name errors** (r1_5 #21, #24): `emit_signal("typo")`, `connect("nosuch", ...)`, InputMap action
  names that do not exist. Project-aware checks resolve them statically.
- **Determinism (R1.8, plan §3.3)**: global RNG outside `rng.gd`, wall clock and Node use in sim dirs, idle-mode
  Tween/Timer/AnimationPlayer and `Engine.time_scale` in replayed code. Feeds A5 (replays) and A9 (sim/view).
- **P15** raw `KEY_*` outside remap code; **F4/F5** partly (signal names); **F11** <= 40 lines. **Fast parse
  diagnostics** via an opt-in LSP daemon (S5), used by the hook only when one is already running. **Oracle**:
  `--godot3-oracle` asks the engine's `--validate-conversion-3to4` (r1_5 #7); nothing is ever converted.
Not covered (engine/test only, r1_5 §3): typed-array mismatch, hallucinated methods, integer division, `_process`
misuse, `parent=` errors, unknown `.tscn` properties (A1 load-check, A2 digest).

## 2. Interfaces
### 2.1 `h lint`
```
h lint [PATH...] [--project DIR] [--strict] [--hook] [--changed] [--godot3-oracle]
```
- `PATH...`: files or dirs, as `res://...` or fs paths (cwd-relative or absolute). Dirs recurse. Default: the whole
  project (all `.gd`, `.tscn`, `.tres` and `project.godot`, minus hidden dirs, `.godot/`, `.harness/` and `exclude`).
  A path outside the project or a missing path: rc 2 `ERROR lint usage: <why>: <path>`. Other extensions are ignored.
- `--hook`: fast mode for hooks. Only the given PATHs (no PATH = rc 2); excluded paths are skipped (counted in
  `skipped:`); never starts Godot; adds LSP diagnostics only if this project's daemon is already running and
  `[lint] lsp_in_hook` is true (§2.2). Budget: <= 300 ms wall for one 300-line `.gd` (LSP part capped at 1.0 s extra).
- `--changed`: lint files reported by `git status --porcelain` (modified, added, untracked) under the project.
  Not a git work tree: rc 2. Combines with `--hook`.
- `--godot3-oracle`: also run the engine converter in validate mode on the given `.gd` files (§3.5), adding
  `lint.g3-oracle` findings. Needs Godot (rc 4 per C §2.8.1 if missing). Requires PATHs.
- Default and `--hook` modes never start a Godot process: `run.json.invocations == []`, and they work with
  `HARNESS_GODOT=/nonexistent` (no rc 4).
- Stat lines, in order: `project:`, `files: <n> .gd, <n> .tscn, <n> .tres[, project.godot]`, `rules: <n>`,
  `skipped: <n> (excluded)` if > 0, `suppressed: <n>` if > 0, `lsp: used|not running|off|timeout` in `--hook` only.
- Finding lines follow C §2.3. Every finding of a regex rule or `lint.*` rule (except `lint.lsp`) has a hint. The
  stdout hint is single-line (newlines -> ` / `) and cut to 100 chars with `...`; `findings.jsonl` has it in full.
- rc per C §2.4: 1 if any error finding (or warning with `--strict`), 5 warnings only, 0 clean; 2 usage/config;
  3 internal (also: rule data missing or invalid); 4 only with `--godot3-oracle`.

Literal example (fixture `godot3_scripts`, cut where marked `...`):
```
$ tools/harness/h lint --project /tmp/h/godot3_scripts
FAIL lint 37 errors, 5 warnings in 41 files (0.19s)
project: /tmp/h/godot3_scripts
files: 36 .gd, 4 .tscn, 0 .tres, project.godot
rules: 1229
res://cases/c01_kinematic.gd:1: [class-KinematicBody2D] error: class KinematicBody2D renamed/removed (hint: CharacterBody2D)
res://cases/c04_yield.gd:3: [syn-yield] error: yield() removed (hint: await signal_or_coroutine  e.g. await get_tree().create_timer(1.0).timeout)
res://cases/c18_emit_str.gd:4: [lint.signal-name] error: signal 'fooo' is not declared on this script or its bases (hint: did you mean 'foo'? prefer foo.emit())
res://cases/c32_get_tree_input.gd:3: [lint.input-action] error: InputMap action 'nope' does not exist (hint: add it under [input] in project.godot; known: jump, ui_accept, ...)
...
... 8 more findings (3 errors, 5 warnings) in findings.jsonl
log: /tmp/h/godot3_scripts/.harness/out/20261015T150102Z-lint-2b7e/
```
(`rules:` and the elapsed time are illustrative; the counts follow from §6.1.)

### 2.2 `h lsp`
```
h lsp start  [--project DIR]
h lsp status [--project DIR]
h lsp stop   [--project DIR | --all]
h lsp diag   FILE... [--project DIR] [--oneshot]
```
- One daemon per project realpath: `godot --headless --editor --path <abs> --lsp-port <free port>`. State file
  `$HARNESS_CACHE/lsp/<sha256(realpath)[:12]>.json` (schema §2.5), daemon log next to it (`.log`).
- `start`: runs `godot.ensure_imported` first (C §2.8.7, prints `import:`), picks a free 127.0.0.1 port, starts the
  daemon with `godot.spawn(run, "lsp_start", project, args, log_path)` (C §2.9, R-09; own session and process group,
  stdin `/dev/null`, log next to the state file; A3 never calls `subprocess` on Godot), waits until the port accepts
  and `initialize` answers (timeout kind `lsp_start` 30 s).
  Already running and answering: rc 0, same pid, reason `already running`. Stats: `pid:`, `port:`, `state: running`.
  Failed to come up: rc 1 `[lint.lsp-daemon] error` with the last daemon log line; the process is killed.
- `status`: always rc 0. `state: running|stopped|stale` (+ `pid:`, `port:`, `uptime_s:` when running). `stale` =
  state file whose pid is dead or port does not answer within 0.5 s; the file is removed.
- `stop`: SIGTERM to the daemon's process group, SIGKILL after 3 s, remove the state file; rc 0 also when not
  running. `--all` stops every daemon in `$HARNESS_CACHE/lsp/` and needs no project.
- `diag FILE...`: needs a running daemon, else rc 4 `ERROR lsp daemon not running (h lsp start)`. `--oneshot` =
  start, diag, stop in one call (scripts and tests; there is no `h check --lsp`, R-29). Per file: connect,
  `initialize`/`initialized` once, `textDocument/didOpen` with the text read from disk, wait up to 5 s for `publishDiagnostics` of that uri,
  `didClose`; close the socket. Findings `res://f.gd:<line+1>: [lint.lsp] <sev>: <message>`, severity 1 -> error,
  2 -> warning, 3/4 -> info. No diagnostics within 5 s: `[lint.lsp-timeout] warning` for that file.
- `--strict`, rc and stdout per C §2.3/§2.4. The daemon itself is long-lived and is not an `invocations` entry of
  `diag`; `start` records one invocation of kind `lsp_start` (via `godot.spawn`) with `timed_out`/`rc` = readiness result.

### 2.3 Python API (for A1 `h check` and A8 hooks; module `harness.lint`)
```python
def run_lint(run: out.Run, project: Path, paths: list[Path] | None = None, mode: str = "full") -> None
    # mode "full" | "hook". Adds findings/stats to run; never starts Godot. Raises nothing for lint findings.
def lsp_diag(run: out.Run, project: Path, files: list[Path], start: bool = False) -> bool
    # adds lint.lsp findings; start=True behaves like --oneshot; returns False if no daemon and start=False.
```
This API is canonical (R-29). A1's `h check` step 9 calls `run_lint(run, project, None, "full")` when no PATH and no
`--changed` were given (lints project.godot too); otherwise it passes the selected file list including dependents, and
`run_lint` still applies `exclude`. `h check` has no `--lsp` flag (R-29); `lsp_diag` serves `h lsp diag` and the `--hook` LSP path. A8's hook
runs `h lint --hook <file>` and may skip its `--check-only` call when stdout has `lsp: used` and no `lint.lsp-timeout`.

### 2.4 Rule data: `tools/harness/rules/lint_rules.json` (public data; tests may read it)
```json
{"type":"object","required":["schema","godot","rules"],"properties":{"schema":{"const":"harness.lint-rules/1"},
 "godot":{"type":"string"},"rules":{"type":"array","items":{"type":"object","required":["id","regex","applies_to",
 "severity","message","hint","family","anchor","scope","risk"],"properties":{"id":{"type":"string","pattern":
 "^[a-z0-9][a-zA-Z0-9._-]*$"},"regex":{"type":"string"},"applies_to":{"type":"array","items":{"enum":[".gd",".tscn",
 ".tres","project.godot"]}},"severity":{"enum":["error","warning","info"]},"message":{"type":"string","minLength":1},
 "hint":{"type":"string","minLength":1},"family":{"type":"string"},"anchor":{"type":["string","null"]},
 "scope":{"enum":["all","sim","det"]},"risk":{"enum":["low","medium","high","n/a"]},"demo_corpus_hits":{"type":"integer"}}}}}}
```
- The 1,213 r1_5 rules keep their ids (r1_5 ids may contain upper case, e.g. `enum-BUTTON_LEFT`; C §2.7 lets them
  stay undotted). `severity`: risk low -> error, medium/high -> warning (plan §7). `hint` = `godot4_replacement`.
  `family` = id prefix before the first `-` (`syn`, `tscn`, `fn`, `prop`, `sig`, `enum`, `class`, `tscnclass`,
  `color`, `theme`). `scope` = `all`. `anchor` = for generated families, the longest identifier in the old name (the
  id after the first `-`), which must occur literally in `regex`; `null` for `syn`/`tscn`. A rule with an anchor is
  only tried on files whose identifier set (`[A-Za-z_]\w*`) contains the anchor ([Run]: identical hits, 8x faster).
- A3's regex-based `lint.*` rules (§3.3) are in the same file with `risk: "n/a"` and their own `scope`.
- `tools/harness/rules/native_classes.json`: `{"schema":"harness.native-classes/1","godot":..,"classes":{"Button":
  {"inherits":"BaseButton","signals":["..."]},...}}` from the pinned `extension_api.json` (1,036 classes, 79 KB, loads
  in ~1 ms [Run]). `tools/harness/rules/builtin_actions.json`: `{"schema":"harness.builtin-actions/1","godot":..,
  "actions":[91 names]}` from `InputMap.get_actions()` in an empty 4.7 project [Run].

### 2.5 LSP state file (`$HARNESS_CACHE/lsp/<key>.json`)
`{"schema":"harness.lsp/1","pid":int,"pgid":int,"port":int,"project":"<realpath>","godot":"<binary realpath>",
"version":"<godot --version>","started_at":"<iso>","log":"<abs path>"}`; `pid` is the Godot process itself (§3.7).

### 2.6 `harness.toml` `[lint]` (CONFIG_TABLE = "lint"; C §2.6)
```toml
[lint]
severity = {}            # {"<rule id>" | "<family>-*" | "lint.*" = "error"|"warning"|"info"|"off"}
exclude = ["res://addons/**"]     # globs over res:// paths; ** = any depth
replay_dirs = []         # determinism scope "det" (warnings); [harness] sim_dirs is scope "sim" (errors)
rng_files = ["**/rng.gd"]          # exempt from lint.det-global-rng
remap_files = ["**/*remap*.gd", "**/*rebind*.gd", "**/*keybind*.gd"]   # exempt from lint.raw-keycode
lsp_in_hook = true
```
`replay_dirs` defaults to `[]` (R-08): user projects stay quiet about UI Tween/Timer/AnimationPlayer, while
`sim_dirs` still give errors. Projects opt in to strict mode with `[lint]\nreplay_dirs = ["res://"]`; A9's
`templates/project/harness.toml` and `sample/harness.toml` do so, as does fixture `lint_clean_demo` (§6.3).
A `severity` key that matches no rule, or a value outside the enum: rc 2 `[harness.config]` naming the key. A file
in `sim_dirs` is scope `sim`, else in `replay_dirs` scope `det`, else neither. Severity resolution: exact id >
family glob > `lint.*` > rule default.

### 2.7 Suppression (in `.gd` only)
`<code>  # lint-ignore: <id>[, <id>...]` suppresses those ids on that line; a comment-only line `# lint-ignore-next-line:
<id>[, ...]` suppresses them on the next line. No wildcard. An unknown id gives `[lint.bad-suppress] warning`.
Suppressed findings count in `suppressed:` and stay in findings.jsonl as `"severity":"info"`, message `suppressed: ...`.

## 3. Design
### 3.1 Files (builder B3 writes exactly these)
- `tools/harness/harness/verbs/lint.py` (CLI, `HELP`, `CONFIG_TABLE`/`CONFIG_KEYS`), `verbs/lsp.py`.
- `tools/harness/harness/lint/__init__.py` (`run_lint`, `lsp_diag`), `lint/rules.py` (load/validate JSON, lazy compile
  cache, severity resolution, globs), `lint/scan.py` (port of `research/scripts/r1_5_lint/scan.py`), `lint/project.py` (project.godot `[input]` + `config_version`, script index,
  signal resolution, receiver inference), `lint/checks.py` (code checks §3.4), `lint/suppress.py`,
  `lint/oracle.py` (§3.5), `lint/lsp_client.py` (JSON-RPC over TCP; port `research/scripts/r1_1_cli/lsp_probe.py`,
  with the S5 didOpen/timeout loop), `lint/lsp_daemon.py` (state file, spawn, readiness, stop).
- `tools/harness/rules/lint_rules.json`, `native_classes.json`, `builtin_actions.json` (committed, generated) and
  `tools/harness/rules/build_lint_data.py` (dev only, runs from `.venv`: reads
  `.claude/research/scripts/r1_5_lint/lint_rules_full.yaml`, adds §3.3 rules, anchors, severities; reads
  `$HARNESS_CACHE/api/4.7/extension_api.json`; dumps built-in actions with Godot via `timeout 30`; validates every
  regex compiles and every anchor occurs in its regex; byte-stable output, sorted keys).

### 3.2 Regex pass (port of scan.py, with fixes)
Per file: read as UTF-8 (`errors="replace"`), split lines, build the identifier set once. Rules filtered by extension
(`project.godot` is its own type), scope (rule `sim`: only scope-sim files; `det`: sim -> error, det -> warning,
else skip; `all`: every non-excluded file), anchor, and exemptions. Skip `.gd` lines whose first non-blank char
is `#` and `.tscn`/`.tres` lines starting with `;` (r1_5 behaviour; trailing comments are still scanned).
**Overlap dedup**: on one (file, line), if any generated-family rule (`fn prop sig enum class tscnclass color theme`)
hits, drop hits of the hand rules `syn-rand-seed syn-change-scene syn-find-node tscn-g3-types syn-rect-props-gd
tscn-rect-props` (the generated hint is the specific one). One finding per (file, line, rule).

### 3.3 `lint.*` rules (all new, dotted per C §2.7)
| id | how | scope / severity | hint (abridged) |
|---|---|---|---|
| `lint.input-action` | code, §3.4a | all / error | add under [input] in project.godot; did-you-mean |
| `lint.signal-name` | code, §3.4b | all / error | did you mean; prefer `<sig>.emit()` / `<sig>.connect(cb)` |
| `lint.indent-mixed` | code, §3.4c | all / error | re-indent with the file's style (tabs default) |
| `lint.det-global-rng` | regex `(?<![\w.])(?<!func )(randf\|randi\|randf_range\|randi_range\|randfn\|randomize\|seed)\s*\(` and `\.(shuffle\|pick_random)\s*\(\s*\)`; not in `rng_files` | det | use the seeded Rng autoload / a RandomNumberGenerator, never the global RNG |
| `lint.det-wallclock` | regex `\b(Time\.(get_ticks_msec\|get_ticks_usec\|get_unix_time_from_system\|get_datetime_\w+_from_system\|get_date_\w+_from_system\|get_time_\w+_from_system)\|Engine\.get_(process_frames\|frames_drawn))\s*\(` | det | count physics ticks (Engine.get_physics_frames or own counter) |
| `lint.det-idle-tween` | code: `create_tween(` with no `TWEEN_PROCESS_PHYSICS` on that line or the next 3 | det | `.set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)` |
| `lint.det-idle-timer` | code: `.gd` `Timer.new()` with no `TIMER_PROCESS_PHYSICS` in the next 5 lines; `create_timer(` whose 3rd arg is not `true`; `.tscn` `[node ... type="Timer"]` block without `process_callback = 0` | det | `process_callback = Timer.TIMER_PROCESS_PHYSICS` / `create_timer(t, false, true)` |
| `lint.det-idle-anim` | code: `.tscn` `type="AnimationPlayer"\|"AnimationTree"` block without `callback_mode_process = 0`; `.gd` `AnimationPlayer.new()`/`AnimationTree.new()` without `ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS` in 5 lines | det | `callback_mode_process = ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS` |
| `lint.det-time-scale` | regex `\bEngine\.(time_scale\s*=(?!=)\|set_time_scale\s*\()` | all / warning | replays and feel metrics assume 1.0; run more ticks per wall second instead |
| `lint.sim-node` | regex `\bNodePath\b\|\bget_node(_or_null)?\s*\(\|\bget_tree\s*\(\|(?<![\w"'])\$[A-Za-z_"]\|(?<![\w"'])%[A-Z]\w*\|\^"` plus code: `extends T` / `: T` / `Array[T]` where native T inherits Node | sim / error | sim state is node-free: store int ids, rebuild the view from events (A9) |
| `lint.raw-keycode` | regex `(?<![\w.])KEY_[A-Z0-9_]+\b\|\bKey\.[A-Z]\w*\|\.(physical_)?keycode\b\|\bInput\.is_(physical_)?key_pressed\s*\(`; not in `remap_files` | all / warning | use InputMap actions; raw keys only in remap code (P15) |
| `lint.g3-project` | regex `^config_version=[0-4]\s*$` on project.godot | all / error | Godot 3 project: `--convert-3to4` on a copy, then review |
| `lint.bad-suppress` | §2.7 | / warning | use a real rule id |
| `lint.g3-oracle` | §3.5 | / warning | official converter: `<new text>` |
| `lint.lsp`, `lint.lsp-timeout`, `lint.lsp-daemon` | §2.2 | LSP severity / warning / error | (no hint for `lint.lsp`) |
(`\|` = Markdown escape of `|`.) Enum values [Run, extension_api.json]: `TIMER_PROCESS_PHYSICS=0`, `IDLE=1`;
`ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS=0`, `IDLE=1`, `MANUAL=2`; `TWEEN_PROCESS_PHYSICS=0`. `.tscn` checks read
the node header with any attribute order (4.7 adds `unique_id=` [Run]); nodes without `type=` (instances,
inherited) are skipped [U: an instanced Timer scene stays unchecked].

### 3.4 Project-aware checks
a. **InputMap.** Known = keys of the `[input]` section of `project.godot` (lines `^([^\s=;\[]+)=` at column 0 while
   in that section) ∪ `builtin_actions.json` ∪ literal names passed to `InputMap.add_action("x")` anywhere in the
   project. Checked calls (first string literal, `"x"` or `&"x"`): `is_action_pressed`, `is_action_just_pressed`,
   `is_action_just_released`, `is_action_released`, `is_action`, `get_action_strength`, `get_action_raw_strength`,
   `action_press`, `action_release`; all literals of `get_axis(...)` and `get_vector(...)`. Not checked:
   `has_action`, non-literal args. Hint lists up to 3 known names by edit distance, else the first 5 project actions.
   [Run] 350 literal action uses in the 4.7 demos: 0 false positives; c32 flagged twice.
b. **Signals.** Calls `emit_signal`, `connect`, `disconnect`, `is_connected` with a string-literal first arg. Receiver:
   none or `self.` -> this script; an identifier declared in the same file as `var x: T`, `var x := T.new()`,
   `var x = T.new()` (incl. `@onready`/`@export` forms) -> class T; anything else is skipped. Declared signals of a
   script = its `signal` lines + those of its base chain: `extends "res://p.gd"`, `extends ClassName` (project
   `class_name` index), native class (`native_classes.json`, with inherited signals), no `extends` = RefCounted.
   An unresolvable base anywhere in the chain -> skip the file (no finding). [Run] demos: 0 false positives (only 2
   string emits exist there); c18 flagged.
c. **Mixed indentation.** For `.gd` statement-start lines only (bracket depth 0 counted outside string literals, not
   after a trailing `\`, not inside `"""`): the first indented one fixes the style; a later one whose indent starts
   with the other char, or mixes both, is flagged. [Run] 459 demo `.gd` files: 0 hits; c28 line 4 flagged.

### 3.5 `--godot3-oracle`
Copy each given `.gd` to `$HARNESS_TMP/oracle-<run-id>/<basename>` with a minimal `project.godot` (config_version 5),
run `godot.run(kind="oracle", args=["--validate-conversion-3to4"])` (timeout 60 s, expected rc {0}) in that dir, then
delete it. Parse the log: `^\s*Line\((\d+)\), (.+) -> (.+?)  -  LINE """ (.*) """$` and
`^\s*Line \(\d+\) - FULL LINES - """ (.*) """  =====>  """ (.*) """$`, attributed to the file named by the preceding
`Checking for conversion - i/n file - "<name>"` line. Line numbers of FULL LINES entries are wrong ([Run]: `Line (1)`
for line 3), so the line is always found by matching the quoted old text against the stripped source lines (first
match; none -> no line). Finding `lint.g3-oracle` warning, message `converter would rewrite: <old>`, hint
`official converter: <new>`. The real project is never touched (the converter writes `.godot/` into its cwd [Run]).

### 3.6 Budgets and timeouts
Hook mode one file <= 300 ms wall incl. shim ([Run] core 11-12 ms, `h --help` 45-51 ms). Full mode <= 3 s per 1,000
files ([Run] 992 demo files, 5.7 MB: 1.36 s). Oracle <= 5 s ([Run] 0.29 s). `lsp start` <= 15 s on a small imported
project ([Run] ready in 3.5 s). `lsp diag` 5 files on a warm daemon <= 1.5 s wall ([Run] 0.12-0.30 s per client).
Godot kinds `oracle` 60 s and `lsp_start` 30 s are in the C §2.8.2 table (R-09); both scaled by `HARNESS_TIMEOUT_SCALE`.

### 3.7 Spikes (scratchpad `a3/`, Godot 4.7.stable.official.5b4e0cb0f, Python 3.13; all [Run])
- YAML -> JSON: 1,213 rules, ids unique; risk low 1,161 / medium 13 / high 39; families fn 409, class 195, tscnclass
  195, color 146, enum 112, prop 94, syn 41, sig 14, tscn 7; 431 KB.
- One 260-line `.gd`, naive: compile 75-106 ms + scan 166-269 ms = 290-408 ms wall (over budget). Anchor prefilter:
  11-12 ms in-process, 34-39 ms wall. Prefilter vs full over 992 demo files (godot-demo-projects@b761b4c) + 36 r1_5
  cases: 98 = 98 hits. Demo files: 0 error-severity hits; warnings only (`syn-semicolon-end` 28,
  `syn-python-elif-colon-missing` 10, `syn-dot-super` 4, `syn-var-types-csharp` 4, ...).
- §6.1 expectations computed with the dedup rule (d01 `syn-connect-3arg`:4, d02 `prop-rect_position`:4).
  `InputMap.get_actions()` in an empty project: 91 built-ins. `extension_api.json` load 221 ms vs index 0.9 ms.
- `--validate-conversion-3to4` on 7 cases: rc 0, 0.29 s, sources unchanged, `.godot/` created; reported
  `rand_range -> randf_range` (Line(3)), `KinematicBody2D -> CharacterBody2D`, 3-arg connect -> `Callable(self,
  "_x")`, yield -> await, `.instance()` -> `.instantiate()`; did NOT report bare `onready` (c02).
- LSP daemon on an imported 3-file project: port ready 3.5 s after spawn; 3 sequential client connections each got
  correct diagnostics (c24 2 errors line 2; c02 `"onready" keyword was removed` line 2; c20 none) in 2-59 ms per
  file; sources unchanged. A `setsid` wrapper pid was not the Godot pid (daemon survived the kill).
- dodge_the_creeps (MIT, 8 text files): 0 regex hits; by grep, with `replay_dirs = ["res://"]` (the fixture's harness.toml, §6.3) gives 5 `lint.det-idle-timer`
  (hud.gd:16 `create_timer(1)`, hud.tscn:57, main.tscn:30/33/35) + 4 `lint.det-global-rng` (main.gd:30/39/43,
  mob.gd:5) warnings.

## 4. Acceptance criteria
Layers: `data` = pytest reading the public `tools/harness/rules/*.json` files, no harness import (accepted, R-01,
C §2.12); others per C §2.12. All
`h` results pass `assert_contract`. "copy" = B3 temp copy of the named fixture.
- AC-03.1 `lint_rules.json` validates against §2.4; its r1_5 id set equals the ids in
  `research/scripts/r1_5_lint/lint_rules_full.yaml`; every regex compiles; every anchor occurs in its regex; low ->
  error, medium/high -> warning; every hint is non-empty; all §3.3 regex rules present. [data]
- AC-03.2 `h lint` on copy of `godot3_scripts`: rc 1, and for every file in §6.1 the set of (path, line, rule,
  severity) findings equals the table exactly (files listed as "none" have no finding). [contract]
- AC-03.3 Dedup: `c10`:3 has `fn-rand_range`, not `syn-rand-seed`; `g3.tscn:5` `tscnclass-Spatial`, not `tscn-g3-types`.
- AC-03.4 `lint_base` copy: rc 0, PASS, zero findings, `run.json.invocations == []`. [contract]
- AC-03.5 `lint_clean_demo` copy (its shipped harness.toml sets `replay_dirs = ["res://"]`, §6.3): rc 5, WARN, 0 error
  findings, exactly the 9 warnings of §3.7 (path, line, rule); with harness.toml replaced by `[lint]\nreplay_dirs = []`:
  rc 0 PASS. [contract]
- AC-03.6 Hook speed: in a `lint_base` copy, a generated clean 300-line `scripts/long.gd`; median wall of 5
  `h lint --hook --project <copy> scripts/long.gd` (after 1 warm-up) <= 300 ms. [contract]
- AC-03.7 Full speed: 1,000 generated `.gd` files of ~100 clean lines in a copy: `h lint` <= 4 s wall. [contract, slow]
- AC-03.8 `HARNESS_GODOT=/nonexistent/godot h lint` on `godot3_scripts` copy: rc 1 (not 4); same for `--hook`. [contract]
- AC-03.9 Every finding line of a regex/`lint.*` rule (except `lint.lsp`) ends with `(hint: ...)`; stdout hints have
  no newline and are <= 100 chars; findings.jsonl hints are complete. [contract]
- AC-03.10 Comment-only `.gd` lines (`# yield(x, "y")`) and `;` lines in `.tscn` give no finding. [contract]
- AC-03.11 Suppression: same-line form suppresses only the named id; next-line form works; `suppressed: 1` stat;
  unknown id -> `[lint.bad-suppress] warning`. [contract]
- AC-03.12 Severity overrides: `{"syn-yield"="warning"}` -> rc 5 on a yield-only file; `"off"` -> rc 0;
  `{"fn-*"="off"}` removes `fn-rand_range`; `{"syn-yeld"="off"}` -> rc 2 `[harness.config]` naming `syn-yeld`;
  value `"fatal"` -> rc 2; `--strict` turns a warnings-only run into rc 1. [contract]
- AC-03.13 `exclude`: a yield file under `res://addons/x/` gives no finding by default (`skipped:` in `--hook`);
  with `exclude = []` it gives `[syn-yield]`. [contract]
- AC-03.14 Input actions (copy of `lint_base` + a written file): `"jumpp"` -> `[lint.input-action] error` with hint
  containing `jump`; `"ui_accept"`, `&"jump"`, `get_vector("move_left","move_right","jump","jump")`, an action added
  by `InputMap.add_action("dyn")` and a non-literal arg give nothing; `get_axis("move_left","nope")` flags `nope`;
  `InputMap.has_action("nope")` gives nothing. [contract]
- AC-03.15 Signals: `emit_signal("hitt")` in a script declaring `signal hit` -> error with hint `hit`; `extends Button`
  + `emit_signal("pressed")` -> none; signal declared in `extends "res://scripts/base.gd"` and in a `class_name`
  base -> none; `extends SomeMissingClass` -> none; `var b := Button.new()` + `b.connect("nosuch", f)` -> error;
  `obj.connect("x", f)` with untyped `obj` -> none. [contract]
- AC-03.16 Determinism (files written into a `lint_base` copy whose `harness.toml` is first written as
  `[lint]\nreplay_dirs = ["res://"]`, R-08): `randf()` in `res://sim/a.gd` -> error
  `lint.det-global-rng`; same in `res://scripts/a.gd` -> warning; in `res://scripts/rng.gd` -> none; `rng.randf()` ->
  none; `arr.shuffle()` in sim -> error; `Time.get_ticks_msec()` sim -> error, scripts -> warning;
  `create_tween()` -> warning, `create_tween().set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)` -> none;
  `get_tree().create_timer(1.0)` -> warning, `create_timer(1.0, false, true)` -> none; `.tscn` Timer without
  `process_callback = 0` -> warning at its `[node` line, with it -> none; AnimationPlayer likewise; 
  `Engine.time_scale = 2.0` -> warning `lint.det-time-scale`. Without that harness.toml (default `[]`), the
  `res://scripts/` cases give no `lint.det-*` finding and the `res://sim/` errors stay. [contract]
- AC-03.17 `lint.sim-node`: in `res://sim/s.gd`, `var p: NodePath`, `get_node("x")`, `get_tree()`, `extends Node2D`,
  `var n: Sprite2D` each -> error; identical code in `res://scripts/` -> no `lint.sim-node`. [contract]
- AC-03.18 `KEY_SPACE` in `res://scripts/player2.gd` -> warning `lint.raw-keycode`; in
  `res://scripts/input_remap.gd` -> none. [contract]
- AC-03.19 c28 line 4 -> `lint.indent-mixed`; a tab file with a space-aligned continuation in `( )` -> none. [contract]
- AC-03.20 `project.godot` with `config_version=4` -> `res://project.godot:<line>: [lint.g3-project] error`. [contract]
- AC-03.21 Paths: `res://cases/c04_yield.gd`, a cwd-relative fs path and a dir arg all work and lint only those
  files; a path outside the project -> rc 2; missing -> rc 2; `--hook` without PATH -> rc 2; `--changed` outside
  git -> rc 2; in a `git init`ed copy after editing one file, `--changed` lints only that file. [contract]
- AC-03.22 `--godot3-oracle scripts/o.gd` (o.gd = `extends Node\nfunc _ready():\n\tprint(rand_range(0,1))\n\tconnect("tree_exited", self, "_x")`):
  findings `res://scripts/o.gd:3: [lint.g3-oracle]` with hint containing `randf_range` and `:4:` with `Callable(`;
  one invocation of kind `oracle`; project files byte-identical, no new `.godot/` in the copy; <= 10 s. [contract, godot]
- AC-03.23 `h check` on a `lint_base` copy plus a yield file shows `[syn-yield]` (A1 integration, §2.3). [contract, godot]
- AC-03.24 LSP lifecycle: `lsp start` rc 0 with `pid:`/`port:`; second `start` same pid, reason `already running`;
  `status` `state: running`; `stop` rc 0 and no process with the copy path in its cmdline survives 5 s; `status`
  then `stopped`; a state file with a dead pid -> `stale` and the file is gone. [contract, godot]
- AC-03.25 `lsp diag`: `scripts/bad.gd` with a parse error on line 4 -> rc 1 `^res://scripts/bad\.gd:4: \[lint\.lsp\] error:`;
  a clean file -> rc 0; no daemon -> rc 4 `lsp daemon not running`; `--oneshot` gives the same finding and leaves
  no daemon; 5 files on a warm daemon <= 1.5 s wall. [contract, godot]
- AC-03.26 Hook + LSP: daemon running -> `lsp: used` and the `lint.lsp` finding for bad.gd appears in
  `h lint --hook`; no daemon -> `lsp: not running`, invocations `[]`; `lsp_in_hook = false` -> `lsp: off`. [contract, godot]
- AC-03.27 Two copies get two daemons on different ports; `stop --all` stops both. [contract, godot]
- AC-03.28 `h selftest --area A3`: rc 0, all must faults CAUGHT, 3 clean PASS, wall <= 180 s. [contract, slow]

## 5. Seeded faults (`selftest/faults/FAULT-A3-NN/fault.toml`; fixture `lint_base`, verb `lint`, files written to
`scripts/f.gd` unless noted; all `must` unless noted; `max_seconds` 15 unless noted)
| ID | Planted (`write` op) | Expect rc / verdict / regex |
|---|---|---|
| FAULT-A3-01 | `extends KinematicBody2D` (c01) | 1 FAIL `^res://scripts/f\.gd:1: \[class-KinematicBody2D\] error` |
| FAULT-A3-02 | c02 bare `onready var` | 1 FAIL `f\.gd:2: \[syn-onready\]` |
| FAULT-A3-03 | c04 `yield(...)` | 1 FAIL `f\.gd:3: \[syn-yield\]` |
| FAULT-A3-04 | c05 3-arg `connect` | 1 FAIL `f\.gd:3: \[syn-connect-3arg\]` |
| FAULT-A3-05 | c15 `move_and_slide(velocity, Vector2.UP)` | 1 FAIL `\[syn-move-and-slide-args\]` |
| FAULT-A3-06 | c06 `.instance()` | 1 FAIL `\[syn-instance\]` |
| FAULT-A3-07 | c10 `rand_range` | 1 FAIL `\[fn-rand_range\]`, not_regex `\[syn-rand-seed\]` |
| FAULT-A3-08 | c13 `OS.get_ticks_msec()` | 1 FAIL `\[syn-os-ticks\]` |
| FAULT-A3-09 | c14 `File.new()` | 1 FAIL `\[syn-file-dir-class\]` |
| FAULT-A3-10 | `scenes/ui.tscn`: format=3 scene, Control root with line `rect_position = Vector2(4, 4)` | 1 FAIL `ui\.tscn:\d+: \[tscn-rect-props\]` |
| FAULT-A3-11 | `scenes/old.tscn` = r1_5 `g3.tscn` (§6.1) | 1 FAIL `old\.tscn:1: \[tscn-g3-header\]` |
| FAULT-A3-12 | `sim/roll.gd`: `extends RefCounted\nfunc roll() -> int:\n\treturn randi() % 6` | 1 FAIL `roll\.gd:3: \[lint\.det-global-rng\] error` |
| FAULT-A3-13 | first op `write` `harness.toml` = `[lint]\nreplay_dirs = ["res://"]\n` (R-08); then `scripts/fx.gd`: `extends Node2D\nfunc _ready() -> void:\n\tvar t := create_tween()\n\tt.tween_property(self, "position:x", 10.0, 0.5)` | 5 WARN `fx\.gd:3: \[lint\.det-idle-tween\] warning` |
| FAULT-A3-14 | `Input.is_action_pressed("jumpp")` in a clean player script | 1 FAIL `\[lint\.input-action\] error: .*jumpp.*hint: .*jump` |
| FAULT-A3-15 | `signal hit` + `emit_signal("hitt")` | 1 FAIL `\[lint\.signal-name\] error` |
| FAULT-A3-16 | `sim/clock.gd`: `extends RefCounted\nfunc now() -> int:\n\treturn Time.get_ticks_msec()` | 1 FAIL `clock\.gd:3: \[lint\.det-wallclock\] error` |
| FAULT-A3-17 | first op `write` `harness.toml` = `[lint]\nreplay_dirs = ["res://"]\n` (R-08); then `scenes/t.tscn`: format=3, Node root + child `[node name="T" type="Timer" parent="."]` (no process_callback) | 5 WARN `t\.tscn:\d+: \[lint\.det-idle-timer\]` |
| FAULT-A3-18 | `if Input.is_key_pressed(KEY_SPACE):` in `scripts/f.gd` | 5 WARN `\[lint\.raw-keycode\]` |
| FAULT-A3-19 | c28 (tab lines then an 8-space line) | 1 FAIL `f\.gd:4: \[lint\.indent-mixed\]` |
| FAULT-A3-20 | `sim/state.gd`: `extends RefCounted\nvar target: NodePath` | 1 FAIL `state\.gd:2: \[lint\.sim-node\]` |
| FAULT-A3-21 (nice) | d03: `var b := Button.new()` + `b.connect("nosuch", _x)` | 1 FAIL `\[lint\.signal-name\]` |
| FAULT-A3-22 | c04 yield file; verb `check` (A1 calls lint); max_seconds 60 | 1 FAIL `\[syn-yield\]` |
| FAULT-A3-23 | c10 file; args `["--godot3-oracle", "{project}/scripts/f.gd"]`; max_seconds 30 | 1 FAIL `\[lint\.g3-oracle\].*randf_range` |
| FAULT-A3-24 | c04 file; args `["--hook", "{project}/scripts/f.gd"]` | 1 FAIL `\[syn-yield\]`, `^lsp: not running` |
| FAULT-A3-25 | `harness.toml` `[lint]\nseverity = {"syn-yeld" = "off"}` | 2 ERROR `syn-yeld` |
| FAULT-A3-26 | `project.godot` `config_version=5` -> `config_version=4` (`replace` op) | 1 FAIL `\[lint\.g3-project\]` |
| FAULT-A3-27 (nice) | `scripts/bad.gd` parse error line 4; verb `lsp`, args `["diag", "--oneshot", "{project}/scripts/bad.gd"]`; max 60 | 1 FAIL `bad\.gd:4: \[lint\.lsp\] error` |
| CLEAN-A3-01 | none (`lint_base`) | 0 PASS, not_regex `\[` |
| CLEAN-A3-02 | fixture `lint_clean_demo` | 5 WARN `\[lint\.det-idle-timer\]`, `\[lint\.det-global-rng\]`, not_regex `\] error:` |
| CLEAN-A3-03 | `lint_clean_demo` with `harness.toml` replaced (`write`) by `[lint]\nreplay_dirs = []` | 0 PASS |

## 6. Fixtures needed (test-writer T3; `tests/fixtures/projects/<name>/`, C §2.11)
### 6.1 `godot3_scripts` (r1_5 corpus; the scratchpad copy is ephemeral, so content is given here)
`project.godot` (C §2.11 minimum + `[input]` with `jump`), `scenes/ok.gd` (`extends Node2D`), `FIXTURE.md` (lint
fixture, deliberately broken; `h check` = FAIL). Files `cases/*.gd` (`\n` newline, `\t` tab), expected lint findings
as `line:rule(E|W)`:
| file | content | expected |
|---|---|---|
| c01_kinematic | `extends KinematicBody2D\nfunc _ready():\n\tpass` | 1:class-KinematicBody2D(E) |
| c02_onready | `extends Node\nonready var a = 1\nfunc _ready():\n\tpass` | 2:syn-onready(E) |
| c03_export | same with `export var a = 1` | 2:syn-export(E) |
| c04_yield | `extends Node\nfunc _ready():\n\tyield(get_tree().create_timer(1.0), "timeout")` | 3:syn-yield(E) |
| c05_connect3 | `extends Node\nfunc _ready():\n\tconnect("tree_exited", self, "_x")\nfunc _x():\n\tpass` | 3:syn-connect-3arg(E) |
| c06_instance | `extends Node\nfunc _ready():\n\tvar s = PackedScene.new()\n\tvar n = s.instance()` | 4:syn-instance(E) |
| c07_tool | `tool\nextends Node` | 1:syn-tool(E) |
| c08_setget | `extends Node\nvar a = 1 setget set_a\nfunc set_a(v):\n\ta = v` | 2:syn-setget(E) |
| c09_rect | `extends Control\nfunc _ready():\n\trect_position = Vector2(1,1)` | 3:syn-rect-props-gd(W) |
| c10_randrange | `extends Node\nfunc _ready():\n\tprint(rand_range(0,1))` | 3:fn-rand_range(E) |
| c11_variant_infer | `extends Node\nfunc _ready():\n\tvar d := {}\n\tvar x := d.get("a")\n\tprint(x)` | 4:syn-dict-get-infer(W) |
| c12_poolarr | `extends Node\nvar a: PoolStringArray` | 2:syn-poolarray(E) |
| c13_os_ticks | `extends Node\nfunc _ready():\n\tprint(OS.get_ticks_msec())` | 3:syn-os-ticks(E) |
| c14_file | `extends Node\nfunc _ready():\n\tvar f = File.new()` | 3:syn-file-dir-class(E) |
| c15_move_and_slide | `extends CharacterBody2D\nfunc _physics_process(d):\n\tvelocity = move_and_slide(velocity, Vector2.UP)` | 3:syn-move-and-slide-args(E) |
| c16_changescene | `extends Node\nfunc _ready():\n\tget_tree().change_scene("res://a.tscn")` | 3:fn-change_scene(E) |
| c17_stepify | `extends Node\nfunc _ready():\n\tprint(stepify(1.234,0.1))` | 3:fn-stepify(E) |
| c18_emit_str | `extends Node\nsignal foo\nfunc _ready():\n\temit_signal("fooo")` | 4:syn-yield-signal-string-emit(W), 4:lint.signal-name(E) |
| c19_get_node_in_var | `extends Node\nvar a = $Missing\nfunc _ready():\n\tprint(a)` | 2:syn-get-node-ready-var(E) |
| c20_ok_baseline | `extends Node\n@export var a: int = 1\n@onready var b = 2\nfunc _ready():\n\tprint(a, b)` | none |
| c21_lambda_capture | `extends Node\nfunc _ready():\n\tvar n := 0\n\tvar f := func(): n += 1\n\tf.call()\n\tprint(n)` | 4:syn-lambda-capture-reassign(W) |
| c22_tween_new | `extends Node\nfunc _ready():\n\tvar t = Tween.new()\n\tt.interpolate_property(self,"x",0,1,1)` | 3:syn-tween-new(E), 4:syn-tween-interpolate(E) |
| c23_shadow_dot_super | `extends Node\nfunc _ready():\n\t._ready()` | 3:syn-dot-super(W) |
| c24_typedarray | `extends Node\nvar a: Array[int] = [1, "x"]` | none (engine only) |
| c25_deg2rad | `extends Node\nfunc _ready():\n\tprint(deg2rad(90))` | 3:fn-deg2rad(E) |
| c26_empty | `extends Node\nfunc _ready():\n\tvar a = []\n\tprint(a.empty())` | 4:syn-empty-call(E) |
| c27_hallucinated | `extends Node\nfunc _ready():\n\tself.get_player_position()\n\tvar v = Vector2(1,1)\n\tv.length_squared_fast()` | none |
| c28_tabspace | `extends Node\nfunc _ready():\n\tvar a = 1\n        print(a)` (8 spaces) | 4:lint.indent-mixed(E) |
| c29_int_div | `extends Node\nfunc _ready():\n\tvar a: int = 5 / 2\n\tvar b: float = 5 / 2\n\tprint(a,b)` | none |
| c30_preload_dyn | `extends Node\nfunc _ready():\n\tvar p = "res://x.tscn"\n\tvar s = preload(p)` | none |
| c31_assign_ret_void | `extends Node\nfunc f() -> void:\n\tpass\nfunc _ready():\n\tvar a = f()` | none |
| c32_get_tree_input | `extends Node\nfunc _ready():\n\tInput.is_action_pressed("nope")\n\tprint(Input.is_action_pressed("nope"))` | 3:lint.input-action(E), 4:lint.input-action(E) |
| d01_untyped_connect | `extends Node\nfunc _ready():\n\tvar b = Button.new()\n\tb.connect("pressed", self, "_x")\nfunc _x():\n\tpass` | 4:syn-connect-3arg(E) |
| d02_untyped_move | `extends Node\nfunc _ready():\n\tvar b = Node2D.new()\n\tb.rect_position = Vector2.ZERO` | 4:prop-rect_position(E) |
| d03_signal_connect_str | `extends Node\nfunc _ready():\n\tvar b = Button.new()\n\tb.connect("pressed", _x)\n\tb.connect("nosuch", _x)\nfunc _x():\n\tpass` | 5:lint.signal-name(E) |
Scenes `scenes/*.tscn`:
- `g3.tscn`: `[gd_scene load_steps=2 format=2]` / blank / `[ext_resource path="res://scenes/ok.gd" type="Script" id=1]`
  / blank / `[node name="Root" type="Spatial"]` / `script = ExtResource( 1 )` / blank /
  `[node name="Body" type="KinematicBody2D" parent="."]` / `rect_position = Vector2( 10, 10 )` -> 1:tscn-g3-header,
  3:tscn-ext-path-first, 3:tscn-g3-numeric-id, 5:tscnclass-Spatial, 6:tscn-extresource-spaces,
  8:tscnclass-KinematicBody2D, 9:tscn-rect-props (all E).
- `g4_mixed.tscn`: `[gd_scene load_steps=2 format=3]` / blank / `[ext_resource type="Script" path="res://scenes/ok.gd"
  id="1"]` / blank / `[node name="Root" type="Node2D"]` / `script = ExtResource( 1 )` / blank /
  `[node name="Body" type="Sprite" parent="."]` / `rect_position = Vector2( 10, 10 )` / `nonexistent_prop = 5` /
  blank / `[node name="Sub" type="Node2D" parent="Missing"]` -> 6:tscn-extresource-spaces, 8:tscnclass-Sprite,
  9:tscn-rect-props (E).
- `g4_ok.tscn` (g4_mixed header/ext_resource, `ExtResource("1")`, Root Node2D + child CharacterBody2D) and
  `g4_badscript.tscn` (`[gd_scene format=3]`, script `res://cases/c02_onready.gd` id `"1"` on a Node root) -> none.
### 6.2 `lint_base` (clean 4.7 project, no harness.toml; must give PASS with zero findings, also warnings, under the
default and under `replay_dirs = ["res://"]`)
`project.godot` (C §2.11 + `[input]` actions `jump`, `move_left`, `move_right`), `FIXTURE.md`,
`scripts/player.gd` (typed `CharacterBody2D`, `signal hit`, `hit.emit()` (no string emit: it warns), actions via
`Input.get_axis("move_left","move_right")`/`is_action_just_pressed("jump")`, one `create_tween().set_process_mode(
Tween.TWEEN_PROCESS_PHYSICS)`), `scripts/base.gd` (`class_name BaseThing extends Node`, `signal died`),
`scripts/rng.gd` (global `seed()`/`randi()` allowed; no `randi() % n`, which warns), `scripts/input_remap.gd` (uses `KEY_SPACE`), `sim/world.gd`
(`extends RefCounted`, int ids, injected `RandomNumberGenerator`), `scenes/main.tscn` (format=3, Node2D root with
player script, `Timer` child with `process_callback = 0`, `AnimationPlayer` child with `callback_mode_process = 0`).
### 6.3 `lint_clean_demo`
Text files of godot-demo-projects@b761b4c `2d/dodge_the_creeps` (MIT; keep `LICENSE`): `project.godot`, `hud.gd`,
`hud.tscn`, `main.gd`, `main.tscn`, `mob.gd`, `mob.tscn`, `player.gd`, `player.tscn` (no `.uid`, no art), plus our own
`harness.toml` = `[lint]\nreplay_dirs = ["res://"]\n` (R-08; strict mode, so the 9 warnings fire). FIXTURE.md records
the source commit, licence, that harness.toml is ours, and "lint only: WARN 9 warnings, 0 errors; h check not applicable".

## 7. Build order (builder B3, after B1's step 0; run `pytest tests/contract/a3 tests/unit/a3 -q` per step)
1. `build_lint_data.py` + the three JSON files; `rules.py` loader -> AC-03.1.
2. `scan.py` regex pass, dedup, comment skipping, `verbs/lint.py` paths/stats/output, `--hook` without LSP
   -> AC-03.2 (regex rows), 3, 4, 6-10, 13, 21.
3. Config `[lint]` + suppression -> AC-03.11, 12.
4. `project.py`/`checks.py`: input actions, signals, indent, `lint.*` det/sim/key/g3 rules -> AC-03.2 (all rows),
   5, 14-20, 7.
5. `run_lint` API, coordinated with B1 for `h check` -> AC-03.23. 6. `oracle.py` -> AC-03.22.
7. `lsp_daemon.py`, `lsp_client.py`, `verbs/lsp.py`, hook LSP path -> AC-03.24-27.
8. `h selftest --area A3`, then `tools/dev/ci.sh --quick` -> AC-03.28.

## 8. Out of scope, open questions, assumptions
### 8.1 Out of scope / deferred
`h fmt` (verb list is closed, C §2.1; gdtoolkit is dev-only, not stdlib; v0.1 could add `h lint --format-check`);
auto-fix or `--convert-3to4` (r1_5: it renamed `$Sprite` to `$Sprite2D`); `.tscn` `[connection]` and node-path checks
(A1/A2); LSP hover/definition/symbols, DAP; C# rules (D1); LSP daemon idle auto-shutdown (`stop --all` exists).

### 8.2 Open questions [U]
1. Closed by R-08: default `replay_dirs = []`; template, sample and `lint_clean_demo` opt in to `["res://"]` (§2.6).
2. Instanced/inherited `.tscn` nodes (no `type=`) are not checked for idle Timer/AnimationPlayer.
3. Whether the headless editor daemon writes into a real project (spike: sources untouched; `.uid` files came from
   `--import`); two editors on one project are avoided by one daemon per project.

### 8.3 Deviations from the contract (all accepted; now in the contract)
- **Accepted (R-09).** Godot kinds `oracle` (60 s, expected rc {0}) and `lsp_start` (30 s, readiness) are in C §2.8.2;
  B1 builds `godot.spawn(run, kind, project, args, log_path=None) -> Popen` (C §2.9). `lsp_daemon.py` uses it and
  never calls `subprocess` on Godot.
- **Accepted (R-01).** Tests read `tools/harness/rules/*.json` as public data (layer `data`); no harness module is
  imported (C §2.12).
- **Accepted (R-48).** `h lsp stop --all` needs no project (C §2.2); `start|status|diag` resolve one.
- **Accepted (R-38).** r1_5 ids keep upper case (`enum-BUTTON_LEFT`, `class-KinematicBody2D`); C §2.7's pattern is
  `[a-z0-9][a-zA-Z0-9._-]*` (upper case only in undotted r1_5 ids), matching §2.4.

### 8.4 Assumptions taken
D1 (GDScript only), D5 small tier; A1 owns `h check` and calls `run_lint` only (§2.3, R-29); A8 owns hook scripts
and decides blocking; A5 provides the `Rng` autoload named in hints; A9's sim dirs default to `res://sim` and A9
uses `lint.sim-node` as its "no Node/NodePath in state" rule; the sample (A9) is written to give `h lint` PASS.
