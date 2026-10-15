# 00 Interface contract (P0)

Status: spec v2, 2026-10-15, Opus planner P0 re-run: applies REVIEW.md B01-B07, N03, N14, N17, N18 (R-ids in §8.1). Every area spec (01-10) must
conform to this file; a deviation goes in that spec's §8 and the reviewer decides. Tags: [Run] verified (§3.4), [U] unverified, Δ = change to existing
code (§3.2). Supersedes plan §3.1/§10 on two points: runtime data files are TOML/JSON, not YAML (`fault.toml`), and there is no committed
`expected_matrix.yaml`.

## 1. Purpose and failure modes covered

One shared surface for all `h` verbs, so parallel planners and builders produce parts that fit and tests can be written black-box from specs.
Covers: **exit codes lie** (R1.1 #4, R1.5 #2, S2: one invocation path `godot.py` with timeout, full log, log scan as the authoritative signal, rc
only an extra failure signal, rc 124 = hang); **F11 noisy logs** (<= 40 stdout lines, verdict first, full logs on disk); **F7 class cache** (R1.1
#3, content-based auto-import §2.8.7); build risks (plan §12): spec drift, parallel collisions (B2 discovery, B3 temp copies), builders loosening
tests (lock, pathguard), lost work after a reset (handoff format).

## 2. Interfaces

### 2.1 Shim and dispatcher (B1, B2)
- `tools/harness/h` runs `python3 -I` (stdlib only, Python >= 3.11 for `tomllib`) with `harness.cli.main(argv)`. It exports `HARNESS_REPO` (the
  harness repo root). Δ It must **not** `cd`: relative paths (`--project sample`, spec files) resolve against the caller's cwd.
- Verb discovery: every module `tools/harness/harness/verbs/<name>.py` whose name does not start with `_` is a verb. The CLI name is the module name
  with `_` -> `-` (`scene_gen.py` -> `h scene-gen`). A module name may end in one `_` (keyword clash); the CLI name drops it (`import_.py` -> `h
  import`). Names starting `_` stay private. No registry.
- Each verb module exports `HELP: str` (one line, <= 70 chars) and `run(argv: list[str]) -> int`. Optional: `CONFIG_TABLE: str` + `CONFIG_KEYS:
  dict[str, type]` (§2.6). Subcommands (`baseline propose`, `lsp start`) are parsed by the verb itself; line 1 still uses the verb name.
- `h --help`: rc 0, `usage: h <verb> [args]` then one line per verb `  <verb>  <HELP>`. `h` with no args: same text, rc 2. `h <unknown>`: exactly one
  stdout line `ERROR h unknown verb '<x>'` (+ ` (did you mean '<y>'?)` when edit distance <= 2), rc 2. These three are the only outputs without a run
  dir.
- `h <verb> --help` / `-h`: usage text <= 40 lines, rc 0, no run dir.
- v0 verb list is closed (plan §3.2): `doctor sync import api check lint digest scene-gen scene-edit test run trace shot baseline lsp selftest init`.
  A new verb needs a planner + reviewer note.

### 2.2 Common flags, project resolution, environment
Every verb accepts (argparse parent parser `out.common_parser()`): `--project DIR` (Godot project dir containing `project.godot`, relative to
cwd), `--strict` (warnings count as errors: a would-be WARN becomes FAIL, rc 1), `-h`/`--help` (usage, rc 0). Argument errors print `ERROR <verb>
usage: <message>` (not argparse's stderr text) and give rc 2.

Project resolution for verbs that need one (all but `doctor`, `selftest`, `api`, `lsp stop --all`; `init --new` may create the dir): `--project` >
`$HARNESS_PROJECT` > nearest ancestor of cwd containing `project.godot`. None found, or the dir has no `project.godot`: rc 2, `ERROR <verb> no Godot
project (pass --project DIR)`.

Env vars (default): `HARNESS_REPO` (set by shim; runners, rules, selftest/), `HARNESS_CACHE` (`~/.cache/godot-harness`; pinned tools, API
index, `pins.cache_dir()`), `HARNESS_GODOT` (unset; Godot binary, beats harness.toml and `$HARNESS_REPO/tools/bin/godot`), `HARNESS_PROJECT`
(unset; project dir fallback), `HARNESS_OUT` (unset; out root override, else §2.5), `HARNESS_TMP` (`${TMPDIR:-/tmp}/godot-harness`; temp copies
for selftest and tests), `HARNESS_TIMEOUT_SCALE` (`1.0`; multiplies every default timeout; 0.1-10, else rc 2), `HARNESS_ROOT` (unset; dev tools
only, `tools/dev/_common.sh`). Also read, for attribution and tool lookup only: `PATH`, `HOME`, `TMPDIR`, `USER` (attribution),
`CLAUDE_PROJECT_DIR` (hook/launcher). No other env var may change verb behaviour (builder rule: no test-detection branches).

### 2.3 Stdout format (all verbs)
Grammar, one item per line, in this order; nothing is printed to stderr by a verb:
1. **Verdict line** (always): `^(PASS|FAIL|WARN|ERROR) <verb> <reason>$`, reason 1-100 chars, e.g. `2 errors, 1 warning in 14 files (3.4s)`.
2. **Stat lines** (0+): `^[a-z][a-z0-9_-]*: <value>$`, value not starting with `[`. Project verbs print `project: <abs path>` first. Verbs that may
   import print `import: ran (<why>)|fresh|skipped`. A verb whose stat lines would exceed the limit ends them with `more: <K> lines in <path>` (A1
   api, A2 digest).
3. **Check lines** (0+): `^(OK|FAIL|SKIP|WARN) +([^:]+): (.*)$`; the name has no colon and may contain spaces and dots (`SKIP autoload Rng: not
   shipped`, `FAIL 1280x720: ...`). Used by doctor, selftest, per-item tables.
4. **Finding lines** (0+): `^<loc>: \[<rule>\] (error|warning|info): <message>( \(hint: <hint>\))?$`
   - `<loc>` = `res://path:LINE` | `res://path` for project files; a cwd-relative or absolute path (with optional `:LINE`) for files outside the
     project; `-` when there is no file. Lines are 1-based.
   - Order: errors, warnings, info; then path, line. Identical (loc, rule, message) collapse into one line with ` (xN)` appended. Info lines are shown
     only if room is left.
5. **Truncation line** (if needed): `... <K> more findings (<e> errors, <w> warnings) in findings.jsonl`.
6. **Log line** (always, last): `log: <run dir>/` (cwd-relative if under cwd, else absolute; trailing `/`).

Limits: <= 40 lines total; each line <= 240 chars (cut with `...`). Exempt: `--help` output. Invariants (tested on every invocation by the test
helper): FAIL => at least one `error` finding or `FAIL` check line; WARN => at least one `warning` finding/`WARN` check line and no error; PASS => no
error/warning findings. An ERROR run prints the verdict, `project:` if resolved, and `log:` (e.g. `ERROR check godot binary not found:
/nonexistent/godot (run tools/bootstrap.sh)`). Literal examples (paths shortened only where marked `...`):
```
$ tools/harness/h check --project sample
FAIL check 2 errors, 1 warning in 14 files (3.4s)
project: /home/user/godot-harness/sample
import: fresh
files: 11 .gd, 3 .tscn
res://player/player.gd:12: [godot.parse-error] error: Expected expression after "+" operator.
res://levels/l1.tscn: [godot.parent-vanished] error: Parent path './Root/A' for node 'B' has vanished (hint: parent= never includes the root name)
res://ui/hud.gd:40: [syn-yield] warning: yield() was removed in Godot 4 (hint: await <signal>)
log: sample/.harness/out/20261015T142233Z-check-a3f9/

$ tools/harness/h doctor
PASS doctor 6/6 checks ok
OK   godot: 4.7.stable.official.5b4e0cb0f
OK   gdunit4: v6.2.2 0127a55f4543
OK   odiff: .../odiff/node_modules/@odiff/linux-x64/odiff
OK   venv: .venv ok
OK   xvfb-run: /usr/bin/xvfb-run
OK   compare: /usr/bin/compare
log: .harness/out/20261015T142400Z-doctor-19ce/
```

### 2.4 Verdicts and exit codes
| rc | Verdict | When |
|---|---|---|
| 0 | PASS | no error/warning findings |
| 1 | FAIL | >= 1 error finding (or warning under `--strict`) |
| 2 | ERROR | usage/config: bad flag, bad `harness.toml`, no project, input file fails its schema |
| 3 | ERROR | harness internal error: uncaught exception (traceback in `traceback.txt`), harness runner rc 2/3 |
| 4 | ERROR | environment: Godot missing or wrong version, xvfb-run/odiff/gdUnit4 missing, `--headless` for shot |
| 5 | WARN | warnings only, `--strict` off |
ERROR conditions stop the verb at once (first one wins). A hang or crash of Godot is a **finding** (FAIL), not ERROR, because project code usually
causes it. Δ `tools/dev/ci.sh` treats rc 5 from an `h` layer as PASS (warnings).

### 2.5 Run directory
- Out root: `$HARNESS_OUT` > `<project>/.harness/out` (project verbs) > `$HARNESS_REPO/.harness/out`. The verb creates `<out root>/../.gdignore`
  (empty) so Godot never imports run outputs (hidden dirs are skipped anyway [Run]).
- Run id: `^\d{8}T\d{6}Z-<verb>-[0-9a-f]{4}$` (UTC start time, random suffix). `<out root>/latest` is a symlink to the newest run dir, replaced
  atomically. Retention: at start, prune to the newest 50 run dirs, never one < 10 min old.
- Contents (reserved names; verbs put their own artefacts under `artifacts/`): `run.json`, `summary.txt` (byte-identical to stdout), `findings.jsonl`
  (all findings, uncapped), `godot/NN-<kind>.log` (combined stdout+stderr per Godot invocation, NN from 01), `godot/NN-<kind>.runner.jsonl` (runner
  `@@H` records), `traceback.txt` (rc 3 only), `artifacts/`.

`run.json` (JSON Schema, draft 2020-12; additional properties allowed for verb extras under `extra`):
```json
{"type":"object","required":["schema","run_id","verb","argv","cwd","project","started_at","duration_s","rc","verdict","reason","counts",
 "findings_total","truncated","invocations"],
 "properties":{"schema":{"const":"harness.run/1"}, "run_id":{"type":"string"}, "verb":{"type":"string"}, "cwd":{"type":"string"},
  "argv":{"type":"array","items":{"type":"string"}}, "project":{"type":["string","null"]}, "duration_s":{"type":"number"},
  "started_at":{"type":"string","format":"date-time"}, "rc":{"enum":[0,1,2,3,4,5]}, "reason":{"type":"string"},
  "verdict":{"enum":["PASS","FAIL","WARN","ERROR"]}, "findings_total":{"type":"integer"}, "truncated":{"type":"boolean"},
  "counts":{"type":"object","required":["error","warning","info"],
            "properties":{"error":{"type":"integer"},"warning":{"type":"integer"},"info":{"type":"integer"}}},
  "godot":{"type":["object","null"],"properties":{"path":{"type":"string"},"version":{"type":"string"}}},
  "invocations":{"type":"array","items":{"type":"object",
    "required":["n","kind","argv","timeout_s","rc","timed_out","duration_s","log","scan_verdict"],
    "properties":{"n":{"type":"integer"},"kind":{"type":"string"},"argv":{"type":"array","items":{"type":"string"}},
      "timeout_s":{"type":"number"},"rc":{"type":"integer"},"timed_out":{"type":"boolean"},"duration_s":{"type":"number"},
      "log":{"type":"string"},"scan_verdict":{"enum":["PASS","WARN","FAIL"]},"runner_rc":{"type":["integer","null"]},
      "retried":{"type":"boolean"},"display_failed":{"type":"boolean"}}}},
  "extra":{"type":"object"}}}
```
`findings.jsonl`, one object per line: `{"path": "res://a.gd"|null, "line": 3|null, "rule": "godot.parse-error", "severity": "error"|"warning"|"info",
"message": "...", "hint": "..."|null, "source": "scan"|"runner"|"verb", "invocation": 1|null}`.

### 2.6 `harness.toml` (project root, optional)
Missing file = all defaults. Invalid TOML, an unknown table, an unknown key or a wrong type: rc 2 with a finding `res://harness.toml: [harness.config]
error: <what>`. Precedence: CLI flag > env > harness.toml > default.
```toml
[harness]
schema = 1
godot = ""                    # binary path, relative to the project dir; HARNESS_GODOT wins
godot_version = "4.7.stable.official.5b4e0cb0f"   # must equal `godot --version`, else rc 4
tick_rate = 60                # physics ticks per second (A5, A7, A9 template)
renderer = "gl_compatibility" # only value accepted in v0 (A6)
autoloads = ["Harness", "Rng", "CommandBus", "Trace"]   # autoloads `h sync` enables (A1; insertion rule in A1 §2.3)
sim_dirs = ["res://sim"]      # determinism-lint scope (A3, A9)
test_dir = "res://tests"      # gdUnit4 root (A4)
[timeouts]                    # seconds per invocation kind (§2.8.2); before HARNESS_TIMEOUT_SCALE
[scan]
ignore = []                   # extra regexes for benign log lines; may not match protected rules (§2.8.4)
```
Other tables belong to areas: a verb module declares `CONFIG_TABLE = "lint"` and `CONFIG_KEYS = {"severity": dict}`; `config.py` collects them by
discovery (no shared registry). Exactly one declaring module per table: `scene` `verbs/digest.py` (A2), `shot` `verbs/shot.py` (A6), `run`
`verbs/run.py` (A5), `feel` `verbs/trace.py` (A7), `hooks` `verbs/init.py` (A8), `lint` `verbs/lint.py` (A3), `test` `verbs/test.py` (A4). A second
declaration of the same table makes `config.py` raise (rc 3).

### 2.7 Rule ids
`[a-z0-9][a-zA-Z0-9._-]*`, globally unique; upper case only in undotted r1_5 ids (`class-KinematicBody2D`). `assert_contract` uses this pattern.
Dotted prefixes per owner: `godot.` and `harness.` (P0/A1), `check.`, `api.`, `selftest.` (A1), `scene.` (A2), `lint.` (A3 project-aware checks),
`test.` (A4), `run.` (A5), `shot.` (A6), `feel.` (A7), `hook.` (A8), `sim.` (A9). The r1_5 rule ids (`syn-*`, `fn-*`, `prop-*`, `tscn-*` ...) stay
undotted; any new rule must be dotted. Core ids defined here: `harness.hang`, `harness.crash`, `harness.rc`, `harness.runner-incomplete`,
`harness.config`, `harness.godot-version`, `harness.internal`, plus the `godot.*` scan rules in §2.8.4.

### 2.8 Godot invocation contract (`tools/harness/harness/godot.py`)
All Godot processes are started by `godot.run()` or `godot.spawn()`; no verb calls `subprocess` on Godot directly (A6's `xvfb-run` goes through
`godot.run(..., display="xvfb")`, odiff through `proc.run()`).

**2.8.1 Binary.** `HARNESS_GODOT` > harness.toml `godot` > `$HARNESS_REPO/tools/bin/godot`. Missing/not executable: rc 4 `godot binary not found:
<path> (run tools/bootstrap.sh)`. `--version` (last stdout line) must equal `godot_version` (default = pins.toml `godot_version_string`), else rc 4
with finding `[harness.godot-version]`. The result is cached in `$HARNESS_CACHE/godot_version.json` keyed by (realpath, mtime, size).

**2.8.2 Command line.** `[godot] + display flags + ["--path", <abs project>] + kind args (+ ["--", user args])`, stdin `/dev/null`, stdout+stderr
combined into one log file, cwd = project dir, own process group. With `project=None` (kinds `version`, `doctool` only) there is no `--path`, `cwd` is
required and no import check runs. Display `headless` -> `--headless`. Display `xvfb` -> prefix `xvfb-run -a -s "-screen 0 1920x1080x24"` and add
`--rendering-method gl_compatibility --audio-driver Dummy`; never together with `--headless` for image capture (A6 refuses a user-passed `--headless`
with rc 4 in every mode; A6 `--layout` may run headless). Default timeouts (s), scaled by `HARNESS_TIMEOUT_SCALE`, overridable per kind in
`[timeouts]`:
| kind | version | import | check_only | runner | smoke | test | scenario | shot | movie | doctool | oracle | lsp_start |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s | 20 | 180 | 30 | 60 | 30 | 300 | 120 | 60 | 300 | 120 | 60 | 30 |
Runner-style kinds (`runner`, `smoke`, `scenario`, `shot`) take `-s <abs path of runner>`; `check_only` adds `--check-only -s res://<file>`.
`lsp_start` is for `godot.spawn` (§2.9): its own session and process group, stdin `/dev/null`, log under the run dir (or a given path), one invocation
entry once readiness is known (`rc` 0 ready / 1 failed, `timed_out`), no auto-import.

**2.8.3 Timeout and rc.** At T: SIGTERM to the group; T+3 s: SIGKILL. Recorded rc 124, `timed_out: true`, finding `<loc>: [harness.hang] error: no
exit within Ts (last log line: <...>)`, loc = runner/scene target if known else `-`. `godot.run()` returns by T+5 s. Signal deaths are normalised to
128+N (SIGABRT -> 134, [Run]) and give `[harness.crash] error`. `import` is retried once on rc 134 (R1.4 §4), `retried: true`, both logs kept. Display
`xvfb`: after the SIGKILL path, remove each `/tmp/.X<n>-lock` created after the invocation started whose PID (file content) is dead, plus
`/tmp/.X11-unix/X<n>`. If the log matches `Unable to create DisplayServer|Xvfb failed to start|xvfb-run: error`, retry once (`retried: true`); if it
still fails, `display_failed: true` and the verb maps that to rc 4 `[shot.no-display]` (verified by A6 AC-06.19).

**2.8.4 Log scan (`logscan.py`, public to unit tests).** Before matching, ANSI CSI sequences `\x1b\[[0-9;]*[A-Za-z]` are stripped. Lines starting
with `@@H` + space and the built-in benign list are skipped. Rules, first match wins, in this order:
| id | regex (Python, per line) | severity | location |
|---|---|---|---|
| `godot.parse-error` * | `^SCRIPT ERROR: Parse Error: (.*)` | error | next `(res://F:L)` |
| `godot.script-error` * | `^SCRIPT ERROR: (.*)` | error | next `(res://F:L)` |
| `godot.script-load-failed` * | `^ERROR: Failed to load script "(res://[^"]+)"` | error | the quoted path, no line |
| `godot.crash` * | `^(handle_crash: Program crashed\|Aborted\|Segmentation fault)` | error | - |
| `godot.load-failed` | `^ERROR: (Failed loading resource\|Failed to load resource\|Cannot load\|No loader found)(.*)` | error | `res://` path in the line |
| `godot.parent-vanished` | `^WARNING: Parent path .* has vanished` | error | - |
| `godot.vanished` | `^WARNING: .*has vanished` | error | - |
| `godot.leak` | `^WARNING: \d+ ObjectDB instances? (was\|were) leaked at exit` | info | - |
| `godot.error` | `^ERROR: (.*)` | error | next `(res://F:L)` |
| `godot.warning` | `^WARNING: (.*)` | warning | next `(res://F:L)` |
(`\|` in the table is the Markdown escape of `|`.) "Next `(res://F:L)`" = the first match of `\((res://[^():]+):(\d+)\)` in the matched line or the
following 6 lines before the next rule match; if none, the first `res://<path>:<line>` token of the matched line; engine C++ locations
(`(core/...cpp:N)`) are never used. `*` = protected: never ignored, never downgraded. Built-in benign list: `^Godot Engine v\d`, `remote port number
must be between 1 and 65535`, `Could not set V-Sync mode`, `^ALSA lib `, `cannot find card`. `[scan] ignore` regexes and a verb's declared downgrade
policy (in its spec) apply only to non-protected rules; an ignore regex that matches a sample line of a protected rule (`SCRIPT ERROR: Parse Error:
x`, `SCRIPT ERROR: x`, `ERROR: Failed to load script "res://x.gd"`) is rejected with rc 2. API: `logscan.scan(text: str, extra_ignore: list[str] = [])
-> list[dict]` (keys of findings.jsonl minus `source`/`invocation`).

**2.8.5 Runner protocol.** Harness runners live in `$HARNESS_REPO/addons/harness/runners/<name>.gd` and are run by absolute path with `--path
<project>` (S1 [Run]), so one-shot checks need no `h sync`. Each runner is one file (`extends SceneTree`, inner classes allowed, no `class_name`, no
`preload` of other harness files). A runner may `load()` (never `preload`) a library file under `$HARNESS_REPO/addons/harness/runners/` whose absolute
path comes from its args or plan; library files start with `_`, have no `class_name`, and never print `done` or call `quit()`. In-game code (autoloads
`Harness`, `Rng`, `CommandBus`, `Trace`, and gdUnit4) is installed by `h sync`. Runners print records as single stdout lines `@@H <json>`:
`{"t":"finding", path, line, rule, severity, message, hint}`, `{"t":"stat","key":..,"value":..}`, `{"t":"data",...}` (verb-specific, saved in
`.runner.jsonl`), and last `{"t":"done","rc":N}` immediately followed by `quit(N)`. Runner rc: 0 clean, 1 findings, 2 bad args, 3 runner bug. Runners
check `load()` results with `can_instantiate()` before `.new()` and `quit(1)` themselves (S2).

**2.8.6 Verdict merge per invocation.** worst of: (a) scan verdict (error -> FAIL, warning -> WARN); (b) rc signal: 124 -> FAIL hang, >=128 -> FAIL
crash, rc outside the kind's expected set (`check_only`: {0,1}; runner kinds: {0,1}; `import`, `oracle`: {0}; `test`: per A4 map) -> FAIL
`[harness.rc]`; (c) runner: no `done` record -> FAIL `[harness.runner-incomplete]` even when rc = 0; runner rc 2/3 -> verb rc 3. rc 0 never improves
(a)-(c). Runner findings win over scan findings with the same (path, line, message) (dedup). This dedup is the minimum: a verb may dedup further (A1
by normalised message, A4 by location), but may drop a protected scan finding only when a runner/XML finding covers the same problem. The verb's
verdict is the worst over its invocations and own findings.

**2.8.7 Auto-import (explicit).** `godot.run` never imports. Verbs call `godot.ensure_imported(run, project)` before their first invocation of a kind
other than `version`/`import`/`doctool`/`oracle`/`lsp_start`. It runs `import` when `.godot/` or `.godot/global_script_class_cache.cfg` is missing, or
when the set of (class, res path) pairs in the cache's `list` [Run, REVIEW §7] differs from the set parsed from every project `*.gd`
(`^\s*class_name\s+(\w+)` in the first 50 lines). Scope: everything Godot imports, including `addons/`, excluding `.godot/`, `.harness/`, hidden dirs
and dirs with `.gdignore`. `base` is not compared [U]. Script mtimes are not used. It prints `import: ran (<why>)` (`no .godot/`, `no class cache`,
`stale class cache (<first differing file>)`, or an A1 §3.3 refinement), else `import: fresh`. Import findings count.

### 2.9 Core Python API for builders (tests import only the §2.12 allowlist)
```python
# harness/out.py
class Run:            # with out.Run(verb, argv, project=None) as r: ...  -> creates run dir; on exception rc 3
    def finding(self, path, line, rule, severity, message, hint=None, source="verb"): ...
    # add_findings(findings) (dicts, e.g. Invocation.findings); stat(key, value); check(status, name, detail)
    # with status in OK FAIL SKIP WARN; error(rc, reason) with rc in 2,3,4: stop with ERROR
    def finish(self, reason) -> int: ...                  # render, write files, return rc
def common_parser() -> argparse.ArgumentParser: ...       # --project --strict; error() -> rc 2 contract line
def render(verb, verdict, reason, stats, checks, findings, log_dir, max_lines=40) -> list[str]: ...
# harness/project.py   resolve(arg: str|None) -> Path ; res_path(project, fs_path) -> "res://..."
# harness/config.py    load(project) -> dict  (validates §2.6 incl. discovered CONFIG_TABLEs)
# harness/godot.py     binary(run, project) -> Path ; ensure_imported(run, project) -> str  (prints import:, §2.8.7)
def run(run, kind, project, args=[], user_args=[], runner=None, display="headless", timeout=None,
        cwd=None) -> Invocation: ...          # project=None only for version/doctool, then cwd required (§2.8.2)
def spawn(run, kind, project, args, log_path=None) -> subprocess.Popen: ...   # lsp_start (§2.8.2)
# Invocation fields: n kind argv rc timed_out duration_s log_path scan_verdict runner_rc retried display_failed,
#   records (parsed @@H data/stat records), findings (scan + rc + runner, merged per §2.8.6)
```
`godot.run` records the run.json invocation entry but does NOT add findings to the Run; the verb calls `run.add_findings(inv.findings)` or dedups
first.

### 2.10 Seeded faults and `h selftest`
Layout: `selftest/faults/<ID>/fault.toml` (+ `files/`), `selftest/clean/<ID>/fault.toml`. ID `^(FAULT|CLEAN)-(P0|A(10|[1-9]))-\d{2}$`, equal to the
dir name. Format:
```toml
id = "FAULT-P0-02"
area = "P0"
title = "scene script hangs in _init during load-check"
fixture = "clean_min"   # tests/fixtures/projects/<name> | "none" (empty dir) | "@sample"
severity = "must"       # must | nice   (CLEAN entries: always must)
source = "plan §7 P0"
# apply: ordered, temp copy only. Ops: write {path, text | from (relative to the fault dir)}; replace {path, old, new,
# count=1} (must match exactly count times); delete {path}. run.args: "{project}", "{fault_dir}" substituted;
# run.no_project = true: do not add --project. expect.regex: all must match (re.MULTILINE over stdout), >= 1 for FAULT.
apply = [{op = "write", path = "scenes/hang.tscn", from = "files/hang.tscn"}]
run = {verb = "check", args = [], env = {}, no_project = false}
expect = {rc = 1, verdict = "FAIL", regex = ['\[harness\.hang\]'], not_regex = [], max_seconds = 30}
```
The table forms `[[apply]]`, `[run]`, `[expect]` are equivalent TOML and equally valid.
`@sample` = `$HARNESS_REPO/sample` copied like a fixture, excluding `.godot/ .harness/ addons/harness/ addons/gdUnit4/`; sample edits need no re-lock.
A fault whose `replace` target is not in the sample yet is `BROKEN` (expected red until B9 lands). `h selftest [--area A]... [--id GLOB] [--jobs N]
[--keep] [--faults-dir DIR]` (`--faults-dir` defaults to `$HARNESS_REPO/selftest`; it is how tests feed synthetic trees). Per entry: fresh dir
`$HARNESS_TMP/selftest-<run-id>/<ID>/proj` <- fixture (without `.godot/`, `.harness/`); apply ops; run `$HARNESS_REPO/tools/harness/h <verb>
[--project <copy>] <args>` with `HARNESS_OUT=<run dir>/entries/<ID>/out`, hard kill at max_seconds + 30; save stdout to `<run
dir>/entries/<ID>/stdout.txt`. Result: `CAUGHT` (rc, verdict, all regex, no not_regex, time <= max_seconds, <= 40 lines), else `MISSED` / `SLOW` /
`OVERFLOW` (> 40 lines) / `BROKEN` (an op failed); CLEAN entries give `PASS` or `FALSEPOS`. Selftest rc: 2 if any fault.toml fails the schema (finding
`<path>: [selftest.bad-fault] error`); 1 if any must entry is not CAUGHT/PASS or any BROKEN/FALSEPOS; 5 if only nice entries missed; else 0. Output:
stat lines `faults: <n> total, <c> caught, <m> missed (must <a>, nice <b>), <s> slow, <o> overflow, <x> broken` and `clean: <n> total, <p> pass, <f>
false-positive`, then one check line per non-success (`FAIL FAULT-P0-02: MISSED expected FAIL rc=1 /\[harness\.hang\]/, got PASS rc=0 in 3.1s`).
`artifacts/matrix.json` lists every entry `{id, area, severity, expected{rc,verdict}, actual{rc, verdict, seconds, first_line, lines}, result}`.
Default `--jobs` = min(4, nproc); results must not depend on it. Temp copies are deleted unless `--keep`.

### 2.11 Fixtures and the B3 temp-copy rule
- B3: no test, selftest entry or verifier ever runs a verb on a project inside the repo tree, except `sample/` by the bootstrap and the orchestrator.
  Copy first (excluding `.godot/`, `.harness/`). After the full suite, `git status --porcelain tests selftest` is empty.
- `tests/fixtures/projects/<name>/`, name `^[a-z0-9_]+$`. Minimum: `project.godot` with `config_version=5`, `[application] config/name="<name>"`,
  `config/features=PackedStringArray("4.7")`; `FIXTURE.md` (<= 5 lines: purpose, owner area, expected `h check` verdict). Never commit `.godot/`,
  `.harness/`, `addons/gdUnit4/`, `addons/harness/` (synced), `*.uid`. Text files only, except `*.png` <= 20 KB under a fixture's `baselines/` or a
  fault's `files/`; <= 200 KB per fixture. Hand-written `.tscn` in fixtures and fault `files/` are allowed (they are inputs, often deliberately
  broken) and follow r1_4 §3 unless broken on purpose.
- Who imports: never the repo copy. The verb under test auto-imports the temp copy (§2.8.7), or a test calls `h import --project <copy>`. Tests may
  cache one imported "warm" copy per fixture per pytest session and copytree it.
- Fixtures are immutable once committed (pathguard): a test-writer that needs a variant creates a new fixture.

### 2.12 Test conventions (all areas)
- pytest only, run from `.venv`. Layers `tests/{unit,contract,gd,e2e}/<area>/`; test names `test_ac_<NN>_<k>_<slug>`.
- Shared helpers (written by T1, read-only for others): `tests/helpers/h.py` with `run_h(*args, cwd=None, env=None, timeout=120) -> Result(rc, stdout,
  lines, verdict, verb, reason, stats, checks, findings, log_dir)`, `copy_fixture(name, dest) -> Path` (name or `"@sample"`, §2.10 exclusions),
  `assert_contract(result)` (the §2.3 grammar incl. the check-line and `more:` forms, the §2.7 rule-id pattern, limits, invariants, run.json schema,
  `summary.txt == stdout`), and `run_godot(args, project, timeout)`, which resolves the binary as §2.8.1 and is the only direct Godot call allowed in
  tests (runner-protocol tests only). `h.py` parses output itself. `tests/helpers/gd.py`: `run_gd_suites(area, fixture="gd_host") -> Result` copies
  the fixture (or `@sample`) to `$HARNESS_TMP`, runs `h sync` (with gdUnit4), copies `tests/gd/<area>/*.gd` to `<copy>/tests/<area>/`, and runs `h
  test --project <copy> res://tests/<area>/`. Each gd area has one pytest wrapper `tests/gd/<area>/test_gd_<area>.py`. `tests/conftest.py` registers
  markers `godot`, `xvfb`, `slow` (> 30 s) and puts `tests/` on `sys.path`.
- Every contract test calls `assert_contract` on each `h` result. Tests never `skip`/`xfail` on a missing environment: a missing Godot yields rc 4 and
  the test fails (skips count as not passed, plan §5.2).
- Unit tests may import only these pure, stdlib-only, side-effect-free modules, via `sys.path` insert of `tools/harness`: `harness.logscan` (scan),
  `harness.out` (render, Run), `harness.scenes.model` (A2), `harness.gdunit` (parse_results, parse_console; A4), `harness.scenario` (load, resolve,
  eval_asserts, compare_golden; A5), `harness.feel` (read_trace, measure, window, rate_spread, judge, is_approved; A7), `harness.wiring`
  (merge_settings; A8). A3 tests read `tools/harness/rules/*.json` as data. Everything else (incl. `harness.checkrun`) is not public.

### 2.13 Role write allowlists (`tools/dev/pathguard.sh`; `<a>` = area id, lowercase; any role: `.claude/handoff/<a>/status.md`)
| Role | May write |
|---|---|
| orchestrator | `.claude/plans/build_and_test_plan.md`, `.claude/sessions/*`, `.claude/handoff/*`, `tests/LOCK.sha256`, `.gitignore`, `CLAUDE.md`, `README.md`; Δ `tools/dev/*` (small fixes only) |
| planner | `.claude/plans/specs/[0-9]*_*.md`, `.claude/research/r2_*_spike.md` |
| spec-reviewer | `.claude/plans/specs/REVIEW.md` |
| test-writer | `tests/{contract,unit,gd,e2e}/<a>/*`, new files under `tests/fixtures/*`, Δ `selftest/faults/fault-<a>-*`, Δ `selftest/clean/clean-<a>-*`, `.claude/handoff/<a>/test_notes.md`; Δ area `a1` also `tests/conftest.py`, `tests/helpers/*` |
| builder | `tools/harness/*`, `addons/harness/*`, `templates/*`, `sample/*`, `docs/*`, `.claude/handoff/<a>/{build_notes,test_disputes}.md`; Δ area `a1` also `tools/bootstrap.sh` |
| verifier | `.claude/handoff/<a>/verify_*.{md,json}` |
| adjudicator | `tests/{contract,unit,gd,e2e}/<a>/*`, `.claude/handoff/<a>/test_disputes.md` |
Δ `<area>` may be a comma list (`a1,p0,bootstrap`); a path passes if any listed area allows it. P0's tests and faults are written by T1 with areas
`a1,p0,bootstrap`.

### 2.14 Test lock (exists; unchanged except Δ prune)
`tests/LOCK.sha256`: one `<sha256>  <path>` line per file under `tests/` and `selftest/`, `LC_ALL=C` sorted, paths repo-relative, excluding the lock,
`__pycache__`, `.pytest_cache`, `.godot`, Δ `.harness`, `*.pyc`. Written only by the orchestrator (`lock_tests.sh`, commit `[lock] <areas>`);
`check_lock.sh` rc 0 ok / 1 changed / 3 no lock. An adjudicated test change is re-locked by the orchestrator in its own commit.

### 2.15 Handoff `status.md` (every agent, before it returns)
```
area: <ID> <slug>      phase: plan|tests|build|verify      state: todo|in-progress|blocked|done
spec: <path> @ <commit|uncommitted>
tests: <N> total / <P> pass / <F> fail (<ids>)      lock: <sha12|n/a>
updated: <YYYY-MM-DD> by <role> (<model>)
done:
next:
blockers:
disputes: <n> open
```
Keys are fixed and in this order; `done:`, `next:` and `blockers:` are each followed by `- <bullet>` lines (`- none` if empty). A new session
resumes from `next:`.

## 3. Design

### 3.1 Files (all built by the A1 builder B1 as its step 0/1; A1's spec must list them)
`tools/harness/harness/out.py` (Run, render, common_parser, run-dir management, retention, latest link), `project.py`, `config.py`, `logscan.py`,
`godot.py` (binary, version cache, run, spawn, timeouts, process groups, xvfb cleanup/retry, merge, ensure_imported), `proc.py` (timeout-safe
subprocess for non-Godot tools), `faults.py` (fault.toml loader + validator, `@sample`), `verbs/selftest.py`; Δ `cli.py`, `verbs/doctor.py`, `h`.

### 3.2 Changes to existing code (Δ)
| # | File | Change | Who |
|---|---|---|---|
| C1 | `tools/harness/h` | drop `cd "$HERE"` | B1 |
| C2 | `harness/cli.py` | `_`->`-` names, trailing `_` dropped; `HELP` one per line; unknown verb to stdout + did-you-mean | B1 |
| C3 | `verbs/doctor.py` | use `out.Run`; verdict line; keep check lines; missing required tool -> rc 4 | B1 |
| C4 | `tests/unit/bootstrap/test_doctor.py` | `"doctor: ok"` -> first line `PASS doctor`; rc != 0 -> rc == 4 | T1 |
| C5 | `tools/dev/pathguard.sh` | comma-separated areas; `fault-<a>-*`/`clean-<a>-*`; a1 extras (§2.13) | orchestrator |
| C6 | `tools/dev/_common.sh` | also prune `.harness` in `lock_manifest` | orchestrator |
| C7 | `tools/dev/ci.sh` | rc 5 from `h` layers = PASS (warn); gd layer = `pytest tests/gd` (helpers copy `gd_host`, B3) | orchestrator |
| C8 | `tools/bootstrap.sh` | step 9: `h sync --project sample`, `h import --project sample` | B1 |
| C9 | `tools/harness/requirements-dev.txt` | add `jsonschema` (test helper validates run.json) | B1 |
| C10 | `.gitignore` | add `sample/addons/gdUnit4/`, `sample/addons/harness/`, `reports/` | orchestrator |
| C11 | plan §3.1/§10 text | `fault.yaml` -> `fault.toml`; drop `expected_matrix.yaml`; `rules/lint_rules.yaml` ships as JSON (A3) | orchestrator |
C5-C7 and C10 are dev-tool edits of <= 20 lines each; the orchestrator applies them before Phase 2 (T1 needs C5).

### 3.3 Why these choices
TOML/JSON: stdlib `tomllib`. `res://` locations: stable across temp copies. Runners outside the project (S1): no `addons/` needed. Hang/crash =
FAIL (fix your code), ERROR = fix harness/env. Content staleness (R-24): an mtime rule re-imported on every `.gd` edit (4.6 s vs 2.5 s budget).

### 3.4 Spikes (scratchpad `p0/proj`, Godot 4.7.stable.official.5b4e0cb0f)
- [Run] `-s res://ok.gd` prints only the banner `Godot Engine v4.7.stable.official.5b4e0cb0f - https://godotengine.org`, a blank line, then script
  output; rc 0. Banner goes in the benign list. `OS.crash("boom")` -> `ERROR: boom`, process `Aborted`, rc 134.
- [Run] leak: `var n=Node.new(); quit(0)` -> `WARNING: 1 ObjectDB instance was leaked at exit (run with `--verbose` for details).` + `   at: cleanup
  (core/object/object.cpp:2535)`, rc 0 -> `godot.leak` info, C++ location ignored.
- [Run] `push_warning("w1")`/`push_error("e1")` -> `WARNING: w1` / `ERROR: e1`, each followed by `GDScript backtrace (most recent call first):` and
  `[0] _init (res://pe.gd:3)` / `(res://pe.gd:4)`, rc 0.
- [Run] `--check-only -s res://bad.gd` -> `SCRIPT ERROR: Parse Error: Expected expression after "+" operator.` + `at: GDScript::reload
  (res://bad.gd:3)` + `ERROR: Failed to load script "res://bad.gd" with error "Parse error".`
- [Run] runtime null call: `SCRIPT ERROR: Invalid call. Nonexistent function 'foo' in base 'Nil'.` + `at: _init (res://rt.gd:4)`; process hangs;
  `timeout -k 2 5` -> rc 124 after 5.01 s with the log fully flushed.
- [Run] after `--import`, `vis/b.png` was imported, `.harness/out/a.png` was not (hidden dirs skipped); `.gdignore` is belt and braces.
- [Run, REVIEW §7] scene `_ready` calling `get_tree().quit(0)` under a `-s` runner awaiting 2 physics frames: no `done`, rc 0 (FAULT-P0-06).
  The class cache `list` holds comparable `class`/`path` pairs (§2.8.7).

## 4. Acceptance criteria (T1 writes these under `tests/{unit,contract}/p0/`)
- AC-00.1 `h --help` rc 0, <= 40 lines, lists every `verbs/*.py` (hyphenated, trailing `_` dropped), wall <= 0.5 s. [contract]
- AC-00.2 `h nosuchverb` -> rc 2, stdout exactly 1 line `^ERROR h unknown verb 'nosuchverb'`; `h` alone -> rc 2. [contract]
- AC-00.3 For every verb listed by `h --help`: `h <v> --help` rc 0, <= 40 lines, no new run dir. [contract]
- AC-00.4 For every listed verb: `h <v> --no-such-flag` -> rc 2, line 1 `^ERROR <v> usage: `, last line `^log: `. [contract]
- AC-00.5 Every `h` result in the P0 and A1 contract suites passes `assert_contract` (§2.12). [contract]
- AC-00.6 `run.json` validates against the §2.5 schema; `summary.txt` == stdout; `findings.jsonl` count == `findings_total`; run id matches the regex;
  `<out root>/latest` points to it; `.harness/.gdignore` exists. [contract]
- AC-00.7 `HARNESS_OUT=<dir>` puts the run dir under `<dir>`. [contract]
- AC-00.8 Project resolution: `--project` relative to a different cwd works; `HARNESS_PROJECT` works; cwd inside a subdir of the project works; none
  -> rc 2 `no Godot project`. [contract]
- AC-00.9 `harness.toml` with unknown key `[harness] tick_rat = 60` -> rc 2, finding `res://harness.toml: [harness.config] error:` naming `tick_rat`;
  invalid TOML -> rc 2; no file -> defaults. [contract]
- AC-00.10 `[scan] ignore = ["SCRIPT ERROR"]` -> rc 2 `[harness.config]`. [contract]
- AC-00.11 `HARNESS_GODOT=/nonexistent/godot h check` -> rc 4, `^ERROR check godot binary not found`, wall <= 2 s. [contract]
- AC-00.12 `HARNESS_GODOT=<fixture script printing 4.6.stable.official.x>` -> rc 4, `[harness.godot-version]`. [contract]
- AC-00.13 Hang (FAULT-P0-02 setup, `runner = 5`): rc 1, `[harness.hang]`; in run.json the invocation has `timed_out: true`, `rc: 124`, `duration_s <=
  10`; no process whose cmdline contains the copy path survives. [contract]
- AC-00.14 Parse-broken script attached to a scene (FAULT-P0-03 setup; loading that scene alone exits 0, S2): rc 1, a finding at
  `res://scripts/broken.gd:4`. [contract]
- AC-00.15 `OS.crash` in a scene script (FAULT-P0-07 setup): rc 1, `[harness.crash]`, invocation rc 134. [contract]
- AC-00.16 `logscan.scan` on the §3.4 logs returns exactly: parse error -> (`godot.parse-error`, `res://bad.gd`, 3), plus (`godot.script-load-failed`,
  `res://bad.gd`, None); runtime -> (`godot.script-error`, `res://rt.gd`, 4); push_error -> (`godot.error`, `res://pe.gd`, 4); push_warning ->
  (`godot.warning`, `res://pe.gd`, 3); leak -> (`godot.leak`, None, None, info); banner, `@@H` lines and `ERROR: remote port number must be between 1
  and 65535` -> nothing; no finding ever has a non-`res://` path. [unit]
- AC-00.17 `out.render` with 100 findings: <= 40 lines, errors before warnings, truncation line counts correct, lines <= 240 chars, duplicates
  collapsed with `(xN)`; `--strict` maps a warnings-only set to FAIL. [unit]
- AC-00.18 `out.Run` whose body raises -> rc 3, line 1 `^ERROR <v> internal: `, `traceback.txt` written. [unit]
- AC-00.19 `HARNESS_TIMEOUT_SCALE=0.5` halves `timeout_s` in run.json; `HARNESS_TIMEOUT_SCALE=50` -> rc 2. [contract]
- AC-00.20 Godot argv in run.json starts with the resolved binary, contains `--headless` and `--path <abs copy>`. [contract]
- AC-00.21 `h selftest --area P0` -> rc 0; stats show 8 faults all caught, 2 clean pass; `artifacts/matrix.json` has 10 entries; wall <= 120 s.
  [contract, slow]
- AC-00.22 `h selftest --faults-dir <synthetic>`: an unmeetable must fault -> rc 1 + `FAIL <id>: MISSED`; only a nice miss -> rc 5; a `replace` that
  matches 0 times -> `BROKEN`, rc 1; a clean entry that fails -> `FALSEPOS`, rc 1; missing `expect.rc` -> rc 2 `[selftest.bad-fault]`; max_seconds
  0.001 -> `SLOW`; a verb flooding > 40 lines is not possible by contract, so OVERFLOW is unit-tested on the comparator. [contract + unit]
- AC-00.23 `--jobs 1` and `--jobs 4` give the same matrix results; fixture source trees are byte-identical before/after; temp dirs are gone without
  `--keep`, present with it. [contract, slow]
- AC-00.24 After the full contract suite, `git status --porcelain tests selftest` is empty (B3). [e2e]
- AC-00.25 `pathguard.sh test-writer a1,p0 working-tree` accepts `selftest/faults/FAULT-P0-01/fault.toml` and `tests/helpers/h.py`; `pathguard.sh
  test-writer a2 ...` rejects both. `check_lock.sh` ignores a new `tests/fixtures/x/.harness/` file. [unit, uses `HARNESS_ROOT` temp repos]
- AC-00.26 `h doctor` follows §2.3 (examples) and returns 4 when a required tool is missing (C3/C4). [contract]
- AC-00.27 Class-cache staleness by content (R-24), on a copy of `clean_min` after `h import`: (a) append a method to `scripts/hello.gd` keeping
  `class_name Hello` -> `h check` prints `import: fresh`; (b) add `scripts/extra.gd` with `class_name Extra` -> a stat line matching
  `^import: ran \(stale class cache \(.*extra\.gd\)\)$`; (c) delete `.godot/global_script_class_cache.cfg` -> `^import: ran `. All rc 0. [contract]
Untestable automatically: handoff format (§2.15; checked by the orchestrator on read).

## 5. Seeded faults (fixture `clean_min`, verb `check` unless noted; all `must`)
| ID | Planted | Expect |
|---|---|---|
| FAULT-P0-01 | `run.env = {HARNESS_GODOT="/nonexistent/godot"}` | rc 4, ERROR, `godot binary not found`, <= 5 s |
| FAULT-P0-02 | write `scripts/hang.gd` (`extends Node` + `func _init(): while true: pass`), `scenes/hang.tscn` (root Node with that script), `harness.toml` `[timeouts] runner = 5` | rc 1, FAIL, `\[harness\.hang\]`, <= 40 s (incl. import) |
| FAULT-P0-03 | write `scripts/broken.gd` with a parse error on line 4, `scenes/uses_broken.tscn` attaching it (Godot loads the scene with rc 0, S2) | rc 1, FAIL, `^res://scripts/broken\.gd:4: \[`, <= 40 s |
| FAULT-P0-04 | write 60 files `scripts/bad_NN.gd`, each with a parse error | rc 1, FAIL, `^\.\.\. \d+ more findings`, <= 40 lines, <= 90 s |
| FAULT-P0-05 | write `harness.toml` = `[harness]\ntick_rat = 60\n` | rc 2, ERROR, `tick_rat`, <= 5 s |
| FAULT-P0-06 | write `scripts/quit_early.gd` (`extends Node` / `func _ready() -> void:` / `\tget_tree().quit(0)`) and `scenes/quit_early.tscn` (root Node with that script); args `["--smoke"]` (project code quits rc 0 before the runner prints `done`, [Run] §3.4) | rc 1, FAIL, `\[harness\.runner-incomplete\]`, <= 40 s |
| FAULT-P0-07 | scene script whose `_init` calls `OS.crash("boom")` | rc 1, FAIL, `\[harness\.crash\]` |
| FAULT-P0-08 | delete `project.godot` | rc 2, ERROR, `no Godot project`, <= 5 s |
| CLEAN-P0-01 | none | rc 0, PASS, `^import: ran` |
| CLEAN-P0-02 | fixture `none`, verb `doctor`, `no_project = true` | rc 0, PASS |

## 6. Fixtures needed (T1)
- `tests/fixtures/projects/clean_min/`: `project.godot` (§2.11; `run/main_scene="res://scenes/main.tscn"`), `scripts/hello.gd` (`class_name Hello
  extends Node2D`, typed, warning-free), `scenes/main.tscn` (root `Node2D` with that script, one `Sprite2D` child, hand-written per r1_4 §3),
  `FIXTURE.md`. Must PASS `h check` (CLEAN-P0-01).
- `tests/fixtures/projects/gd_host/`: §2.11 minimum plus `[autoload]` Harness, Rng, CommandBus, Trace as `*res://addons/harness/<snake>.gd`; no tests
  (used by `run_gd_suites`, §2.12).
- `tests/fixtures/bin/godot_wrong_version` (executable sh: prints `4.6.stable.official.deadbeef`, exit 0).
- `tests/fixtures/selftest_trees/{miss_must,miss_nice,broken_op,falsepos,bad_schema,slow}/` (AC-00.22; use `doctor` with `no_project` or `check` on
  `clean_min`).
- `tests/fixtures/logs/*.log`: the §3.4 excerpts verbatim (AC-00.16).

## 7. Build order (B1, step 0/1 of A1; each step ends green on the named ACs)
1. C1, C2, `out.py`, `project.py`, `config.py`, C3 doctor -> AC-00.1-4, 6-9 (with doctor and a stub-free `check` arriving in A1), 17, 18, 26.
2. `logscan.py` (ANSI strip, location fallback) -> AC-00.16, 10.
3. `godot.py` (run incl. `project=None`, spawn, xvfb cleanup/retry, `Invocation`, content-based `ensure_imported`) + `proc.py` (needs A1's `check` +
   `load_check.gd` runner) -> AC-00.11-15, 19, 20, 27.
4. `faults.py` (incl. `@sample`), `verbs/selftest.py` -> AC-00.21-23.
5. C8, C9; orchestrator applies C5-C7, C10, C11 before Phase 2 -> AC-00.24, 25.

## 8. Out of scope, open questions, assumptions
Out of scope: Windows/macOS, a global `--json` stdout mode (verbs such as `digest --json` define their own), LSP daemon lifecycle (A3), C# (`h test
--dotnet` stub, D1), parallel runs against one project dir (B3 avoids it). Open [U]: (2) Godot output to stdout vs stderr interleaving in one pipe
keeps order per write, not strictly by time; (4) whether `.harness/` inside a project confuses `--import` on 4.7.x patch releases (hidden-dir skip
verified only on 4.7.0); (5) whether the class cache's `base` field matters for staleness (not compared, §2.8.7). Closed: (1) autoloads are
instantiated under `-s`, after the runner's `_init` [Run A1 K, A4 K13]; the old FAULT-P0-06 premise could not fire and was replaced (R-25). (3)
`xvfb-run` exit status on group kill: answered by A6 §3.5.

### 8.1 Accepted deviations and review decisions applied (REVIEW.md v1)
R-01 unit-import allowlist (§2.12); R-03 `api.` prefix (§2.7); R-04 trailing `_` module names (§2.1, C2); R-05 `project=None`/`cwd` (§2.8.2,
§2.9); R-06 ANSI strip + location fallback (§2.8.4); R-07 verb-level stricter dedup (§2.8.6); R-09 `oracle`/`lsp_start`, `godot.spawn` (§2.8);
R-10 `@sample` (§2.10, §2.12); R-11 PNG exception (§2.11); R-12 runner `load()` of `_` libraries (§2.8.5); R-13 headless clause for image capture
only (§2.8.2); R-14 xvfb cleanup/retry/`display_failed` (§2.8.3, run.json); R-16 default autoloads + Trace (§2.6); R-22 `more:` stat, plan §7
digest "<= 60 lines" superseded (§2.3); R-24 content-based staleness, mtime rule dropped (§2.8.7, AC-00.27); R-25 FAULT-P0-06 replaced, now must
(§5); R-31 `Invocation`, findings not auto-added (§2.9); R-32 explicit `ensure_imported` (§2.8.7); R-38 rule-id pattern (§2.7); R-39 `run_godot`,
`gd.py`, `gd_host` (§2.12, §6, C7); R-44 `init --new`, R-45 env vars, R-48 `lsp stop --all` (§2.2); R-46 one CONFIG_TABLE owner (§2.6); R-50
check-line grammar (§2.3). Own deviation from the plan: TOML/JSON instead of YAML, no `expected_matrix.yaml` (C11).

Assumptions (reconciled in REVIEW.md): A1 owns `check import sync doctor api`, `harness/sync.py` (R-33), the `load_check` runner and steps 0/1
above; A4 maps gdUnit4 rcs into §2.4 (103 -> rc 4) and may downgrade only non-protected scan rules; A8 hooks read `log:` then `findings.jsonl`.
Plan defaults D1-D5 and B1-B8 are taken as given; S6 -> single working branch.
